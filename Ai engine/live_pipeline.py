"""
IntelliGate — Full Integrated Pipeline with MJPEG Stream
Detects faces + plates from camera, sends to backend, shows decision on screen.
Also streams processed video to dashboard via MJPEG on http://localhost:5001/video_feed

Controls:
  Q → quit
  S → save screenshot
  F → toggle face detection
  P → toggle plate OCR

Configuration:
  Copy config.env.example → config.env and fill in your values.
  Never commit config.env — it contains your facility API key.
"""

import os
import cv2
import numpy as np
import httpx
import threading
import time
from datetime import datetime
from flask import Flask, Response
from loguru import logger
from rich.console import Console
from dotenv import load_dotenv

load_dotenv("config.env")

console = Console()

# ─── Config ──────────────────────────────────────────────────
CLOUD_API_URL    = os.getenv("CLOUD_API_URL", "http://localhost:8000")
FACILITY_API_KEY = os.getenv("FACILITY_API_KEY", "")
GATE_ID          = os.getenv("GATE_ID", "")
HEADERS          = {"X-API-Key": FACILITY_API_KEY}
STREAM_PORT      = int(os.getenv("STREAM_PORT", "5001"))

if not FACILITY_API_KEY or not GATE_ID:
    raise SystemExit(
        "ERROR: FACILITY_API_KEY and GATE_ID must be set in config.env\n"
        "Copy config.env.example → config.env and fill in your values."
    )

# ─── Flask MJPEG server ───────────────────────────────────────
app = Flask(__name__)
output_frame = None
frame_lock = threading.Lock()


def generate_stream():
    global output_frame
    while True:
        with frame_lock:
            if output_frame is None:
                time.sleep(0.05)
                continue
            ret, buffer = cv2.imencode('.jpg', output_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ret:
                continue
            frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.033)  # ~30fps


