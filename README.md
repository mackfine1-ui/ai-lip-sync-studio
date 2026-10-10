# LipSync Studio — long-form AI lip-sync website

This is a working FastAPI website and video-job orchestrator. **Actual AI lip-sync requires a separately installed Wav2Lip inference engine and its model checkpoint.** The site does not generate lip-sync without that engine. Wav2Lip's original code/checkpoint may have **noncommercial restrictions**: check the upstream license before using it commercially.

## Requirements
- Python 3.10+ (use an environment compatible with your selected Wav2Lip fork)
- `ffmpeg` and `ffprobe` installed and on PATH
- A configured Wav2Lip inference installation, dependencies and model checkpoint; an NVIDIA GPU is recommended for long videos

## Run
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
# Set these environment variables to your existing Wav2Lip setup:
# WAV2LIP_DIR=/path/to/Wav2Lip
# WAV2LIP_CHECKPOINT=/path/to/Wav2Lip/checkpoints/wav2lip_gan.pth
# INFERENCE_PYTHON=/path/to/python-with-Wav2Lip-dependencies
uvicorn app:app --host 127.0.0.1 --port 8000
```
Visit http://127.0.0.1:8000.

On Windows PowerShell, set environment variables with `$env:WAV2LIP_DIR='C:\\path\\to\\Wav2Lip'`, etc.

## How long videos work
Audio is split into 120-second WAV segments; each segment is lip-synced using the same portrait, and FFmpeg concatenates the outputs into a single MP4. There is no hard-coded 4-minute duration cap. Actual limits depend on disk, GPU, processing time, and deployment request/upload size. Segment boundaries may have visual discontinuities. A 10-minute video can take substantial processing time.

## Important limitations
- This is a local/self-hosted prototype, **not a deployed public website**.
- Jobs run in background threads and statuses live in memory. Restarting the server loses job statuses; videos stay in `jobs/` until manually removed. For production, add durable queues, authentication, rate limits, storage lifecycle, HTTPS, file scanning, and abuse safeguards.
- For best results use a clear front-facing portrait. Lip-sync quality varies, especially for singing.
- Use only media you own or are authorized to use; get the depicted person's consent and clearly label synthetic media.
