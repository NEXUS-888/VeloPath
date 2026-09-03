FROM python:3.11-slim

# Install system libraries for OpenCV and FFmpeg video processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY velopath/ velopath/
COPY static/ static/
COPY assets/ assets/
COPY models/ models/

# Pre-download YOLO weights during build (optional/fallback handled at runtime)
RUN python -c "import velopath.model_manager as mm; mm.resolve_model_path(True)" || true

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "uvicorn", "velopath.server:app", "--host", "0.0.0.0", "--port", "8000"]
