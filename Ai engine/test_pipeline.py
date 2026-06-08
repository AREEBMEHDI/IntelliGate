"""
IntelliGate — Full Pipeline Test
Runs on MacBook M1 using built-in camera (or any webcam).

Tests:
  1. YOLOv8  → detects vehicles + people in frame
  2. PaddleOCR → reads any text / license plate region
  3. InsightFace → detects faces, draws bounding boxes

Controls:
  Q  → quit
  S  → save current frame as screenshot
  F  → toggle face detection on/off
  P  → toggle plate OCR on/off
  V  → toggle vehicle detection on/off
"""

import cv2
import numpy as np
import time
import os
from datetime import datetime
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich import print as rprint

console = Console()

# ─── Load models ─────────────────────────────────────────────

def load_yolo():
    console.print("[bold cyan]Loading YOLOv8...[/bold cyan]")
    from ultralytics import YOLO
    model = YOLO("yolov8n.pt")  # auto-downloads on first run (~6MB)
    console.print("[bold green]✓ YOLOv8 ready[/bold green]")
    return model


def load_ocr():
    console.print("[bold cyan]Loading PaddleOCR...[/bold cyan]")
    from paddleocr import PaddleOCR
    # use_gpu=False for M1 (MPS not supported by PaddleOCR yet)
    ocr = PaddleOCR(use_textline_orientation=True, lang="en")
    console.print("[bold green]✓ PaddleOCR ready[/bold green]")
    return ocr


def load_face():
    console.print("[bold cyan]Loading InsightFace...[/bold cyan]")
    from insightface.app import FaceAnalysis
    app = FaceAnalysis(
        name="buffalo_sc",   # smaller model — better for M1 CPU
        providers=["CPUExecutionProvider"],
    )
    app.prepare(ctx_id=-1, det_size=(640, 640))
    console.print("[bold green]✓ InsightFace ready[/bold green]")
    return app


# ─── Detection functions ──────────────────────────────────────

VEHICLE_CLASSES = {2: "Car", 3: "Motorcycle", 5: "Bus", 7: "Truck"}
PERSON_CLASS = 0

def detect_objects(model, frame):
    """Run YOLOv8 — returns list of (label, confidence, x1,y1,x2,y2)."""
    results = model(frame, conf=0.45, verbose=False)[0]
    detections = []
    for box in results.boxes:
        cls_id = int(box.cls[0])
        conf = float(box.conf[0])
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        if cls_id in VEHICLE_CLASSES:
            detections.append(("vehicle", VEHICLE_CLASSES[cls_id], conf, x1, y1, x2, y2))
        elif cls_id == PERSON_CLASS:
            detections.append(("person", "Person", conf, x1, y1, x2, y2))
    return detections


def run_ocr(ocr_model, frame, x1, y1, x2, y2):
    """Run OCR on a cropped region. Returns list of (text, confidence)."""
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return []
    # Upscale small regions for better OCR
    h, w = crop.shape[:2]
    if w < 150:
        scale = 150 / w
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    # Preprocess
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    crop_ready = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)

    try:
        result = ocr_model.ocr(crop_ready, cls=True)
        if not result or not result[0]:
            return []
        texts = []
        for line in result[0]:
            text, conf = line[1]
            clean = "".join(c for c in text.upper() if c.isalnum())
            if len(clean) >= 3:
                texts.append((clean, conf))
        return texts
    except Exception:
        return []


def detect_faces(face_app, frame):
    """Run InsightFace — returns list of (name, confidence, x1,y1,x2,y2)."""
    try:
        faces = face_app.get(frame)
        result = []
        for face in faces:
            if face.det_score < 0.5:
                continue
            x1, y1, x2, y2 = map(int, face.bbox)
            result.append(("Face", float(face.det_score), x1, y1, x2, y2))
        return result
    except Exception:
        return []


# ─── Drawing helpers ──────────────────────────────────────────

