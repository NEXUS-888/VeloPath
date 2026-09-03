#!/usr/bin/env bash
set -e

echo "========================================================"
echo "               VeloPath AI Launcher (Unix)"
echo "========================================================"
echo ""

if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 could not be found!"
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "[*] Creating virtual environment (venv)..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "[*] Installing/Verifying requirements..."
pip install --upgrade pip
pip install -r requirements.txt

echo "[*] Verifying model weights..."
python3 -c "import velopath.model_manager as mm; p = mm.resolve_model_path(True); dev, name = mm.get_acceleration_device(); print(f'[VeloPath AI] Model: {p}'); print(f'[VeloPath AI] Device: {name}')"

echo ""
echo "========================================================"
echo "  Server starting on: http://localhost:8000"
echo "========================================================"
echo ""
python3 -m uvicorn velopath.server:app --host 0.0.0.0 --port 8000
