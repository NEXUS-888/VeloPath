# VeloPath AI ⚡⚾
> **Computer Vision Baseball Pitch Trajectory Tracking, Statcast 3D Visuals & Automated Strike Zone System**

VeloPath is an end-to-end computer vision engine and web platform that analyzes baseball and softball pitch videos. It accurately detects the airborne ball, calculates real-time release velocity and flight kinematics, reconstructs smooth Statcast 3D trajectory streamlines, and evaluates Automated Ball-Strike (ABS) strike zone calls.

---

## Key Features

- **⚡ Statcast 3D Trajectory Streamlines**:
  - High-resolution cubic spline trajectory fitting.
  - Multi-layer emissive bloom with a white-hot laser core and glowing 3D ball marker.
  - Selectable visual themes: **Statcast 3D Cyan** (MLB Broadcast standard), **PitchLab Neon Gold**, **Electric Violet**, and **Laser Emerald**.

- **🎯 Precision Velocity & Kinematics Engine**:
  - Automatically isolates the true pitch flight window (.38 - 0.44	ext{s}$) using peak translational displacement analysis, stripping out pitcher windups.
  - Computes release speed (**MPH** & **km/h**), total flight time (**ms**), and vertical/horizontal break (**inches**).
  - Supports regulation MLB (.5	ext{ ft}$), Little League (.0	ext{ ft}$), Softball (.0	ext{ ft}$), and custom distances.

- **⚖️ Automated Ball-Strike (ABS) Umpire with Interactive Calibration**:
  - Sleek broadcast K-Zone overlay with 1px anti-aliased borders, corner brackets, and subtle 3x3 grid.
  - **On-Screen Interactive Editor**: Drag the strike zone directly over home plate on the video and resize with corner handles.
  - **Fast 1-Second Re-Rendering**: Instant re-rendering API (\/api/rerender\) that updates the video with custom strike zone alignment without re-running full ball detection.

- **🖥️ High-Tech Video Player Dashboard**:
  - Frame-by-frame stepping forward/backward.
  - Slow-motion playback rates (.25	ext{x}$, .5	ext{x}$, .0	ext{x}$).
  - Clean startup empty state with drag-and-drop video upload and built-in demo pitch.
  - Universal web-compatible H.264 video rendering with \+faststart\ streaming.

---

## Architecture

\\	ext
VeloPath/
├── velopath/                  # Core Computer Vision & Physics Engine
│   ├── physics.py             # Velocity (MPH/km/h), flight time & pitch break
│   ├── strike_zone.py         # Automated Ball-Strike (ABS) strike zone engine
│   ├── tracker.py             # YOLOv8 ball tracking & cubic spline interpolation
│   ├── renderer.py            # Statcast 3D laser streamline & HUD card renderer
│   ├── pipeline.py            # End-to-end video processing & instant re-renderer
│   └── server.py              # FastAPI server & streaming video backend
│
├── static/                    # Dark-Theme Frontend Dashboard
│   ├── index.html             # Video player & interactive strike zone UI
│   ├── style.css              # Custom styling
│   └── app.js                 # Video controller, on-screen drag/resize & telemetry
│
└── tests/                     # Automated Test Suites (13/13 passing)
\
---

## Quick Start

### 1. Clone the Repository
\\ash
git clone https://github.com/NEXUS-888/VeloPath.git
cd VeloPath
\
### 2. Install Dependencies
\\ash
pip install -r requirements.txt
\
### 3. Setup Model Weights (Optional)
To enable YOLOv8 deep learning ball detection:
\\ash
git clone https://github.com/BaseballCV/BaseballCV
\*(VeloPath automatically falls back to optical motion tracking if weights are not downloaded)*

### 4. Launch the Server
\\ash
python -m uvicorn velopath.server:app --host 0.0.0.0 --port 8000
\Open **http://localhost:8000** in your browser!

---

## Running Tests

\\ash
python -m pytest tests/
\
---

## License

MIT License. Developed for advanced baseball analytics and automated ball-strike verification.
