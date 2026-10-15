# VeloPath AI Model Weights

This directory holds the deep learning weights for baseball and softball pitch tracking:
- `ball_trackingv4.pt` (~109 MB, YOLOv11 primary flight model)
- `ball_small_yolo11s.pt` (~72.5 MB, YOLO11s fast scan model)

## Automatic Self-Assembly & Download
Both models are pre-packaged as split parts inside `models/weights_parts/` and **automatically assemble in 0.3s on first launch**:
- `models/weights_parts/ball_trackingv4.pt.part1` & `.part2`
- `models/weights_parts/ball_small_yolo11s.pt.part1` & `.part2`

If parts are ever missing, VeloPath AI will automatically download them from official hosting.

## Manual Download (Optional)
If you are in an offline or air-gapped environment without repo parts:
- **Primary Model**: https://data.balldatalab.com/index.php/s/YkGBwbFtsf34ky3/download/ball_tracking_v4-YOLOv11.pt -> Save as `models/ball_trackingv4.pt`
