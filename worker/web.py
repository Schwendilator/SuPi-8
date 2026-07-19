# SPDX-License-Identifier: GPL-3.0-only
import os
import cv2
import time
import threading
import subprocess
from flask import Flask, render_template, send_from_directory, Response, request, jsonify, redirect

import camera

# Flask Setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_HOME = os.path.dirname(BASE_DIR)

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "../templates")
)


# Preview stream
def gen_frames():
    camera.stream_active = True
    try:
        while True:
            with camera.camera_lock:
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
    data = request.get_json(silent=True) or {}

    try:
        if 'fps' in data:
            fps = int(data['fps'])
            if not (1 <= fps <= 60):
                return jsonify({'status': 'error', 'message': 'fps must be between 1 and 60'}), 400
        if 'threshold' in data:
            threshold = float(data['threshold'])
            if not (0 <= threshold <= 255):
                return jsonify({'status': 'error', 'message': 'threshold must be between 0 and 255'}), 400
        if 'bitrate' in data:
            bitrate = int(data['bitrate'])
            if not (1 <= bitrate <= 50):
                return jsonify({'status': 'error', 'message': 'bitrate must be between 1 and 50'}), 400
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'message': 'Invalid config values'}), 400

    if 'threshold' in data:
        camera.BRIGHTNESS_THRESHOLD = threshold
    if 'fps' in data:
        camera.set_fps(fps)
    if 'bitrate' in data:
        camera.BITRATE = bitrate * 1_000_000
    camera.save_config()
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
        'roi_x_offset': camera.ROI_X_OFFSET,
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
    camera.save_config()
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
    camera.save_config()
    return jsonify({'status': 'ok',
                    'focus_peaking': camera.focus_peaking,
                    'peaking_threshold': camera.PEAKING_THRESHOLD})


@app.route('/set_roi', methods=['POST'])
def set_roi():
    data = request.get_json()
    x = float(data.get('x_offset', camera.ROI_X_OFFSET))
    x = max(0.0, min(1.0, x))
    camera.set_roi(x)
    camera.save_config()
    return jsonify({'status': 'ok', 'roi_x_offset': camera.ROI_X_OFFSET})


@app.route('/reset_config', methods=['POST'])
def reset_config():
    camera.reset_config()
    return jsonify({'status': 'ok', 'message': 'Config reset to defaults'})


@app.route('/update', methods=['POST'])
def update():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file uploaded'}), 400
    file = request.files['file']
    if file.filename == '' or not file.filename.endswith('.tar.gz'):
        return jsonify({'status': 'error', 'message': 'File must be a .tar.gz archive'}), 400

    tmp_path = '/tmp/supi-update.tar.gz'
    file.save(tmp_path)

    def _apply():
        time.sleep(0.5)
        subprocess.run(['sudo', '/usr/local/bin/apply-update.sh', tmp_path])
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    threading.Thread(target=_apply, daemon=True).start()
    return jsonify({'status': 'ok', 'message': 'Update applied, restarting...'})


@app.route('/setup')
def setup():
    return render_template('setup.html')


@app.route('/setup/connect_wifi', methods=['POST'])
def setup_connect_wifi():
    data = request.get_json()
    ssid = data.get('ssid', '').strip()
    password = data.get('password', '')
    if not ssid:
        return jsonify({'status': 'error', 'message': 'SSID required'}), 400
    try:
        subprocess.run(['sudo', 'nmcli', 'device', 'wifi', 'connect', ssid, 'password', password],
                       check=True, capture_output=True, text=True)
        subprocess.run(['sudo', 'nmcli', 'connection', 'modify', ssid,
                        'connection.autoconnect', 'yes'], check=False)
        return jsonify({'status': 'ok',
                        'message': f'Connected to {ssid}. The device will be available on your network shortly.'})
    except subprocess.CalledProcessError as e:
        msg = e.stderr.strip() if e.stderr else 'Connection failed'
        return jsonify({'status': 'error', 'message': msg}), 500


@app.route('/setup/network_status')
def setup_network_status():
    try:
        active_out = subprocess.run(
            ['sudo', 'nmcli', '-t', '-f', 'NAME,DEVICE', 'connection', 'show', '--active'],
            capture_output=True, text=True, check=True
        ).stdout.strip()
        active_name = None
        for line in active_out.split('\n'):
            parts = line.split(':')
            if len(parts) == 2 and parts[1] == 'wlan0':
                active_name = parts[0]
                break

        hotspot_ssid = subprocess.run(
            ['sudo', 'nmcli', '-g', '802-11-wireless.ssid', 'connection', 'show', 'supi-8-hotspot'],
            capture_output=True, text=True, check=True
        ).stdout.strip()

        if active_name == 'supi-8-hotspot':
            mode = 'ap'
        elif active_name:
            mode = 'client'
        else:
            mode = 'none'

        return jsonify({'status': 'ok', 'mode': mode, 'active_ssid': active_name, 'hotspot_ssid': hotspot_ssid})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/setup/set_mode', methods=['POST'])
