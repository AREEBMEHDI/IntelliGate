#!/bin/bash
# Smart Access — M1 Mac Setup Script
# Run this once: bash install.sh

set -e
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Smart Access — M1 Mac Install          ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Check Python ─────────────────────────────────────────────
echo "→ Checking Python..."
if ! command -v python3 &>/dev/null; then
    echo "ERROR: Python3 not found. Install via: brew install python"
    exit 1
fi
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  Python $PYTHON_VERSION found"

# ── Create virtual environment ────────────────────────────────
echo ""
echo "→ Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate
echo "  venv activated"

# ── Upgrade pip ───────────────────────────────────────────────
echo ""
echo "→ Upgrading pip..."
pip install --upgrade pip --quiet

# ── Install packages ──────────────────────────────────────────
echo ""
echo "→ Installing OpenCV..."
pip install opencv-python==4.9.0.80 --quiet

echo "→ Installing NumPy + Pillow..."
pip install numpy==1.26.4 Pillow==10.3.0 --quiet

echo "→ Installing YOLOv8 (ultralytics)..."
pip install ultralytics==8.2.18 --quiet

echo "→ Installing PaddlePaddle for M1..."
# M1 needs the CPU version
pip install paddlepaddle==2.6.1 --quiet

echo "→ Installing PaddleOCR..."
pip install paddleocr==2.7.3 --quiet

echo "→ Installing InsightFace + ONNX Runtime (CPU for M1)..."
pip install insightface==0.7.3 onnxruntime==1.18.0 --quiet

echo "→ Installing logging + display libs..."
pip install loguru==0.7.2 rich==13.7.1 --quiet

# ── Download YOLOv8 model ─────────────────────────────────────
echo ""
echo "→ Pre-downloading YOLOv8 nano model..."
python3 -c "from ultralytics import YOLO; YOLO('yolov8n.pt')" 2>/dev/null
echo "  YOLOv8n.pt downloaded"

# ── Download InsightFace model ────────────────────────────────
echo ""
echo "→ Pre-downloading InsightFace buffalo_sc model..."
python3 -c "
from insightface.app import FaceAnalysis
app = FaceAnalysis(name='buffalo_sc', providers=['CPUExecutionProvider'])
app.prepare(ctx_id=-1, det_size=(320, 320))
print('  InsightFace model ready')
" 2>/dev/null || echo "  (will download on first run)"

# ── Camera permission reminder ────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  IMPORTANT: Camera Permission            ║"
echo "║                                          ║"
echo "║  When the script runs for the first      ║"
echo "║  time, macOS will ask for camera access. ║"
echo "║  Click ALLOW.                            ║"
echo "║                                          ║"
echo "║  If it doesn't appear, go to:            ║"
echo "║  System Settings → Privacy → Camera      ║"
echo "║  → Enable for Terminal                   ║"
echo "╚══════════════════════════════════════════╝"

echo ""
echo "✅ Installation complete!"
echo ""
echo "To run the test:"
echo "  source venv/bin/activate"
echo "  python3 test_pipeline.py"
echo ""
