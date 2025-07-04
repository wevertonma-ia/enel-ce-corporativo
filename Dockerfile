FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV CHROMIUM_BIN=/usr/bin/chromium
ENV DOWNLOAD_DIR=/tmp/selenium_downloads

RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    fonts-liberation \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p ${DOWNLOAD_DIR} && chmod 777 ${DOWNLOAD_DIR}

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]