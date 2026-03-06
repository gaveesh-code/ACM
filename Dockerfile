FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3.10-venv \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip3 install --no-cache-dir -r backend/requirements.txt
COPY backend/ ./backend/

COPY frontend/package*.json ./frontend/
WORKDIR /app/frontend
RUN npm install
COPY frontend/ .
RUN npm run build

WORKDIR /app
COPY data/ ./data/
RUN cp -r /app/frontend/dist /app/backend/static

# Write start.sh directly to avoid Windows CRLF line ending issues
RUN printf '#!/bin/bash\ncd /app/backend\npython3 -m uvicorn main:app --host 0.0.0.0 --port 8000\n' > start.sh \
    && chmod +x start.sh

EXPOSE 8000
CMD ["./start.sh"]