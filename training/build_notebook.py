"""Builds train_ball_model_colab.ipynb with make_synthetic.py embedded. Rerun after editing either."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
BCV_URL = "https://data.balldatalab.com/index.php/s/pLy7sZqqMdx3jj7/download/baseball_rubber_home_glove.zip"


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(True)}


def code(text):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": text.strip("\n").splitlines(True)}


generator = open(os.path.join(HERE, "make_synthetic.py"), encoding="utf-8").read()

cells = [
    md("""
# VeloPath: train a small, fast ball detector (YOLO11s @ 1280)

**Before you start**
1. **Runtime → Change runtime type → T4 GPU**.
2. In Google Drive make a folder **`velopath`** containing:
   - **`clips/`**: your training videos. **Leave out** `20260923_140455.MOV.mp4` and `Test !.mp4`;
     they are kept back to test the new model fairly.
   - **`ball_trackingv4.pt`**: the current big model (it labels your clips as a teacher). It is in the
     project at `worker/ball_trackingv4.pt`.
3. **Runtime → Run all**. Training takes about **3-5 hours**. Keep this tab open.

**If Colab disconnects**: reconnect and **Run all** again. It continues from the last saved epoch
(saved in Drive under `velopath/runs/`).

**When it finishes**: download **`velopath/ball_small_yolo11s.pt`** from Drive and send it back.
"""),
    code("""
import os, subprocess
print(subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv"], capture_output=True, text=True).stdout)
import torch
assert torch.cuda.is_available(), "No GPU: Runtime -> Change runtime type -> T4 GPU, then Run all again."
"""),
    code("""
from google.colab import drive
drive.mount("/content/drive")
DRIVE = "/content/drive/MyDrive/velopath"
CLIPS, TEACHER = f"{DRIVE}/clips", f"{DRIVE}/ball_trackingv4.pt"
assert os.path.isdir(CLIPS) and os.listdir(CLIPS), f"Put your training videos in {CLIPS}"
assert os.path.exists(TEACHER), f"Put ball_trackingv4.pt in {DRIVE}"
print(len(os.listdir(CLIPS)), "clips:", sorted(os.listdir(CLIPS)))
"""),
    code("""
!pip -q install ultralytics
"""),
    md("BaseballCV ball dataset (MLB broadcast, ~4,000 labelled frames). Downloaded once into Drive; the server is slow and resumes after drops."),
    code(f"""
ZIP = f"{{DRIVE}}/baseball_rubber_home_glove.zip"
EXPECTED = 1427814730
for attempt in range(30):
    if os.path.exists(ZIP) and os.path.getsize(ZIP) == EXPECTED:
        break
    !curl -L -C - --retry 10 --retry-all-errors --retry-delay 5 -o "$ZIP" "{BCV_URL}"
assert os.path.getsize(ZIP) == EXPECTED, "Download incomplete: run this cell again."
!unzip -q -n "$ZIP" -d /content/bcv -x "__MACOSX/*"
!find /content/bcv -name "*(1)*" -delete
BCV = "/content/bcv/baseball_rubber_home_glove"
print({{s: len(os.listdir(f"{{BCV}}/{{s}}/images")) for s in ("train", "valid", "test")}})
"""),
    md("Synthetic + teacher-labelled frames from your clips (`make_synthetic.py`, embedded below)."),
    code("%%writefile /content/make_synthetic.py\n" + generator),
    code("""
!python /content/make_synthetic.py --baseballcv "$BCV" --clips "$CLIPS" --teacher "$TEACHER" --out /content/synth --n 4000
"""),
    code("""
open("/content/data.yaml", "w").write(f'''
train: [{BCV}/train/images, /content/synth/images]
val: {BCV}/valid/images
test: {BCV}/test/images
names: {{0: glove, 1: homeplate, 2: baseball, 3: rubber}}
''')
print(open("/content/data.yaml").read())
"""),
    md("Training. About 3-5 hours on a T4. If it stops with *CUDA out of memory*, change `batch=16` to `batch=8`."),
    code("""
from ultralytics import YOLO
RUN = f"{DRIVE}/runs/ball_s1280"
if os.path.exists(f"{RUN}/weights/last.pt"):
    print("Resuming from the last saved epoch")
    YOLO(f"{RUN}/weights/last.pt").train(resume=True)
else:
    YOLO("yolo11s.pt").train(data="/content/data.yaml", imgsz=1280, epochs=40, batch=16, patience=15,
                             workers=2, project=f"{DRIVE}/runs", name="ball_s1280", exist_ok=True)
"""),
    md("Check on held-out broadcast frames: small model vs the big one (ball class). Phone clips are tested back in the app."),
    code("""
for name, w in (("small YOLO11s", f"{RUN}/weights/best.pt"), ("big ball_trackingv4", TEACHER)):
    m = YOLO(w).val(data="/content/data.yaml", split="test", imgsz=1280, verbose=False)
    i = list(m.box.ap_class_index).index(2)  # per-class arrays follow ap_class_index; 2 = baseball
    print(f"{name:22s} baseball: precision {m.box.p[i]:.3f}  recall {m.box.r[i]:.3f}  mAP50 {m.box.ap50[i]:.3f}")
"""),
    code("""
import shutil
shutil.copy(f"{RUN}/weights/best.pt", f"{DRIVE}/ball_small_yolo11s.pt")
print("Done. Download velopath/ball_small_yolo11s.pt from Google Drive and send it back.")
"""),
]

nb = {"nbformat": 4, "nbformat_minor": 5, "cells": cells,
      "metadata": {"accelerator": "GPU", "colab": {"provenance": []}, "kernelspec": {"name": "python3", "display_name": "Python 3"}}}
path = os.path.join(HERE, "train_ball_model_colab.ipynb")
json.dump(nb, open(path, "w", encoding="utf-8"), indent=1)
print("wrote", path)
