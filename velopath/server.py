"""
FastAPI Server for VeloPath AI: Web-based pitch tracking, speed analysis & strike zone umpiring.
"""
from typing import Optional
import os
import shutil
import uuid
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from velopath.pipeline import process_pitch_video

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


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="Frontend index.html not found.")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


_SAMPLE_CACHE = None


@app.get("/api/sample")
async def process_sample_pitch():
    """Processes or returns the cached pitch video in the workspace instantly."""
    meta_file = os.path.join(OUTPUTS_DIR, "velopath_sample_meta.json")
    out_file = os.path.join(OUTPUTS_DIR, "velopath_sample_result.mp4")

    if os.path.exists(meta_file) and os.path.exists(out_file):
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                import json
                return JSONResponse(json.load(f))
        except Exception:
            pass

    sample_file = os.path.join(BASE_DIR, "assets", "sample_pitch.mp4")
    if not os.path.exists(sample_file):
        sample_file = os.path.join(BASE_DIR, "WhatsApp Video 2026-09-02 at 11.24.19 PM.mp4")
    if not os.path.exists(sample_file):
        raise HTTPException(status_code=404, detail="Sample video not found in workspace.")

    result = process_pitch_video(
        input_video_path=sample_file,
        output_video_path=out_file,
        distance_ft=60.5,
    )
    result["video_url"] = "/api/video/velopath_sample_result.mp4"
    try:
        import json
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
    except Exception:
        pass
    return JSONResponse(result)


import json
from pydantic import BaseModel
from velopath.pipeline import process_pitch_video, rerender_pitch


class RerenderPayload(BaseModel):
    video_id: str
    trajectory: list
    distance_ft: float = 60.5
    custom_strike_zone: dict
    graphic_style: str = "statcast_cyan"
    pitch_number: int = 1


@app.post("/api/process")
async def process_uploaded_video(
    file: UploadFile = File(...),
    distance_ft: float = Form(60.5),
    pitch_number: int = Form(1),
    graphic_style: str = Form("statcast_cyan"),
    custom_strike_zone: Optional[str] = Form(None),
):
    """Accepts an uploaded pitch video and returns Pitch Lab metrics and rendered video."""
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

    try:
        result = process_pitch_video(
            input_video_path=saved_input,
            output_video_path=saved_output,
            distance_ft=distance_ft,
            custom_strike_zone=zone_dict,
            pitch_number=pitch_number,
            graphic_style=graphic_style,
        )
        result["video_id"] = file_id
        result["video_url"] = f"/api/video/{output_filename}"
        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@app.post("/api/rerender")
async def rerender_existing_pitch(payload: RerenderPayload):
    """Fast re-render using existing trajectory and updated strike zone or graphic style."""
    if payload.video_id == "sample":
        input_video = os.path.join(BASE_DIR, "WhatsApp Video 2026-09-02 at 11.24.19 PM.mp4")
    else:
        matches = [f for f in os.listdir(UPLOADS_DIR) if f.startswith(f"input_{payload.video_id}")]
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
    file_path = os.path.join(OUTPUTS_DIR, filename)
    if not os.path.exists(file_path):
        file_path = os.path.join(BASE_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Video not found.")

    file_size = os.path.getsize(file_path)
    range_header = request.headers.get("range")

    if not range_header:
        return FileResponse(file_path, media_type="video/mp4")

    # Parse range header: e.g. "bytes=0-1024"
    byte_range = range_header.replace("bytes=", "").split("-")
    start = int(byte_range[0])
    end = int(byte_range[1]) if byte_range[1] else file_size - 1

    chunk_size = (end - start) + 1

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

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(chunk_size),
        "Content-Type": "video/mp4",
    }
    return StreamingResponse(iterfile(), status_code=status.HTTP_206_PARTIAL_CONTENT, headers=headers)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("velopath.server:app", host="0.0.0.0", port=8000, reload=False)
