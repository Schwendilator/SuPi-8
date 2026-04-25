import camera
import web
import led


if __name__ == "__main__":
    camera.start()
    led.start()
    web.app.run(host='0.0.0.0', port=5091, threaded=True)