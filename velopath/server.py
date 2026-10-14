"""
FastAPI Server for VeloPath AI: Web-based pitch tracking, speed analysis & strike zone umpiring.
"""
from typing import Annotated, List, Optional
import os
import re
import shutil
import time
import uuid
import json
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from velopath.pipeline import process_pitch_video, rerender_pitch

app = FastAPI(title="VeloPath AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")

os.makedirs(OUTPUTS_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

PROGRESS = {}  # job_id -> {"stage", "pct", "started"} while /api/process runs; polled by the UI


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="Frontend index.html not found.")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/api/health")
@app.get("/health")
async def health_check():
    return {"status": "ok", "app": "VeloPath AI", "port": 8000}


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Silences browser favicon requests without 404 errors."""
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/video_feed")
async def legacy_video_feed():
    return RedirectResponse(url="/")


@app.get("/api/sample")
def process_sample_pitch():
    """Processes or returns the cached pitch video in the workspace instantly."""
    meta_file = os.path.join(OUTPUTS_DIR, "velopath_sample_meta.json")
    out_file = os.path.join(OUTPUTS_DIR, "velopath_sample_result.mp4")

    if os.path.exists(meta_file) and os.path.exists(out_file):
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                return JSONResponse(json.load(f))
        except Exception:
            pass

    sample_file = os.path.join(BASE_DIR, "assets", "sample_pitch.mp4")
    if not os.path.exists(sample_file):
        raise HTTPException(status_code=404, detail="Sample video not found in workspace.")

    result = process_pitch_video(
        input_video_path=sample_file,
        output_video_path=out_file,
        distance_ft=60.5,
    )
    result["video_url"] = "/api/video/velopath_sample_result.mp4"
    try:
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
    except Exception:
        pass
    return JSONResponse(result)


class RerenderPayload(BaseModel):
    video_id: str
    trajectory: list
    distance_ft: float = 60.5
    custom_strike_zone: Optional[dict] = None
    graphic_style: str = "statcast_cyan"
    ball_type: str = "auto"
    perspective: str = "auto"
    pitch_number: int = 1
    trim_to_pitch: bool = False
    hud_style: str = "none"
    mode: str = "baseball"
    show_strike_zone: Optional[bool] = None
    # two front corners of home plate tapped on the rendered video, [[x, y], [x, y]]
    plate_corners: Optional[List[Annotated[List[float], Field(min_length=2, max_length=2)]]] = Field(None, min_length=2, max_length=2)
    batter_height_in: float = Field(72.0, ge=36.0, le=96.0)

    @field_validator("plate_corners")
    @classmethod
    def corners_apart(cls, v):
        if v and v[0] == v[1]:
            raise ValueError("plate corners must be two different points")
        return v


@app.post("/api/process")
def process_uploaded_video(
    file: UploadFile = File(...),
    distance_ft: float = Form(60.5),
    pitch_number: int = Form(1),
    graphic_style: str = Form("statcast_cyan"),
    ball_type: str = Form("auto"),
    perspective: str = Form("auto"),
    custom_strike_zone: Optional[str] = Form(None),
    trim_to_pitch: bool = Form(False),
    hud_style: str = Form("none"),
    mode: str = Form("baseball"),
    job_id: Optional[str] = Form(None),
    start_s: Optional[float] = Form(None),
    end_s: Optional[float] = Form(None),
):
    """Accepts an uploaded pitch video and returns Pitch Lab metrics and rendered video.
    Optional client-chosen job_id lets the UI poll /api/progress/{job_id} meanwhile."""
    if job_id is not None and not re.fullmatch(r"[A-Za-z0-9]{1,32}", job_id):
        raise HTTPException(status_code=422, detail="job_id must be 1-32 letters or digits.")
    if (start_s is None) != (end_s is None) or (start_s is not None and not 0 <= start_s < end_s):
        raise HTTPException(status_code=422, detail="Pitch window needs 0 <= start_s < end_s (seconds).")
    started = time.monotonic()
    file_id = str(uuid.uuid4())[:8]
    ext = os.path.splitext(file.filename)[1] or ".mp4"
    saved_input = os.path.join(UPLOADS_DIR, f"input_{file_id}{ext}")
    output_filename = f"velopath_{file_id}.mp4"
    saved_output = os.path.join(OUTPUTS_DIR, output_filename)

    with open(saved_input, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    zone_dict = None
    if custom_strike_zone:
        try:
            zone_dict = json.loads(custom_strike_zone)
        except Exception:
            zone_dict = None

    progress = None
    if job_id:
        PROGRESS[job_id] = {"stage": "Queued", "pct": 0.0, "started": started}
        progress = lambda stage, pct: PROGRESS[job_id].update(stage=stage, pct=pct)  # noqa: E731
    try:
        result = process_pitch_video(
            input_video_path=saved_input,
            output_video_path=saved_output,
            distance_ft=distance_ft,
            custom_strike_zone=zone_dict,
            pitch_number=pitch_number,
            graphic_style=graphic_style,
            ball_type=ball_type,
            perspective=perspective,
            trim_to_pitch=trim_to_pitch,
            hud_style=hud_style,
            mode=mode,
            progress=progress,
            time_window=(start_s, end_s) if start_s is not None else None,
        )
        result["video_id"] = file_id
        result["video_url"] = f"/api/video/{output_filename}"
        result["processing_time_s"] = round(time.monotonic() - started, 1)
        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
    finally:
        PROGRESS.pop(job_id, None)


@app.get("/api/progress/{job_id}")
def job_progress(job_id: str):
    """Stage, percent and elapsed seconds of a running /api/process job."""
    job = PROGRESS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="No running job with that id.")
    return {"stage": job["stage"], "pct": round(100 * job["pct"]), "elapsed_s": round(time.monotonic() - job["started"], 1)}


@app.post("/api/rerender")
def rerender_existing_pitch(payload: RerenderPayload):
    """Fast re-render using existing trajectory and updated strike zone or graphic style."""
    if payload.video_id == "sample":
        input_video = os.path.join(BASE_DIR, "assets", "sample_pitch.mp4")
    else:
        if not payload.video_id.isalnum():
            raise HTTPException(status_code=404, detail="Original video not found for re-render.")
        matches = [f for f in os.listdir(UPLOADS_DIR) if f.startswith(f"input_{payload.video_id}.")]
        if not matches:
            raise HTTPException(status_code=404, detail="Original video not found for re-render.")
        input_video = os.path.join(UPLOADS_DIR, matches[0])

    output_filename = f"velopath_{payload.video_id}.mp4"
    saved_output = os.path.join(OUTPUTS_DIR, output_filename)

    try:
        result = rerender_pitch(
            input_video_path=input_video,
            output_video_path=saved_output,
            trajectory=payload.trajectory,
            distance_ft=payload.distance_ft,
            custom_strike_zone=payload.custom_strike_zone,
            graphic_style=payload.graphic_style,
            pitch_number=payload.pitch_number,
            ball_type=payload.ball_type,
            perspective=payload.perspective,
            trim_to_pitch=payload.trim_to_pitch,
            hud_style=payload.hud_style,
            mode=payload.mode,
            show_strike_zone=payload.show_strike_zone,
            plate_corners=payload.plate_corners,
            batter_height_in=payload.batter_height_in,
        )
        result["video_id"] = payload.video_id
        result["video_url"] = f"/api/video/{output_filename}"
        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Re-render failed: {str(e)}")


@app.get("/api/video/{filename}")
@app.head("/api/video/{filename}")
async def stream_video(filename: str, request: Request):
    """
    HTTP Range-streaming video endpoint for smooth seeking and scrubbing in HTML5 video players.
    """
    file_path = os.path.join(OUTPUTS_DIR, os.path.basename(filename.replace("\\", "/")))
    if not filename.endswith(".mp4") or not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Video not found.")

    file_size = os.path.getsize(file_path)
    range_header = request.headers.get("range")

    if not range_header or not range_header.startswith("bytes="):
        return FileResponse(file_path, media_type="video/mp4")

    # Parse RFC 7233 byte-range: e.g. "bytes=0-1024", "bytes=500-", "bytes=-500"
    try:
        raw_range = range_header.replace("bytes=", "").strip()
        parts = raw_range.split("-")
        if not parts[0]:  # Suffix range: bytes=-500
            suffix = int(parts[1])
            start = max(0, file_size - suffix)
            end = file_size - 1
        else:
            start = int(parts[0])
            end = int(parts[1]) if parts[1] else file_size - 1

        end = min(end, file_size - 1)
        if start > end or start >= file_size:
            return Response(
                status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
                headers={"Content-Range": f"bytes */{file_size}"}
            )
    except (ValueError, IndexError):
        return FileResponse(file_path, media_type="video/mp4")

    chunk_size = (end - start) + 1
    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(chunk_size),
        "Content-Type": "video/mp4",
    }

    if request.method == "HEAD":
        return Response(status_code=status.HTTP_206_PARTIAL_CONTENT, headers=headers)

    def iterfile():
        with open(file_path, "rb") as f:
            f.seek(start)
            bytes_left = chunk_size
            while bytes_left > 0:
                read_bytes = min(bytes_left, 1024 * 1024)
                data = f.read(read_bytes)
                if not data:
                    break
                bytes_left -= len(data)
                yield data

    return StreamingResponse(iterfile(), status_code=status.HTTP_206_PARTIAL_CONTENT, headers=headers)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("velopath.server:app", host="0.0.0.0", port=8000, reload=False)
