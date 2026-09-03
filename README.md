# VeloPath AI ⚡⚾
> **Computer Vision Baseball & Cricket Pitch Trajectory Tracking, Statcast 3D Visuals & Automated Strike Zone System**

[![Tests](https://img.shields.io/badge/tests-15%2F15%20passed-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)]()
[![PyTorch](https://img.shields.io/badge/PyTorch-CUDA%20%2F%20CPU-EE4C2C.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

VeloPath is an end-to-end computer vision engine and web platform that analyzes baseball and softball pitch videos. It accurately detects the airborne ball, calculates real-time release velocity and flight kinematics, reconstructs smooth Statcast 3D trajectory streamlines, and evaluates Automated Ball-Strike (ABS) strike zone calls.

---

## 🌟 Key Features

### ⚡ Statcast 3D Trajectory Streamlines
- **Laser-Core Emissive Streamlines**: Aerodynamic Statcast 3D laser ribbon with multi-layer bloom, white-hot core, and glowing baseball impact marker.
- **Cubic Spline Interpolation**: Eliminates video frame jitter and extrapolates physical ball trajectory smoothly across missing or blurred frames.
- **Selectable Visual Themes**:
  - **Statcast 3D Cyan** *(MLB Broadcast standard)*
  - **PitchLab Neon Gold** *(High-contrast dark fields)*
  - **Electric Violet** *(Cyberpunk glow)*
  - **Laser Emerald** *(Vibrant green streamline)*

### 🎯 Velocity & Flight Kinematics
- **Ballistic Speed & Flight Filtering**: Distinguishes high-speed airborne pitches (e.g. 8–15 px/frame) from stationary hands, return throws, and moving uniforms.
- **Complete Pitch Metrics**:
  - **Release Velocity**: Measured in both **MPH** and **km/h**.
  - **Flight Time**: Precise duration from release to plate in **milliseconds (ms)**.
  - **Pitch Break**: 2D trajectory deviation measuring **Vertical Break (in)** and **Horizontal Break (in)**.
  - **Pitch Classification**: Automatic pitch tagging (Four-Seam Fastball, Two-Seam / Sinker, Cutter, Slider, Sweeper, Curveball, Changeup, Dropball).
- **Regulation & Custom Mound Distances**:
  - MLB Regulation (60.5 ft / 18.44 m)
  - Little League / Minor (46.0 ft / 14.02 m)
  - Softball Regulation (43.0 ft / 13.11 m)
  - Custom Distance Input (ft)

### ⚖️ Automated Ball-Strike (ABS) Umpire & Direct Drag & Drop
- **Broadcast K-Zone Overlay**: Semi-transparent strike zone box with 1px anti-aliased borders, corner brackets, and 3x3 inner grid.
- **Direct Drag & Drop Positioning**: Click and drag the strike zone directly on the video screen to align it perfectly over home plate, stumps, or a practice net. Resize with corner handles.
- **Instant 1-Second Re-Rendering**: Change the strike zone position or graphic theme and re-render without re-running full YOLO ball detection.

### 🎥 Multi-Perspective & Multi-Ball Support
- **Camera Perspectives**:
  - **Behind Bowler / Pitcher POV**: Optimized for smartphone practice recordings behind the mound.
  - **MLB Broadcast Center-Field**: Tuned for TV broadcast cameras behind the pitcher looking towards home plate.
  - **Behind Home Plate**: Tuned for umpire/catcher perspective looking out to the mound.
- **Ball Types**:
  - **Regulation Baseball**: White leather with red stitching.
  - **Tennis / Cricket Ball**: High-visibility optic-yellow/neon green tennis and wind balls.

### 🚀 Self-Healing Cross-Platform Architecture
- **Self-Healing Model Manager**: Zero manual setup. The 114 MB YOLO detection model is packaged in the repository (`models/weights_parts/`) and auto-reassembles in 0.3 seconds on first launch.
- **NVIDIA GPU CUDA Acceleration**: Automatically detects NVIDIA GPUs, configures PyTorch CUDA 12.1, and processes pitches in **under 15 seconds**!
- **CPU Optimized Corridor Cropping**: Reduces CPU latency by ~60% on machines without discrete GPUs.
- **Action-Window Trimming**: Fast video export that clips idle walking and outputs a tight pitch highlight reel.

---

## 📁 Repository Structure

```text
VeloPath/
├── velopath/                  # Core Computer Vision & Physics Engine
│   ├── launcher.py            # Cross-platform application launcher & GPU detector
│   ├── model_manager.py       # Self-healing weights manager & hardware selector
│   ├── physics.py             # Velocity (MPH/km/h), flight time & pitch break
│   ├── strike_zone.py         # Automated Ball-Strike (ABS) strike zone engine
│   ├── tracker.py             # YOLO ball tracking, ROI cropping & spline smoothing
│   ├── renderer.py            # Statcast 3D streamline, HUD card & video encoder
│   ├── pipeline.py            # End-to-end video processing & instant re-renderer
│   └── server.py              # FastAPI server & streaming video backend
│
├── static/                    # Dark-Theme Frontend Web Dashboard
│   ├── index.html             # Video player & interactive strike zone UI
│   ├── style.css              # Custom styles & HUD overlays
│   └── app.js                 # Video controller, on-screen drag/resize & telemetry
│
├── models/                    # Deep Learning Model Weights
│   ├── README.md              # Weight specifications and download instructions
│   └── weights_parts/         # Repository-packaged split weights (auto-reassembled)
│       ├── ball_trackingv4.pt.part1
│       └── ball_trackingv4.pt.part2
│
├── tests/                     # Automated Test Suites (15/15 passing)
│   ├── test_physics.py        # Velocity, break, and flight time verification
│   ├── test_strike_zone.py    # ABS strike calling & edge buffer tests
│   └── test_tracker.py        # Spline smoothing & trajectory interpolation
│
├── run_gpu.bat                # One-click Windows NVIDIA GPU Launcher
├── run.bat                    # One-click Windows CPU Launcher
├── run.sh                     # One-click Unix / macOS / Linux Launcher
├── Dockerfile                 # Multi-stage production container image
├── docker-compose.yml         # Container compose definition (optional GPU passthrough)
└── requirements.txt           # Python dependencies
```

---

## 🚀 Quick Start

### Option A: Windows with NVIDIA GPU (Fastest)

Double-click **`run_gpu.bat`** (or run from PowerShell / Command Prompt):
```cmd
git clone https://github.com/NEXUS-888/VeloPath.git
cd VeloPath
.\run_gpu.bat
```
*The launcher automatically installs PyTorch with CUDA 12.1, reassembles the model weights, and starts the server on `http://localhost:8000`.*

---

### Option B: Windows CPU

Double-click **`run.bat`**:
```cmd
git clone https://github.com/NEXUS-888/VeloPath.git
cd VeloPath
.\run.bat
```

---

### Option C: macOS / Linux

Run the Unix launcher:
```bash
git clone https://github.com/NEXUS-888/VeloPath.git
cd VeloPath
chmod +x run.sh
./run.sh
```

---

### Option D: Docker Container

```bash
docker compose up --build
```
Open **http://localhost:8000** in your browser!

---

## 🧪 Running Automated Tests

VeloPath comes with a comprehensive test suite verifying kinematics math, strike zone geometries, and trajectory smoothing algorithms:

```bash
python -m pytest tests/ -v
```

```text
tests/test_physics.py::test_calculate_velocity_mph_regulation PASSED
tests/test_physics.py::test_calculate_velocity_mph_softball PASSED
tests/test_physics.py::test_calculate_velocity_kmh PASSED
tests/test_physics.py::test_calculate_flight_time_ms PASSED
tests/test_physics.py::test_velocity_zero_frames_raises PASSED
tests/test_physics.py::test_calculate_pitch_break PASSED
tests/test_physics.py::test_classify_pitch_type PASSED
tests/test_strike_zone.py::test_strike_zone_detection_inside PASSED
tests/test_strike_zone.py::test_strike_zone_detection_outside PASSED
tests/test_strike_zone.py::test_strike_zone_edge_buffer PASSED
tests/test_strike_zone.py::test_strike_zone_dynamic_dimensions PASSED
tests/test_tracker.py::test_interpolate_missing_frames PASSED
tests/test_tracker.py::test_smooth_trajectory_reduces_jitter PASSED
tests/test_tracker.py::test_detect_color_motion_ball_synthetic PASSED
tests/test_tracker.py::test_extrapolate_measured_flight PASSED

============================= 15 passed in 3.4s ==============================
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Serves the web dashboard application. |
| `GET` | `/api/health` | Health check endpoint returning server status and port. |
| `GET` | `/api/sample` | Runs Pitch Lab analysis on the built-in demo pitch video. |
| `POST` | `/api/process` | Uploads and processes a new pitch video (`multipart/form-data`). |
| `POST` | `/api/rerender` | Re-renders video with updated strike zone position or graphic theme in ~1s. |
| `GET` | `/api/video/{filename}` | Streams processed web-compatible H.264 MP4 videos with range requests. |

---

## 📄 License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for more information.
