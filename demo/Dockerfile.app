FROM python:3.11-slim

WORKDIR /app

ENV PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir flask requests psycopg[binary] opencv-python-headless numpy

COPY scenario_driver.py .
COPY templates/ templates/

EXPOSE 6002

CMD ["python", "scenario_driver.py"]
