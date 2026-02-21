FROM python:3.13-slim

# system deps: ffmpeg/ffprobe + build basics
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# install python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy app
COPY . .

# create folders (safe)
RUN mkdir -p user_uploads static/reels

ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production

# web port
EXPOSE 8000

# Gunicorn for Flask
CMD ["gunicorn", "-b", "0.0.0.0:8000", "main:app", "--workers", "2", "--timeout", "300"]
