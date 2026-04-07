import time
import os
import threading
import traceback
import subprocess
import numpy as np
import cv2
from datetime import datetime
from flask import Flask, render_template, send_from_directory, Response, request, jsonify

from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FfmpegOutput
from libcamera import Transform, controls

# ========= Einstellungen =========
FPS = 18
RES_MAIN = (1600, 1200)
ROI_NORM = (0.25, 0.0, 0.75, 1.0)
ROTATE_180 = True
BITRATE = 10_000_000
OUTPUT_PATH = "recordings"
BRIGHTNESS_THRESHOLD = 30.0
CHECK_EVERY_S = 0.05
DEBUG_PRINT_EVERY = 20
LORES_SIZE = (640, 480)
NUM_SAMPLES = 3
AWB_MODE = "Auto"
preview_while_recording = False
stream_active = False

AWB_MODES = {
    "Tungsten":    controls.AwbModeEnum.Tungsten,
    "Indoor":      controls.AwbModeEnum.Indoor,
    "Fluorescent": controls.AwbModeEnum.Fluorescent,
    "Daylight":    controls.AwbModeEnum.Daylight,
    "Cloudy":      controls.AwbModeEnum.Cloudy,
    "Auto":        controls.AwbModeEnum.Auto,
}

if not os.path.exists(OUTPUT_PATH):
    os.makedirs(OUTPUT_PATH)


# ========= Flask Webserver =========
app = Flask(__name__)
picam2 = Picamera2()