def draw_box(frame, label, conf, x1, y1, x2, y2, color):
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    text = f"{label} {conf:.0%}"
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 6, y1), color, -1)
    cv2.putText(frame, text, (x1 + 3, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)


def draw_ocr_result(frame, texts, x1, y2):
    for i, (text, conf) in enumerate(texts[:2]):  # show max 2 lines
        label = f"PLATE: {text} ({conf:.0%})"
        cv2.putText(frame, label, (x1, y2 + 20 + i * 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)


def draw_overlay(frame, fps, flags, counts):
    h, w = frame.shape[:2]
    # FPS
    cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    # Mode flags
    modes = []
    if flags["vehicle"]: modes.append("VEHICLE")
    if flags["face"]:    modes.append("FACE")
    if flags["plate"]:   modes.append("PLATE-OCR")
    mode_str = " | ".join(modes) if modes else "ALL OFF"
    cv2.putText(frame, mode_str, (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 1)
    # Counts
    cv2.putText(frame, f"Vehicles: {counts['vehicle']}  Faces: {counts['face']}",
                (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    # Controls hint
    cv2.putText(frame, "Q:Quit  S:Save  F:Face  P:Plate  V:Vehicle",
                (10, h - 45), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)


# ─── Main loop ────────────────────────────────────────────────

def main():
    console.rule("[bold]IntelliGate — Pipeline Test[/bold]")
    console.print("Starting models... this takes ~30 seconds on first run\n")

    # Load all models
    yolo = load_yolo()
    ocr  = load_ocr()
    face = load_face()

    console.print("\n[bold green]All models loaded! Opening camera...[/bold green]\n")
    console.print("Controls: [bold]Q[/bold]=Quit  [bold]S[/bold]=Save frame  "
                  "[bold]F[/bold]=Face  [bold]P[/bold]=Plate OCR  [bold]V[/bold]=Vehicle\n")

    # Open MacBook camera (index 0 = built-in FaceTime camera)
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    if not cap.isOpened():
        console.print("[bold red]ERROR: Cannot open camera. Check System Preferences → Privacy → Camera[/bold red]")
        return

    # Feature flags
    flags = {"vehicle": True, "face": True, "plate": True}

    # Stats
    frame_times = []
    total_detections = {"vehicle": 0, "face": 0, "plate": 0}
    session_log = []

    os.makedirs("captures", exist_ok=True)

    console.print("[bold green]Camera open. Pipeline running![/bold green]")

    # OCR runs every N frames (it's slow)
    ocr_interval = 10
    frame_count = 0
    last_ocr_texts = {}   # vehicle_box_key → texts

    while True:
        t_start = time.time()
        ret, frame = cap.read()
        if not ret:
            console.print("[red]Camera read failed[/red]")
            break

        frame_count += 1
        display = frame.copy()
        counts = {"vehicle": 0, "face": 0}

        # ── Vehicle + Person detection (YOLOv8) ──────────────
        vehicle_boxes = []
        if flags["vehicle"]:
            objects = detect_objects(yolo, frame)
            for obj_type, label, conf, x1, y1, x2, y2 in objects:
                if obj_type == "vehicle":
                    color = (0, 200, 255)   # orange
                    draw_box(display, label, conf, x1, y1, x2, y2, color)
                    counts["vehicle"] += 1
                    vehicle_boxes.append((x1, y1, x2, y2))

                    # ── Plate OCR (every N frames per vehicle) ──
                    if flags["plate"]:
                        box_key = f"{x1//50}_{y1//50}"
                        if frame_count % ocr_interval == 0:
                            # Crop bottom 35% of vehicle = plate zone
                            ph = y2 - y1
                            py1 = y1 + int(ph * 0.62)
                            texts = run_ocr(ocr_model=ocr,
                                           frame=frame,
                                           x1=x1, y1=py1,
                                           x2=x2, y2=y2)
                            last_ocr_texts[box_key] = texts
                            if texts:
                                total_detections["plate"] += 1
                                for text, conf_t in texts:
                                    session_log.append({
                                        "type": "PLATE",
                                        "value": text,
                                        "confidence": f"{conf_t:.0%}",
                                        "time": datetime.now().strftime("%H:%M:%S"),
                                    })
                                    console.print(
                                        f"[bold yellow]🚗 PLATE DETECTED:[/bold yellow] "
                                        f"[cyan]{text}[/cyan] ({conf_t:.0%})"
                                    )

                        # Draw last known OCR result
                        box_key = f"{x1//50}_{y1//50}"
                        if box_key in last_ocr_texts:
                            draw_ocr_result(display, last_ocr_texts[box_key], x1, y2)

                elif obj_type == "person":
                    draw_box(display, "Person", conf, x1, y1, x2, y2, (200, 200, 200))

        # ── Face detection (InsightFace) ──────────────────────
        if flags["face"] and frame_count % 2 == 0:  # every 2nd frame
            faces = detect_faces(face, frame)
            for label, conf, x1, y1, x2, y2 in faces:
                color = (0, 255, 120)   # green
                draw_box(display, f"Face", conf, x1, y1, x2, y2, color)
                counts["face"] += 1

                if conf > 0.85:
                    total_detections["face"] += 1
                    # Draw landmark dots if available
                    cv2.circle(display, (x1 + (x2-x1)//2, y1 + (y2-y1)//3),
                               3, (0, 255, 0), -1)

        # ── FPS + overlay ─────────────────────────────────────
        t_end = time.time()
        fps = 1.0 / (t_end - t_start + 1e-9)
        draw_overlay(display, fps, flags, counts)

        cv2.imshow("IntelliGate — Pipeline Test", display)

        # ── Key handling ──────────────────────────────────────
        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break
        elif key == ord("s"):
            fname = f"captures/capture_{datetime.now().strftime('%H%M%S')}.jpg"
            cv2.imwrite(fname, display)
            console.print(f"[green]Saved → {fname}[/green]")
        elif key == ord("f"):
            flags["face"] = not flags["face"]
            console.print(f"Face detection: [{'green' if flags['face'] else 'red'}]{'ON' if flags['face'] else 'OFF'}[/]")
        elif key == ord("p"):
            flags["plate"] = not flags["plate"]
            console.print(f"Plate OCR: [{'green' if flags['plate'] else 'red'}]{'ON' if flags['plate'] else 'OFF'}[/]")
        elif key == ord("v"):
            flags["vehicle"] = not flags["vehicle"]
            console.print(f"Vehicle detection: [{'green' if flags['vehicle'] else 'red'}]{'ON' if flags['vehicle'] else 'OFF'}[/]")

    cap.release()
    cv2.destroyAllWindows()

    # ── Session summary ───────────────────────────────────────
    console.rule("[bold]Session Summary[/bold]")
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Type")
    table.add_column("Count")
    table.add_row("Vehicles detected", str(total_detections["vehicle"] or counts.get("vehicle", 0)))
    table.add_row("Faces detected",    str(total_detections["face"]))
    table.add_row("Plates read",       str(total_detections["plate"]))
    console.print(table)

    if session_log:
        console.rule("[bold]Detections Log[/bold]")
        log_table = Table(show_header=True, header_style="bold yellow")
        log_table.add_column("Time")
        log_table.add_column("Type")
        log_table.add_column("Value")
        log_table.add_column("Confidence")
        for entry in session_log[-20:]:  # last 20
            log_table.add_row(
                entry["time"], entry["type"], entry["value"], entry["confidence"]
            )
        console.print(log_table)


if __name__ == "__main__":
    main()
