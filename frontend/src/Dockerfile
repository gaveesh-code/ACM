FROM ubuntu:22.04

# Prevent interactive prompts during install
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3.10-venv \
    nodejs \
    npm \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# ── Backend setup ──────────────────────────────────────────
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip3 install --no-cache-dir -r backend/requirements.txt

# Copy backend source
COPY backend/ ./backend/

# ── Frontend setup ─────────────────────────────────────────
COPY frontend/package*.json ./frontend/
WORKDIR /app/frontend
RUN npm install
COPY frontend/ .
RUN npm run build

# ── Final setup ────────────────────────────────────────────
WORKDIR /app

# Copy data files
COPY data/ ./data/

# Serve frontend static files from backend
RUN cp -r /app/frontend/dist /app/backend/static

# Copy startup script
COPY start.sh .
RUN chmod +x start.sh

# Expose port
EXPOSE 8000

# Start the application
CMD ["./start.sh"]