def setup_set_mode():
    data = request.get_json(silent=True) or {}
    mode = data.get('mode')
    if mode not in ('ap', 'client'):
        return jsonify({'status': 'error', 'message': "mode must be 'ap' or 'client'"}), 400

    def _apply():
        time.sleep(1.5)
        try:
            listing = subprocess.run(
                ['sudo', 'nmcli', '-t', '-f', 'NAME,TYPE', 'connection', 'show'],
                capture_output=True, text=True, check=True
            ).stdout.strip()
            other_wifi = [
                line.split(':')[0] for line in listing.split('\n')
                if len(line.split(':')) == 2 and line.split(':')[1] == 'wifi'
                and line.split(':')[0] != 'supi-8-hotspot'
            ]

            if mode == 'ap':
                for name in other_wifi:
                    subprocess.run(['sudo', 'nmcli', 'connection', 'modify', name,
                                    'connection.autoconnect', 'no'], check=False)
                subprocess.run(['sudo', 'nmcli', 'connection', 'up', 'supi-8-hotspot'], check=False)
            else:
                for name in other_wifi:
                    subprocess.run(['sudo', 'nmcli', 'connection', 'modify', name,
                                    'connection.autoconnect', 'yes'], check=False)
                subprocess.run(['sudo', 'nmcli', 'connection', 'down', 'supi-8-hotspot'], check=False)
        except Exception as e:
            print(f"set_mode failed: {e}")

    threading.Thread(target=_apply, daemon=True).start()
    return jsonify({'status': 'ok', 'message': f'Switching to {"hotspot" if mode == "ap" else "Wi-Fi client"} mode...'})


@app.route('/setup/hotspot_settings', methods=['POST'])
def setup_hotspot_settings():
    data = request.get_json(silent=True) or {}
    ssid = data.get('ssid', '').strip()
    password = data.get('password', '')

    if not ssid:
        return jsonify({'status': 'error', 'message': 'SSID required'}), 400
    if len(password) < 8:
        return jsonify({'status': 'error', 'message': 'Password must be at least 8 characters'}), 400

    try:
        subprocess.run(['sudo', 'nmcli', 'connection', 'modify', 'supi-8-hotspot',
                        '802-11-wireless.ssid', ssid], check=True, capture_output=True, text=True)
        subprocess.run(['sudo', 'nmcli', 'connection', 'modify', 'supi-8-hotspot',
                        'wifi-sec.psk', password], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        msg = e.stderr.strip() if e.stderr else 'Failed to update hotspot settings'
        return jsonify({'status': 'error', 'message': msg}), 500

    def _reapply():
        time.sleep(1.5)
        active = subprocess.run(
            ['sudo', 'nmcli', '-t', '-f', 'NAME,DEVICE', 'connection', 'show', '--active'],
            capture_output=True, text=True
        ).stdout.strip()
        if any(line.startswith('supi-8-hotspot:') for line in active.split('\n')):
            subprocess.run(['sudo', 'nmcli', 'connection', 'down', 'supi-8-hotspot'], check=False)
            subprocess.run(['sudo', 'nmcli', 'connection', 'up', 'supi-8-hotspot'], check=False)

    threading.Thread(target=_reapply, daemon=True).start()
    return jsonify({'status': 'ok',
                    'message': f'Hotspot updated to "{ssid}". Reconnect with the new name/password if you were on the hotspot.'})


@app.route('/setup/factory_reset', methods=['POST'])
def setup_factory_reset():
    try:
        camera.reset_config()
        subprocess.run(['sudo', 'nmcli', 'connection', 'modify', 'supi-8-hotspot',
                        'wifi-sec.psk', 'Classic!'], check=True)
        for conn in subprocess.run(['sudo', 'nmcli', '-t', '-f', 'NAME,TYPE', 'connection', 'show'],
                                   capture_output=True, text=True, check=True).stdout.strip().split('\n'):
            parts = conn.split(':')
            if len(parts) == 2 and parts[1] == 'wifi' and parts[0] != 'supi-8-hotspot':
                subprocess.run(['sudo', 'nmcli', 'connection', 'delete', parts[0]], check=False)
        return jsonify({'status': 'ok', 'message': 'Factory reset complete. Hotspot password: Classic!'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/setup/backups')
def setup_backups():
    backups = []
    pattern = "backup-*.tar.gz"
    for f in sorted(os.listdir(APP_HOME), reverse=True):
        if f.startswith("backup-") and f.endswith(".tar.gz"):
            path = os.path.join(APP_HOME, f)
            size = os.path.getsize(path)
            backups.append({"name": f, "size": f"{size / 1024:.0f} KB"})
    return jsonify(backups)


@app.route('/setup/restore_backup', methods=['POST'])
def setup_restore_backup():
    data = request.get_json()
    name = data.get('name', '')
    if not name or '..' in name or '/' in name:
        return jsonify({'status': 'error', 'message': 'Invalid backup name'}), 400
    backup_path = os.path.join(APP_HOME, name)
    if not os.path.exists(backup_path):
        return jsonify({'status': 'error', 'message': 'Backup not found'}), 404
    try:
        import tarfile
        with tarfile.open(backup_path, 'r:gz') as tar:
            tar.extractall(path=APP_HOME)
        subprocess.run(['sudo', 'systemctl', 'restart', 'supi-8.service'], check=True)
        return jsonify({'status': 'ok', 'message': f'Restored {name}, restarting...'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# Captive portal
@app.route('/hotspot-detect.html')
@app.route('/generate_204')
@app.route('/connectivity-check.html')
@app.route('/ncsi.txt')
def captive_portal():
    return redirect('http://10.42.0.1/', 302)