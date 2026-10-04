FROM python:3.11-slim

WORKDIR /app

ENV PIP_NO_CACHE_DIR=1 \
    YOLO_CONFIG_DIR=/tmp/ultralytics \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt \
    # ultralytics réinstalle opencv-python 5.x qui écrase cv2 (CascadeClassifier
    # déplacé) -> on le retire, headless 4.x suffit (même module, sans GUI)
    && pip uninstall -y opencv-python opencv-python-headless \
    && pip install --no-cache-dir --force-reinstall --no-deps "opencv-python-headless>=4.8,<5"

COPY src/ ./src/

# Preuves écrites dans le volume partagé (monté au run par algorithms-controller)
ENV IMAGES_ROOT=/var/www/5scontrol/images

CMD ["python", "src/main.py"]