@app.route('/video_feed')
def video_feed():
    return Response(
        generate_stream(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


@app.route('/health')
def health():
    return {'status': 'streaming', 'port': STREAM_PORT}


def start_stream_server():
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host='0.0.0.0', port=STREAM_PORT, threaded=True, use_reloader=False)


# ─── Decision colors ─────────────────────────────────────────
COLORS = {
    "allowed":            (0, 220, 80),
    "allowed_with_alert": (0, 200, 255),
    "denied":             (0, 0, 220),
    "scanning":           (200, 200, 200),
}

ICONS = {
    "allowed":            "ALLOW",
    "allowed_with_alert": "ALERT",
    "denied":             "DENY",
    "scanning":           "...",
}


# ─── Load models ─────────────────────────────────────────────
def load_models():
    console.print("[bold cyan]Loading YOLOv8...[/bold cyan]")
    from ultralytics import YOLO
    yolo = YOLO("yolov8n.pt")
    console.print("[green]✓ YOLOv8[/green]")

    console.print("[bold cyan]Loading PaddleOCR...[/bold cyan]")
    from paddleocr import PaddleOCR
    ocr = PaddleOCR(use_textline_orientation=True, lang="en")
    console.print("[green]✓ PaddleOCR[/green]")

    console.print("[bold cyan]Loading InsightFace...[/bold cyan]")
    from insightface.app import FaceAnalysis
    face_app = FaceAnalysis(name="buffalo_sc", providers=["CPUExecutionProvider"])
    face_app.prepare(ctx_id=-1, det_size=(640, 640))
    console.print("[green]✓ InsightFace[/green]")

    return yolo, ocr, face_app


# ─── Backend call ─────────────────────────────────────────────
def send_to_backend(plate_number, plate_conf, persons):
    try:
        payload = {
            "gate_id": GATE_ID,
            "plate_number": plate_number,
            "plate_confidence": plate_conf,
            "persons": persons,
            "edge_timestamp": datetime.utcnow().isoformat(),
        }
        resp = httpx.post(
            f"{CLOUD_API_URL}/api/scan/",
            json=payload,
            headers=HEADERS,
            timeout=5.0,
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        logger.error(f"Backend unreachable: {e}")
        return None


# ─── Drawing helpers ──────────────────────────────────────────
def draw_decision_banner(frame, decision_data):
    if not decision_data:
        return
    decision = decision_data.get("decision", "scanning")
    driver   = decision_data.get("driver_name") or "Unknown"
    plate    = decision_data.get("plate", "") or ""
    reason   = decision_data.get("decision_reason", "")
    color    = COLORS.get(decision, (200, 200, 200))
    icon     = ICONS.get(decision, "...")
    h, w     = frame.shape[:2]

    cv2.rectangle(frame, (0, 0), (w, 80), color, -1)
    cv2.rectangle(frame, (0, 0), (w, 80), (255, 255, 255), 2)
    cv2.putText(frame, icon, (15, 52), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (255, 255, 255), 3)
    info = f"{driver}"
    if plate:
        info += f"  |  {plate}"
    cv2.putText(frame, info, (120, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(frame, reason[:70], (120, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)


def draw_face_box(frame, x1, y1, x2, y2, conf, decision=None):
    color = COLORS.get(decision, (0, 255, 120))
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    cv2.putText(frame, f"Face {conf:.0%}", (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)


def draw_status_bar(frame, fps, cloud_ok, last_scan_time):
    h, w = frame.shape[:2]
    cv2.rectangle(frame, (0, h - 35), (w, h), (30, 30, 30), -1)
    cv2.putText(frame, f"FPS:{fps:.0f}", (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
    cloud_color = (0, 220, 80) if cloud_ok else (0, 0, 220)
    cloud_text  = "BACKEND OK" if cloud_ok else "BACKEND OFFLINE"
    cv2.putText(frame, cloud_text, (90, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.5, cloud_color, 1)

    # Stream indicator
    cv2.putText(frame, f"STREAM: localhost:{STREAM_PORT}/video_feed",
                (w - 320, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 200, 255), 1)

    if last_scan_time:
        elapsed = int(time.time() - last_scan_time)
        cv2.putText(frame, f"Last scan: {elapsed}s ago", (w - 320, h - 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1)

    cv2.putText(frame, "Q:Quit  S:Save  F:Face  P:Plate",
                (10, h - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)


# ─── Main pipeline ────────────────────────────────────────────
def main():
    global output_frame

    console.rule("[bold]IntelliGate — Live Pipeline + Stream[/bold]")

    # Start MJPEG stream server in background
    stream_thread = threading.Thread(target=start_stream_server, daemon=True)
    stream_thread.start()
    console.print(f"[bold green]MJPEG stream started → http://localhost:{STREAM_PORT}/video_feed[/bold green]")

    yolo, ocr, face_app = load_models()
    console.print("\n[bold green]All models ready! Opening camera...[/bold green]\n")

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    if not cap.isOpened():
        console.print("[red]Cannot open camera![/red]")
        return

    flags           = {"face": True, "plate": True}
    current_decision = {}
    decision_timeout = 0
    last_scan_time  = None
    cloud_ok        = True
    frame_count     = 0
    scanning        = False

    import os
    os.makedirs("captures", exist_ok=True)

    VEHICLE_CLASSES = {2: "Car", 3: "Motorcycle", 5: "Bus", 7: "Truck"}

    console.print(f"[bold green]Camera open![/bold green]")
    console.print(f"[cyan]Dashboard stream: http://localhost:{STREAM_PORT}/video_feed[/cyan]")
    console.print("[dim]Press Q to quit[/dim]")

    while True:
        t0 = time.time()
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        display = frame.copy()

        # ── Every 15 frames: full AI pipeline ─────────────
        if frame_count % 15 == 0 and not scanning:
            plate_text = None
            plate_conf = 0.0
            persons    = []
            vehicle_box = None

            results = yolo(frame, conf=0.45, verbose=False)[0]
            for box in results.boxes:
                cls_id = int(box.cls[0])
                if cls_id in VEHICLE_CLASSES:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    vehicle_box = (x1, y1, x2, y2)
                    cv2.rectangle(display, (x1, y1), (x2, y2), (0, 200, 255), 2)
                    cv2.putText(display, VEHICLE_CLASSES[cls_id], (x1, y1 - 8),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)

                    h_v = y2 - y1
                    py1 = y1 + int(h_v * 0.62)
                    plate_crop = frame[py1:y2, x1:x2]
                    if plate_crop.size > 0:
                        try:
                            gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
                            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                            ready = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
                            ocr_result = ocr.ocr(ready, cls=True)
                            if ocr_result and ocr_result[0]:
                                for line in ocr_result[0]:
                                    txt, cf = line[1]
                                    clean = "".join(c for c in txt.upper() if c.isalnum())
                                    if len(clean) >= 3 and cf > plate_conf:
                                        plate_text = clean
                                        plate_conf = cf
                        except Exception:
                            pass

            if flags["face"]:
                try:
                    faces = face_app.get(frame)
                    for face in faces:
                        if face.det_score < 0.5:
                            continue
                        fx1, fy1, fx2, fy2 = map(int, face.bbox)
                        persons.append({
                            "face_embedding": face.normed_embedding.tolist(),
                            "face_confidence": float(face.det_score),
                        })
                        draw_face_box(display, fx1, fy1, fx2, fy2,
                                      float(face.det_score),
                                      current_decision.get("decision"))
                except Exception:
                    pass

            if (plate_text or persons) and not scanning:
                scanning = True

                def scan_thread():
                    nonlocal current_decision, decision_timeout, last_scan_time, cloud_ok, scanning
                    result = send_to_backend(plate_text, plate_conf, persons)
                    if result:
                        result["plate"] = plate_text
                        current_decision = result
                        decision_timeout = time.time() + 5
                        last_scan_time   = time.time()
                        cloud_ok         = True
                        decision = result.get("decision", "")
                        driver   = result.get("driver_name") or "Unknown"
                        console.print(
                            f"[{'green' if decision == 'allowed' else 'red' if decision == 'denied' else 'yellow'}]"
                            f"{ICONS.get(decision, '?')} {driver} | {plate_text or 'No plate'}"
                            f"[/]"
                        )
                    else:
                        cloud_ok = False
                    scanning = False

                threading.Thread(target=scan_thread, daemon=True).start()

        # ── Draw decision banner ──────────────────────────
        if current_decision and time.time() < decision_timeout:
            draw_decision_banner(display, current_decision)
        elif time.time() >= decision_timeout:
            current_decision = {}

        # ── Status bar ────────────────────────────────────
        fps = 1.0 / (time.time() - t0 + 1e-9)
        draw_status_bar(display, fps, cloud_ok, last_scan_time)

        # ── Update stream frame ───────────────────────────
        with frame_lock:
            output_frame = display.copy()

        # ── Show local window ─────────────────────────────
        cv2.imshow("IntelliGate — Live", display)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("s"):
            fname = f"captures/capture_{datetime.now().strftime('%H%M%S')}.jpg"
            cv2.imwrite(fname, display)
            console.print(f"[green]Saved → {fname}[/green]")
        elif key == ord("f"):
            flags["face"] = not flags["face"]
        elif key == ord("p"):
            flags["plate"] = not flags["plate"]

    cap.release()
    cv2.destroyAllWindows()
    console.print("\n[bold]Pipeline stopped.[/bold]")


if __name__ == "__main__":
    main()