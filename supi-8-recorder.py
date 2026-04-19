import time
import os
import threading
import traceback
import subprocess
import numpy as np
import cv2
from datetime import datetime
from flask import Flask, render_template, send_from_directory, Response, request, jsonify, redirect
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FileOutput
from libcamera import Transform, controls

# ========= Einstellungen =========
FPS = 18
RES_MAIN = (1600, 1200)
ROI_NORM = (0.25, 0.0, 0.75, 1.0)
ROTATE_180 = True
BITRATE = 10_000_000
OUTPUT_PATH = "recordings"
BRIGHTNESS_THRESHOLD = 50
CHECK_EVERY_S = 0.1
DEBUG_PRINT_EVERY = 10
LORES_SIZE = (640, 480)
NUM_SAMPLES = 3
AWB_MODE = "Auto"
PEAKING_THRESHOLD = 75
AWB_MODES = {
    "Tungsten":    controls.AwbModeEnum.Tungsten,
    "Indoor":      controls.AwbModeEnum.Indoor,
    "Fluorescent": controls.AwbModeEnum.Fluorescent,
    "Daylight":    controls.AwbModeEnum.Daylight,
    "Cloudy":      controls.AwbModeEnum.Cloudy,
    "Auto":        controls.AwbModeEnum.Auto,
}

# ========= Sonstiges =========

preview_while_recording = False
stream_active = False
camera_status = {"avg": 0.0, "focus": 0.0, "gain": 0.0, "temp": 0, "recording": False}

focus_peaking = False

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
 
            if focus_peaking:
                bgr = cv2.cvtColor(y_frame, cv2.COLOR_GRAY2BGR)
                gaussblurr = cv2.GaussianBlur(y_frame, (3, 3), 0)
                edges = cv2.Laplacian(gaussblurr, cv2.CV_16S, ksize=3)
                edges = cv2.convertScaleAbs(edges)
                _, mask = cv2.threshold(edges, PEAKING_THRESHOLD, 255, cv2.THRESH_BINARY)
                bgr[mask > 0] = (0, 0, 255)
                ret, buffer = cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, 70])
            else:
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
    return jsonify({'status': 'ok', 'threshold': BRIGHTNESS_THRESHOLD, 'fps': FPS, 'bitrate': BITRATE // 1_000_000,})


@app.route('/get_config')
def get_config():
    return jsonify({'threshold': BRIGHTNESS_THRESHOLD, 
                    'fps': FPS, 
                    'bitrate': BITRATE // 1_000_000, 
                    'preview_while_recording': preview_while_recording,
                    'focus_peaking': focus_peaking,
                    'peaking_threshold': PEAKING_THRESHOLD,
                    'awb': AWB_MODE})


@app.route('/get_status')
def get_status():
    return jsonify(camera_status)


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

@app.route('/set_peaking', methods=['POST'])
def set_peaking():
    global focus_peaking
    data = request.get_json()
    focus_peaking = bool(data.get('enabled', False))
    return jsonify({'status': 'ok', 'focus_peaking': focus_peaking})


# ========= Captive Portal =========

@app.route('/hotspot-detect.html')         # iOS
@app.route('/generate_204')                # Android
@app.route('/connectivity-check.html')     # older Android
@app.route('/ncsi.txt')                    # Windows
def captive_portal():
    return redirect('http://10.42.0.1/', 302)

# ========= Muxen nach Aufnahme =========

def mux_and_remove_raw(raw_file, mp4_file, fps):
    cmd = ["ffmpeg", "-y", "-r", str(fps), "-i", raw_file, "-c", "copy", mp4_file]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.remove(raw_file)
        print(f"Muxing done, raw file removed: {mp4_file}")
    except Exception as e:
        print(f"Error while muxing {raw_file}: {e}")




# ========= Kamera-Logik =========
def average_brightness_y_plane_yuv420(frame_yuv, lores_size):
    w, h = lores_size
    y_plane = frame_yuv[:h, :w]
    return float(np.mean(y_plane))


def camera_worker():
    global camera_status
    frame_us = int(round(1_000_000 / FPS))
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
    filename = None

    try:
        while True:
            lo = picam2.capture_array("lores")
            avg = average_brightness_y_plane_yuv420(lo, LORES_SIZE)

            metadata = picam2.capture_metadata()
            gain = metadata.get("AnalogueGain", 0)
            exp = metadata.get("ExposureTime", 0)
            colour_gains = metadata.get("ColourGains", (0, 0))
            colour_temp = metadata.get("ColourTemperature", 0)
            focus = metadata.get("FocusFoM", 0)

            if DEBUG_PRINT_EVERY and (loop_count % DEBUG_PRINT_EVERY == 0):
                print(f"[{time.strftime('%H:%M:%S')}] avgY={avg:.1f}  "
                      f"({'REC' if recording else '---'})  thr={BRIGHTNESS_THRESHOLD:.1f}  "
                      f"dark_cnt={consecutive_dark_count}  stream={stream_active}  "
                      f"preview_while_rec={preview_while_recording}  "
                      f"focus_peaking={focus_peaking}  "
                      f"gain={gain:.2f}  exp={exp}  "
                      f"R={colour_gains[0]:.2f}  B={colour_gains[1]:.2f}  temp={colour_temp}K  "
                      f"focus={focus:.2f}"
                      )

            camera_status.update({
                "avg": round(avg, 1),
                "focus": round(focus, 1),
                "gain": round(gain, 2),
                "temp": colour_temp,
                "recording": recording,
            })

            frame_us = int(round(1_000_000 / FPS))

            if avg < BRIGHTNESS_THRESHOLD:
                consecutive_dark_count += 1
                if recording and consecutive_dark_count >= NUM_SAMPLES:
                    picam2.stop_encoder()
                    recording = False
                    mp4_filename = filename.replace(".h264", ".mp4")
                    threading.Thread(
                        target=mux_and_remove_raw, 
                        args=(filename, mp4_filename, FPS),
                        daemon=True
                    ).start()
                    
                    print(f"Recording stopped, muxing in background...")
            
            else:
                consecutive_dark_count = 0
                if not recording and (not stream_active or preview_while_recording):
                    filename = os.path.join(OUTPUT_PATH, datetime.now().strftime("%y-%m-%d_%H-%M-%S") + ".h264")
                    encoder = H264Encoder(bitrate=BITRATE, framerate=FPS, enable_sps_framerate=True)
                    output = FileOutput(filename)
                    picam2.start_encoder(encoder, output)
                    recording = True
                    print(f"Recording started: {filename}")

                elif recording and stream_active and not preview_while_recording:
                    picam2.stop_encoder()
                    recording = False
                    print("Recording stopped (preview)")

            loop_count += 1
            time.sleep(CHECK_EVERY_S)
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    t = threading.Thread(target=camera_worker, daemon=True)
    t.start()
    app.run(host='0.0.0.0', port=5091, threaded=True)