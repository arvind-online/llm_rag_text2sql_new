# Multi-stage Dockerfile to build both UI and Backend in a single image

# ---------------------------
# Stage 1: Build Frontend (UI)
# ---------------------------
# Using Node 22 (LTS) which is compatible with most modern React builds
FROM node:22-slim AS ui-build

WORKDIR /app/ui

# Copy dependency definitions
COPY ui/package.json ui/package-lock.json ./

# Install dependencies strictly from lock file
RUN npm ci

# Copy the rest of the UI source code
COPY ui/ .

# Build the frontend (produces files in /app/ui/dist)
RUN npm run build


# ---------------------------
# Stage 2: Backend Runtime
# ---------------------------
# Using Python 3.9-slim-bookworm to match user's Python 3.9 and ensure newer SQLite for ChromaDB
FROM python:3.9-slim-bookworm

WORKDIR /app

# Install system dependencies
# build-essential for compiling some python packages if needed
# curl for healthchecks (optional but good practice)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy python requirements
COPY requirements.txt .

# Install python dependencies strictly
RUN pip install --default-timeout=1000 --no-cache-dir torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
# Note: we rely on .dockerignore to exclude .venv, .git, ui/node_modules, etc.
COPY . .

# Copy built frontend assets from the ui-build stage
# We place them in ui/dist because main.py is configured to serve from there
COPY --from=ui-build /app/ui/dist ./ui/dist

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Expose the application port
EXPOSE 8000

# Command to run the application
# Using uvicorn directly for production performance
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