def gen_frames():
    global stream_active
    stream_active = True
    try:
        while True:
            frame = picam2.capture_array("lores")
            y_frame = frame[:LORES_SIZE[1], :LORES_SIZE[0]]
            ret, buffer = cv2.imencode('.jpg', y_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if not ret:
                continue
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(1 / FPS)
    except GeneratorExit:
        pass
    finally:
        stream_active = False


@app.route('/')
def index():
    files = []
    for f in sorted([f for f in os.listdir(OUTPUT_PATH) if f.endswith('.mp4')], reverse=True):
        path = os.path.join(OUTPUT_PATH, f)
        files.append({
            'name': f,
            'size': f"{os.path.getsize(path) / 1024 / 1024:.2f} MB"
        })
    return render_template('index.html', files=files)


@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/download/<filename>')
def download(filename):
    return send_from_directory(OUTPUT_PATH, filename, mimetype='video/mp4')


@app.route('/delete/<filename>', methods=['DELETE'])
def delete(filename):
    path = os.path.join(OUTPUT_PATH, filename)
    if os.path.exists(path):
        os.remove(path)
        return jsonify({'status': 'ok'})
    return jsonify({'status': 'not found'}), 404


@app.route('/set_config', methods=['POST'])
def set_config():
    global BRIGHTNESS_THRESHOLD, FPS, BITRATE
    data = request.get_json()
    if 'threshold' in data:
        BRIGHTNESS_THRESHOLD = float(data['threshold'])
    if 'fps' in data:
        FPS = int(data['fps'])
    if 'bitrate' in data:
        BITRATE = int(data['bitrate']) * 1_000_000
    return jsonify({'status': 'ok', 'threshold': BRIGHTNESS_THRESHOLD, 'fps': FPS, 'bitrate': BITRATE // 1_000_000})


@app.route('/get_config')
def get_config():
    return jsonify({'threshold': BRIGHTNESS_THRESHOLD, 'fps': FPS, 'bitrate': BITRATE // 1_000_000, 'preview_while_recording': preview_while_recording, 'awb': AWB_MODE})


@app.route('/set_awb', methods=['POST'])
def set_awb():
    global AWB_MODE
    data = request.get_json()
    mode = data.get('mode', 'Auto')
    if mode in AWB_MODES:
        AWB_MODE = mode
        picam2.set_controls({"AwbMode": AWB_MODES[mode]})
        print(f"AWB: {mode}")
    return jsonify({'status': 'ok', 'awb': AWB_MODE})


@app.route('/set_preview', methods=['POST'])
def set_preview():
    global preview_while_recording
    data = request.get_json()
    preview_while_recording = bool(data.get('enabled', False))
    print(f"Live Preview while Recording: {'an' if preview_while_recording else 'aus'}")
    return jsonify({'status': 'ok', 'preview_while_recording': preview_while_recording})

@app.route('/set_time', methods=['POST'])
def set_time():
    data = request.get_json()
    iso_time = data.get('time')
    try:
        subprocess.run(['sudo', 'date', '-s', iso_time], check=True)
        return jsonify({'status': 'ok', 'time': iso_time})
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)})

# ========= Kamera-Logik =========
def average_brightness_y_plane_yuv420(frame_yuv, lores_size):
    w, h = lores_size
    y_plane = frame_yuv[:h, :w]
    return float(np.mean(y_plane))


def camera_worker():
    frame_us = int(round(1_000_000 / FPS))
#    min_frame_us = int(frame_us / 2)
    camera_controls = {
        "FrameDurationLimits": (frame_us, frame_us),
        "AfMode": controls.AfModeEnum.Manual,
        "ExposureTime": frame_us,
    }
    transform = Transform(hflip=1, vflip=1) if ROTATE_180 else Transform()

    config = picam2.create_video_configuration(
        main={"size": RES_MAIN, "format": "YUV420"},
        lores={"size": LORES_SIZE, "format": "YUV420"},
        encode="main", transform=transform, controls=camera_controls
    )
    picam2.configure(config)
    picam2.start()

    sensor_w, sensor_h = picam2.camera_properties.get("PixelArraySize")
    rect = (
        int(ROI_NORM[0] * sensor_w), int(ROI_NORM[1] * sensor_h),
        int(ROI_NORM[2] * sensor_w), int(ROI_NORM[3] * sensor_h)
    )

    picam2.set_controls({
        "ScalerCrop": rect,
        "AwbMode": AWB_MODES[AWB_MODE],
        "Saturation": 1.4,
        "Sharpness": 0.2,
        "Contrast": 0.9,
        "NoiseReductionMode": 0
    })

    recording = False
    loop_count = 0
    consecutive_dark_count = 0

    try:
        while True:
            lo = picam2.capture_array("lores")
            avg = average_brightness_y_plane_yuv420(lo, LORES_SIZE)

            metadata = picam2.capture_metadata()
            gain = metadata.get("AnalogueGain", 0)
            exp = metadata.get("ExposureTime", 0)
            colour_gains = metadata.get("ColourGains", (0, 0))
            colour_temp = metadata.get("ColourTemperature", 0)

            if DEBUG_PRINT_EVERY and (loop_count % DEBUG_PRINT_EVERY == 0):
                print(f"[{time.strftime('%H:%M:%S')}] avgY={avg:.1f}  "
                      f"({'REC' if recording else '---'})  thr={BRIGHTNESS_THRESHOLD:.1f}  "
                      f"dark_cnt={consecutive_dark_count}  stream={stream_active}  "
                      f"preview_while_rec={preview_while_recording}  "
                      f"gain={gain:.2f}  exp={exp}  "
                      f"R={colour_gains[0]:.2f}  B={colour_gains[1]:.2f}  temp={colour_temp}K")

            frame_us = int(round(1_000_000 / FPS))

            if avg < BRIGHTNESS_THRESHOLD:
                consecutive_dark_count += 1
                if recording and consecutive_dark_count >= NUM_SAMPLES:
                    picam2.stop_recording()
                    recording = False
                    print("Aufnahme gestoppt (Dunkelheit)")
                    picam2.start()
            else:
                consecutive_dark_count = 0
                if not recording and (not stream_active or preview_while_recording):
                    filename = os.path.join(OUTPUT_PATH, datetime.now().strftime("%y-%m-%d_%H-%M-%S") + ".mp4")
                    encoder = H264Encoder(bitrate=BITRATE, framerate=FPS, enable_sps_framerate=True)
                    output = FfmpegOutput(filename)
                    picam2.start_recording(encoder, output=output)
                    recording = True
                    print(f"Aufnahme startet: {filename}")
                elif recording and stream_active and not preview_while_recording:
                    picam2.stop_recording()
                    recording = False
                    print("Aufnahme gestoppt (Stream aktiv)")
                    picam2.start()

            loop_count += 1
            time.sleep(CHECK_EVERY_S)
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    t = threading.Thread(target=camera_worker, daemon=True)
    t.start()
    app.run(host='0.0.0.0', port=80, threaded=True)
