# ReelyAI : http://reelyai.duckdns.org/

AI-powered short video reel generator. Upload images and videos, add AI-generated voiceover and background music, and get a polished reel ready to share.

## Features

- **Drag & Drop Upload** - Upload images, GIFs, and videos with drag-and-drop. Reorder files before processing.
- **AI Voice Narration** - Convert text to speech using ElevenLabs with multiple voice options and live preview.
- **AI Background Music** - Describe the vibe and get AI-generated background music mixed behind the voiceover.
- **Smart Timeline** - Images display for the right duration to match your voiceover. GIFs and videos keep their natural timing.
- **Gallery** - Browse and manage all generated reels.
- **Background Processing** - Reels are generated asynchronously via Redis job queue with real-time status updates.

## Tech Stack

- **Backend**: Flask, Gunicorn, Redis + RQ (job queue)
- **AI**: ElevenLabs API (text-to-speech + music generation)
- **Video Processing**: FFmpeg (scaling, concat, audio mixing)
- **Deployment**: Docker Compose, Nginx, AWS EC2
- **CI/CD**: GitHub Actions (auto-deploy on push to main)

## Prerequisites

- Docker and Docker Compose
- ElevenLabs API key (paid plan required for voice API access)

## Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/sanket3122/ReelyAI.git
   cd ReelyAI
   ```

2. **Create a `.env` file**
   ```
   ELEVENLABS_API_KEY=your_api_key_here
   ```

3. **Run with Docker Compose**
   ```bash
   docker compose build
   docker compose up -d
   ```

4. **Open the app**
   ```
   http://localhost:8000
   ```

## Architecture

```
User Browser
     |
     v
  Nginx (reverse proxy)
     |
     v
  Flask Web App (port 8000)
     |
     +--> Redis (job queue)
     |        |
     |        v
     |    RQ Worker
     |      - ElevenLabs TTS
     |      - ElevenLabs Music
     |      - FFmpeg pipeline
     |        |
     |        v
     |    static/reels/*.mp4
     |
     v
  Gallery / Download
```

## Project Structure

```
ReelyAI/
├── main.py                 # Flask routes (upload, gallery, API)
├── tasks.py                # RQ job definitions
├── generate_process.py     # FFmpeg pipeline (clips, concat, audio mix)
├── text_to_audio.py        # ElevenLabs TTS + music generation
├── worker.py               # RQ worker process
├── config.py               # Environment config
├── queue_config.py         # Redis/RQ setup
├── Dockerfile
├── docker-compose.yml
├── templates/              # Jinja2 HTML templates
│   ├── base.html
│   ├── index.html
│   ├── create.html
│   ├── processing.html
│   └── gallery.html
├── static/
│   ├── css/
│   ├── img/
│   └── reels/              # Generated output videos
└── .github/workflows/
    └── deploy.yml          # Auto-deploy to EC2
```

## How It Works

1. User uploads images/videos, enters voiceover text, selects a voice, and optionally describes background music
2. Flask saves files and metadata, then enqueues a job to Redis
3. The RQ worker picks up the job and:
   - Generates TTS audio via ElevenLabs
   - Generates background music (if requested) via ElevenLabs Music API
   - Scales all media to 1080x1920 portrait format
   - Builds a timeline matching voiceover duration
   - Concatenates clips and mixes audio with FFmpeg
4. The finished reel appears in the gallery

## Deployment

The project includes a GitHub Actions workflow that auto-deploys to AWS EC2 on every push to `main`. Required GitHub secrets:

| Secret | Description |
|--------|-------------|
| `EC2_HOST` | EC2 public IP address |
| `EC2_SSH_KEY` | EC2 private key (.pem contents) |
| `ELEVENLABS_API_KEY` | ElevenLabs API key |
