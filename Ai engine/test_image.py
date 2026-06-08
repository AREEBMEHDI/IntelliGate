"""
Static Image Test — no camera needed
Drop any car image in this folder and run:
  python3 test_image.py your_car.jpg

Tests the full pipeline on a single image.
"""

import sys
import cv2
import numpy as np
from rich.console import Console
from rich.panel import Panel

console = Console()


def test_image(image_path: str):
    console.rule("[bold]IntelliGate — Image Test[/bold]")

    # Load image
    frame = cv2.imread(image_path)
    if frame is None:
        console.print(f"[red]Cannot load image: {image_path}[/red]")
        return
    console.print(f"Image loaded: [cyan]{image_path}[/cyan] ({frame.shape[1]}x{frame.shape[0]})")

    display = frame.copy()

    # ── YOLOv8 ───────────────────────────────────────────────
    console.print("\n[bold cyan]Running YOLOv8 vehicle detection...[/bold cyan]")
    from ultralytics import YOLO
    model = YOLO("yolov8n.pt")
    results = model(frame, conf=0.4, verbose=False)[0]

    VEHICLE_CLASSES = {2: "Car", 3: "Motorcycle", 5: "Bus", 7: "Truck"}
    vehicle_boxes = []

    for box in results.boxes:
        cls_id = int(box.cls[0])
        conf = float(box.conf[0])
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        if cls_id in VEHICLE_CLASSES:
            label = VEHICLE_CLASSES[cls_id]
            console.print(f"  ✓ [green]{label}[/green] detected ({conf:.0%}) at [{x1},{y1},{x2},{y2}]")
            cv2.rectangle(display, (x1, y1), (x2, y2), (0, 200, 255), 2)
            cv2.putText(display, f"{label} {conf:.0%}", (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)
            vehicle_boxes.append((x1, y1, x2, y2))

    if not vehicle_boxes:
        console.print("  [yellow]No vehicles detected[/yellow]")

    # ── PaddleOCR on plate region ─────────────────────────────
    console.print("\n[bold cyan]Running PaddleOCR on plate region...[/bold cyan]")
    from paddleocr import PaddleOCR
    ocr = PaddleOCR(use_angle_cls=True, lang="en", use_gpu=False, show_log=False)

    for x1, y1, x2, y2 in vehicle_boxes:
        h = y2 - y1
        py1 = y1 + int(h * 0.62)
        plate_crop = frame[py1:y2, x1:x2]

        if plate_crop.size == 0:
            continue

        # Upscale + preprocess
        pw = plate_crop.shape[1]
        if pw < 150:
            scale = 150 / pw
            plate_crop = cv2.resize(plate_crop, None, fx=scale, fy=scale)

        gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        plate_ready = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)

        result = ocr.ocr(plate_ready, cls=True)
        if result and result[0]:
            for line in result[0]:
                text, conf = line[1]
                clean = "".join(c for c in text.upper() if c.isalnum())
                if len(clean) >= 3:
                    console.print(f"  ✓ [yellow]PLATE:[/yellow] [bold cyan]{clean}[/bold cyan] ({conf:.0%})")
                    cv2.putText(display, f"PLATE: {clean}", (x1, y2 + 25),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        else:
            console.print("  [yellow]No plate text detected in this region[/yellow]")

    # ── InsightFace ───────────────────────────────────────────
    console.print("\n[bold cyan]Running InsightFace face detection...[/bold cyan]")
    from insightface.app import FaceAnalysis
    face_app = FaceAnalysis(name="buffalo_sc", providers=["CPUExecutionProvider"])
    face_app.prepare(ctx_id=-1, det_size=(640, 640))

    faces = face_app.get(frame)
    if faces:
        for face in faces:
            if face.det_score < 0.5:
                continue
            x1, y1, x2, y2 = map(int, face.bbox)
            conf = float(face.det_score)
            console.print(f"  ✓ [green]Face[/green] detected ({conf:.0%}) at [{x1},{y1},{x2},{y2}]")
            cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 120), 2)
            cv2.putText(display, f"Face {conf:.0%}", (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 120), 2)
    else:
        console.print("  [yellow]No faces detected[/yellow]")

    # ── Save result ───────────────────────────────────────────
    out_path = image_path.replace(".", "_result.")
    cv2.imwrite(out_path, display)
    console.print(f"\n[bold green]Result saved → {out_path}[/bold green]")

    # Show result
    cv2.imshow("IntelliGate — Image Test", display)
    console.print("[dim]Press any key in the image window to close[/dim]")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        console.print(Panel(
            "Usage: [bold]python3 test_image.py your_car_photo.jpg[/bold]\n\n"
            "Drop any car/face image in this folder and pass its filename.\n"
            "The script will run the full pipeline and save the result.",
            title="IntelliGate — Image Test",
        ))
    else:
        test_image(sys.argv[1])
