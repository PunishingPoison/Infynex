# ==============================================================================
# INFYNEX Edge AI Engine Dockerfile
# NVIDIA CUDA 12.x + PyTorch + OpenCV + Trimesh + Raycaster
# ==============================================================================

FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libspatialindex-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir \
    torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    opencv-python-headless \
    numpy \
    scipy \
    trimesh \
    rtree \
    pyembree \
    pyyaml \
    requests \
    pydantic \
    fastapi \
    uvicorn

COPY . /app

CMD ["python3", "ai_engine/main.py"]
