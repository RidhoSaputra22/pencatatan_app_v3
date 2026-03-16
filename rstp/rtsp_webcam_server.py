import cv2
from flask import Flask, Response

app = Flask(__name__)

video_path = "cctv-footage-1.mp4"
cap = cv2.VideoCapture(video_path)

def generate_frames():
    global cap

    while True:
        ret, frame = cap.read()

        # jika video selesai, ulang dari awal
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        ret, buffer = cv2.imencode(".jpg", frame)
        frame_bytes = buffer.tobytes()

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )

@app.route("/")
def index():
    return "Video Stream Server Running"

@app.route("/video")
def video():
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7000, debug=True)