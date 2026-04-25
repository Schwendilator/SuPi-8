import time
import threading
from rpi_ws281x import PixelStrip, Color

# Hardware config
LED_COUNT      = 2
LED_PIN        = 10
LED_FREQ_HZ    = 800000
LED_DMA        = 10
LED_BRIGHTNESS = 40
LED_INVERT     = False
LED_CHANNEL    = 0

RECLED = 0   # recording status
STATLED  = 1   # focus / exposure status

OFF   = Color(0,   0,   0  )
GREEN = Color(0,   80,  0  )
RED   = Color(80,  0,   0  )
BLUE  = Color(0,   0,   80 )
WHITE = Color(80,  80,  80 )

BLINK_INTERVAL = 1


class LEDController:
    def __init__(self):
        self.strip = PixelStrip(
            LED_COUNT, LED_PIN, LED_FREQ_HZ,
            LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL
        )
        self.strip.begin()
        self._running = True
        self._phase = False   # toggles every BLINK_INTERVAL
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._running = False
        self.strip.setPixelColor(RECLED, OFF)
        self.strip.setPixelColor(STATLED, OFF)
        self.strip.show()

    def _set(self, index, colour):
        self.strip.setPixelColor(index, colour)

    def _loop(self):
        import camera 

        while self._running:
            self._phase = not self._phase
            status  = camera.camera_status
            active  = status.get("recording") or camera.stream_active

            # LED 0: Recording status 
            if status.get("recording"):
                self._set(RECLED, RED if self._phase else OFF)
            else:
                self._set(RECLED, GREEN)

            # LED 1: Focus + Exposure
            # Only show warnings when recording or previewing
            if not active:
                self._set(STATLED, OFF)
            else:
                focus     = status.get("focus", 0)
                gain      = status.get("gain", 0)

                in_focus   = focus >= (camera.FOCUS_MAX * 0.8)
                too_dark   = gain  >= camera.GAIN_TOO_HIGH
                too_bright = gain  <= camera.GAIN_TOO_LOW

                if in_focus and not too_dark and not too_bright:
                    self._set(STATLED, GREEN)

                elif not in_focus and too_dark:
                    self._set(STATLED, RED if self._phase else BLUE)

                elif not in_focus and too_bright:
                    self._set(STATLED, RED if self._phase else WHITE)

                elif too_dark:
                    self._set(STATLED, BLUE if self._phase else OFF)

                elif too_bright:
                    self._set(STATLED, WHITE if self._phase else OFF)

                else:
                    self._set(STATLED, RED if self._phase else OFF)

            self.strip.show()
            time.sleep(BLINK_INTERVAL)


_controller = None


def start():
    global _controller
    _controller = LEDController()
    _controller.start()


def stop():
    if _controller:
        _controller.stop()