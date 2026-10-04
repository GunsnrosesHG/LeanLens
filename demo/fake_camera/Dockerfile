FROM python:3.11-slim

WORKDIR /app

ENV PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir flask opencv-python-headless numpy

COPY camera_app.py .

EXPOSE 6001

CMD ["python", "camera_app.py"]
