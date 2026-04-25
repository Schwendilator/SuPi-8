import time
import os
import threading
import traceback
import subprocess
import numpy as np
from datetime import datetime
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FileOutput
from libcamera import Transform, controls

# Settings
FPS                  = 18
RES_MAIN             = (1600, 1200)
ROI_NORM             = (0.2, 0.0, 0.75, 1.0)
ROTATE_180           = True
BITRATE              = 10_000_000
OUTPUT_PATH          = "/mnt/recordings"
BRIGHTNESS_THRESHOLD = 50
CHECK_EVERY_S        = 0.1
DEBUG_PRINT_EVERY    = 10
LORES_SIZE           = (640, 480)
NUM_SAMPLES          = 3
AWB_MODE             = "Auto"
PEAKING_THRESHOLD    = 75
FOCUS_MAX            = 4500
GAIN_TOO_HIGH        = 10.0
GAIN_TOO_LOW         = 1.1

AWB_MODES = {
    "Tungsten":    controls.AwbModeEnum.Tungsten,
    "Indoor":      controls.AwbModeEnum.Indoor,
    "Fluorescent": controls.AwbModeEnum.Fluorescent,
    "Daylight":    controls.AwbModeEnum.Daylight,
    "Cloudy":      controls.AwbModeEnum.Cloudy,
    "Auto":        controls.AwbModeEnum.Auto,
}

# States
preview_while_recording = False
stream_active = False
focus_peaking = False
camera_status = {"avg": 0.0, "focus": 0.0, "gain": 0.0, "temp": 0, "recording": False}

if not os.path.exists(OUTPUT_PATH):
    os.makedirs(OUTPUT_PATH)

picam2 = Picamera2()


# Helpers
def average_brightness_y_plane_yuv420(frame_yuv, lores_size):
    w, h = lores_size
    y_plane = frame_yuv[:h, :w]
    return float(np.mean(y_plane))


def mux_and_remove_raw(raw_file, mp4_file, fps):
    cmd = ["ffmpeg", "-y", "-r", str(fps), "-i", raw_file, "-c", "copy", mp4_file]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.remove(raw_file)
        print(f"Muxing done: {mp4_file}")
    except Exception as e:
        print(f"Error muxing {raw_file}: {e}")


# Camera worker
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
        "Saturation": 1.2,
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
                    print("Recording stopped, muxing in background...")
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
                    mp4_filename = filename.replace(".h264", ".mp4")
                    threading.Thread(
                        target=mux_and_remove_raw,
                        args=(filename, mp4_filename, FPS),
                        daemon=True
                    ).start()
                    print("Recording stopped (preview)")

            loop_count += 1
            time.sleep(CHECK_EVERY_S)
    except Exception:
        traceback.print_exc()


def start():
    t = threading.Thread(target=camera_worker, daemon=True)
    t.start()