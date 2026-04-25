import os
import cv2
import time
import subprocess
from flask import Flask, render_template, send_from_directory, Response, request, jsonify, redirect

import camera

# Flask Setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "../templates")
)


# Preview stream
def gen_frames():
    camera.stream_active = True
    try:
        while True:
            frame = camera.picam2.capture_array("lores")
            y_frame = frame[:camera.LORES_SIZE[1], :camera.LORES_SIZE[0]]

            if camera.focus_peaking:
                bgr = cv2.cvtColor(y_frame, cv2.COLOR_GRAY2BGR)
                gaussblur = cv2.GaussianBlur(y_frame, (3, 3), 0)
                edges = cv2.Laplacian(gaussblur, cv2.CV_16S, ksize=3)
                edges = cv2.convertScaleAbs(edges)
                _, mask = cv2.threshold(edges, camera.PEAKING_THRESHOLD, 255, cv2.THRESH_BINARY)
                bgr[mask > 0] = (0, 0, 255)
                ret, buffer = cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, 70])
            else:
                ret, buffer = cv2.imencode('.jpg', y_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])

            if not ret:
                continue
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(1 / camera.FPS)
    except GeneratorExit:
        pass
    finally:
        camera.stream_active = False


# Routes
@app.route('/')
def index():
    files = []
    for f in sorted([f for f in os.listdir(camera.OUTPUT_PATH) if f.endswith('.mp4')], reverse=True):
        path = os.path.join(camera.OUTPUT_PATH, f)
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
    return send_from_directory(camera.OUTPUT_PATH, filename, mimetype='video/mp4')


@app.route('/delete/<filename>', methods=['DELETE'])
def delete(filename):
    path = os.path.join(camera.OUTPUT_PATH, filename)
    if os.path.exists(path):
        os.remove(path)
        return jsonify({'status': 'ok'})
    return jsonify({'status': 'not found'}), 404


@app.route('/set_config', methods=['POST'])
def set_config():
    data = request.get_json()
    if 'threshold' in data:
        camera.BRIGHTNESS_THRESHOLD = float(data['threshold'])
    if 'fps' in data:
        camera.FPS = int(data['fps'])
    if 'bitrate' in data:
        camera.BITRATE = int(data['bitrate']) * 1_000_000
    return jsonify({'status': 'ok',
                    'threshold': camera.BRIGHTNESS_THRESHOLD,
                    'fps': camera.FPS,
                    'bitrate': camera.BITRATE // 1_000_000})


@app.route('/get_config')
def get_config():
    return jsonify({
        'threshold': camera.BRIGHTNESS_THRESHOLD,
        'fps': camera.FPS,
        'bitrate': camera.BITRATE // 1_000_000,
        'preview_while_recording': camera.preview_while_recording,
        'focus_peaking': camera.focus_peaking,
        'peaking_threshold': camera.PEAKING_THRESHOLD,
        'focus_max': camera.FOCUS_MAX,
        'gain_too_high': camera.GAIN_TOO_HIGH,
        'awb': camera.AWB_MODE,
    })


@app.route('/get_status')
def get_status():
    return jsonify(camera.camera_status)


@app.route('/set_awb', methods=['POST'])
def set_awb():
    data = request.get_json()
    mode = data.get('mode', 'Auto')
    if mode in camera.AWB_MODES:
        camera.AWB_MODE = mode
        camera.picam2.set_controls({"AwbMode": camera.AWB_MODES[mode]})
        print(f"AWB: {mode}")
    return jsonify({'status': 'ok', 'awb': camera.AWB_MODE})


@app.route('/set_preview', methods=['POST'])
def set_preview():
    data = request.get_json()
    camera.preview_while_recording = bool(data.get('enabled', False))
    print(f"Live Preview while Recording: {'an' if camera.preview_while_recording else 'aus'}")
    return jsonify({'status': 'ok', 'preview_while_recording': camera.preview_while_recording})


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
    data = request.get_json()
    if 'enabled' in data:
        camera.focus_peaking = bool(data['enabled'])
    if 'threshold' in data:
        camera.PEAKING_THRESHOLD = int(data['threshold'])
    return jsonify({'status': 'ok',
                    'focus_peaking': camera.focus_peaking,
                    'peaking_threshold': camera.PEAKING_THRESHOLD})


# Captive portal
@app.route('/hotspot-detect.html')
@app.route('/generate_204')
@app.route('/connectivity-check.html')
@app.route('/ncsi.txt')
def captive_portal():
    return redirect('http://10.42.0.1/', 302)