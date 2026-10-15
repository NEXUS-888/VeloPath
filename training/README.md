# Small ball model (YOLO11s) - what was done and why

Written 2026-10-15 so any agent (Antigravity, Claude) knows exactly how `models/ball_small_yolo11s.pt` was made.
Code: `training/build_notebook.py` (builds `train_ball_model_colab.ipynb`), `training/make_synthetic.py`,
`training/compare_models.py`. The weights file is gitignored (`*.pt`); it lives in `models/` on the dev laptop and in
Google Drive `MyDrive/velopath/runs/ball_s1280/weights/`.

## Why
The app's ball model `ball_trackingv4.pt` (YOLO11x, 194 GFLOPs) is accurate but slow on the CPU-only laptop
(~2.9 s/frame at 1280, 1-5 min per clip). A small model (YOLO11s) is ~7x faster on a T4 (28.6 vs 203 ms/img).
Goal: same tracking accuracy, less time. ONNX, stride-2 scanning and lower resolution were tried or rejected:
ONNX was not faster than PyTorch on this CPU; stride-2 lost the ball; 640 misses the 4-8 px phone-video ball.

## Model and settings
- YOLO11s, started from pretrained `yolo11s.pt` (ultralytics), `imgsz=1280`, `epochs=40`, `batch=16`, `patience=15`, `workers=2`.
- Classes (same as BaseballCV / ball_trackingv4): `0 glove, 1 homeplate, 2 baseball, 3 rubber`. The ball is class 2.
- Free Colab T4 GPU, ~7 min per epoch. Run dir on Drive: `velopath/runs/ball_s1280/` (`results.csv`, `weights/best.pt`, `last.pt`).
  The notebook resumes from `last.pt` automatically if it exists (Colab free tier cuts sessions after ~3.5 h).
- Trained 32 of 40 epochs; stopped by hand (session time, accuracy plateau). **Best checkpoint = epoch 30.**

## Training data (about 8.4k images)
1. **BaseballCV `baseball_rubber_home_glove`**: 4,110 MLB-broadcast 720p frames (ball ~14-25 px). Stray class-4 labels
   and duplicate "(1)" files were removed. Broadcast only, which is why phone clips alone were weak.
2. **Teacher-checked real frames from the user's own clips (259)**: the big model ("teacher") labelled frames; only confident
   detections became labels, unsure frames were dropped so a real unlabelled ball is never taught as background.
3. **Synthetic frames (4,000)**: `make_synthetic.py` cuts real ball crops (with natural motion blur) from BaseballCV, and pastes
   0-2 per image onto frames from the user's phone clips: size 5-40 px, motion streak, brightness change, white / pink / yellow.
- User clips used (in Drive `velopath/clips/`): `20260923_140405.MOV`, `20260923_140422.MOV.mp4`, `VID_20260903_095215_4.mp4`,
  the WhatsApp 474x850 clip, `test real world.mp4`.
- **Held out, never used in training or synthetic backgrounds:** `not good tracking/Test !.mp4` and
  `test videos/20260923_140455.MOV.mp4`. Use only these two to judge the model.

## Results
- Validation (BaseballCV val, all classes, mAP50): epoch 10 0.860, epoch 12 0.878, epoch 21 0.894, **epoch 30 0.902**,
  epoch 31 0.883, epoch 32 0.884. After about epoch 12 it only wobbles between 0.85 and 0.90.
- Ball only at epoch 10: small P 0.894 / R 0.934 / mAP50 0.951 vs big P 0.942 / R 0.890 / mAP50 0.937.
- Real clips (`python training/compare_models.py models/ball_small_yolo11s.pt`, CPU):

| Clip | Mode | Time | Frames | Recall | Start/end error |
|---|---|---|---|---|---|
| Test !.mp4 | big | 59 s | 51-65 | 1.00 | 0/0 |
| Test !.mp4 | hybrid | 48 s | 51-65 | 1.00 | 0/0 |
| Test !.mp4 | small only | 16 s | 52-65 | 0.93 | 1/0 |
| 20260923_140455.MOV.mp4 | big | 271 s | 44-72 | 1.00 | 0/0 |
| 20260923_140455.MOV.mp4 | hybrid | 77 s | 44-72 | 1.00 | 0/0 |
| 20260923_140455.MOV.mp4 | small only | 29 s | 45-71 | 0.93 | 1/-1 |

  (Clip 1 recall is against hand ground truth; clip 2 has none, so it is measured against the big model's track.)

## How the app uses it (hybrid)
`velopath/model_manager.py:resolve_small_model_path()` returns `models/ball_small_yolo11s.pt` if present;
`PitchTracker.__init__` loads it as `scan_model`. The small model scans whole frames at 1280 and also finds home plate;
the big model still refines the ball near each detection at native resolution (`_refine_flight`). Normal (non-baseball) mode
does not use it. Delete the file to go back to big-model-only. **Hybrid is on; small-only is NOT used** (it trims a frame at the
pitch start/end, which would shift speed and break slightly).

## Limits / not verified
- Only two held-out clips; the hybrid has not been tried on other cameras or lighting.
- It matched the big model; it was not shown to be more accurate, and clips the big model fails on were not tested.
- Pink ball and 4K footage are still unsupported (the 4K pink-ball clip tracked the cap).
- Best further gain: a 5-10 min tripod session (white ball, 1080p, >=60 fps, plate and rubber visible).

## Re-running / resuming
1. Open `training/train_ball_model_colab.ipynb` in Colab (rebuild it with `python training/build_notebook.py`), set a T4 GPU first.
2. Mount Drive and keep `velopath/clips/`, `ball_trackingv4.pt` and `baseball_rubber_home_glove.zip` there.
3. Copy `training/make_synthetic.py` to `/content/` and run the pipeline cell: unzip, generate data, train (or resume from `last.pt`).
4. Download `runs/ball_s1280/weights/best.pt`, save as `models/ball_small_yolo11s.pt`, then run `compare_models.py` and
   keep it only if both held-out clips still match the big model.
