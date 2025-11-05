#!/bin/bash
# Azure App Service custom startup script for the FastAPI backend.
# Installs LibreOffice (if missing) and launches Uvicorn.
set -euo pipefail

# Install LibreOffice once (skips if already present)
if ! command -v soffice >/dev/null 2>&1; then
  echo "LibreOffice not detected. Installing..."
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends libreoffice fonts-dejavu-core
  apt-get clean
  rm -rf /var/lib/apt/lists/*
else
  echo "LibreOffice already installed. Skipping."
fi

# Ensure Python dependencies are installed
if [ -f "/home/site/wwwroot/requirements.txt" ]; then
  python -m pip install --upgrade pip
  python -m pip install -r /home/site/wwwroot/requirements.txt
elif [ -f "/home/site/wwwroot/apps/requirements.txt" ]; then
  python -m pip install --upgrade pip
  python -m pip install -r /home/site/wwwroot/apps/requirements.txt
fi

exec python -m uvicorn apps.main:app --host 0.0.0.0 --port 8000 --proxy-headers
