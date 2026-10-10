import os, uuid, subprocess, threading, shutil, json, math
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

ROOT=Path(__file__).resolve().parent
JOBS=ROOT/'jobs'; JOBS.mkdir(exist_ok=True)
MAX_MB=int(os.getenv('MAX_UPLOAD_MB','500'))
CHUNK_SECONDS=int(os.getenv('CHUNK_SECONDS','120'))
WAV2LIP_DIR=Path(os.getenv('WAV2LIP_DIR',str(ROOT/'Wav2Lip'))).resolve()
CHECKPOINT=Path(os.getenv('WAV2LIP_CHECKPOINT',str(WAV2LIP_DIR/'checkpoints'/'wav2lip_gan.pth'))).resolve()
PYTHON=os.getenv('INFERENCE_PYTHON','python')
app=FastAPI(title='LipSync Studio')
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
statuses={}

def run(cmd, cwd=None):
    p=subprocess.run([str(c) for c in cmd],cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    if p.returncode: raise RuntimeError(p.stdout[-2500:])
    return p.stdout

def duration(path):
    return float(json.loads(run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',path]))['format']['duration'])

def render(job_id, image, audio):
    state=statuses[job_id]; folder=JOBS/job_id
    try:
        if not (WAV2LIP_DIR/'inference.py').exists() or not CHECKPOINT.exists():
            raise RuntimeError('Wav2Lip engine is not configured. See README.md for setup instructions.')
        total=duration(audio)
        if total<=0: raise RuntimeError('Audio is empty')
        count=math.ceil(total/CHUNK_SECONDS)
        segments=[]
        for i in range(count):
            state.update(stage=f'Rendering part {i+1} of {count}',progress=round(i/count*95))
            start=i*CHUNK_SECONDS; length=min(CHUNK_SECONDS,total-start)
            part_audio=folder/f'part_{i:04d}.wav'
            part_video=folder/f'part_{i:04d}.mp4'
            run(['ffmpeg','-y','-ss',str(start),'-i',str(audio),'-t',str(length),'-ar','16000','-ac','1',str(part_audio)])
            run([PYTHON,'inference.py','--checkpoint_path',str(CHECKPOINT),'--face',str(image),'--audio',str(part_audio),'--outfile',str(part_video)],cwd=WAV2LIP_DIR)
            if not part_video.exists(): raise RuntimeError(f'Engine did not produce segment {i+1}')
            segments.append(part_video)
        concat=folder/'segments.txt'
        concat.write_text(''.join("file '"+p.name+"'\n" for p in segments))
        output=folder/'finished.mp4'
        # Re-encode joins to make final output playable on typical devices.
        run(['ffmpeg','-y','-f','concat','-safe','0','-i',str(concat),'-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',str(output)],cwd=folder)
        state.update(stage='Ready to download',progress=100,status='done')
    except Exception as e:
        state.update(status='error',stage=str(e)[:1000])

@app.get('/')
def home(): return FileResponse(ROOT/'static'/'index.html')

@app.post('/api/create')
async def create(image:UploadFile=File(...),audio:UploadFile=File(...), consent:str=Form(...)):
    if consent!='yes': raise HTTPException(400,'You must confirm you have permission to use the likeness and audio.')
    if image.content_type not in ('image/jpeg','image/png','image/webp'): raise HTTPException(400,'Upload a JPG, PNG, or WebP portrait.')
    if audio.content_type not in ('audio/mpeg','audio/mp3','audio/wav','audio/x-wav','audio/mp4','audio/x-m4a','application/octet-stream'): raise HTTPException(400,'Upload an MP3, WAV, or M4A audio file.')
    job_id=uuid.uuid4().hex; folder=JOBS/job_id; folder.mkdir()
    async def save(upload, name):
        dest=folder/name; size=0
        with dest.open('wb') as out:
            while data:=await upload.read(1024*1024):
                size+=len(data)
                if size>MAX_MB*1024*1024:
                    shutil.rmtree(folder,ignore_errors=True)
                    raise HTTPException(413,'File too large')
                out.write(data)
        return dest
    image_path=await save(image,'portrait'+Path(image.filename or '.jpg').suffix.lower())
    audio_path=await save(audio,'song'+Path(audio.filename or '.mp3').suffix.lower())
    statuses[job_id]={'status':'working','stage':'Preparing','progress':0}
    threading.Thread(target=render,args=(job_id,image_path,audio_path),daemon=True).start()
    return {'job_id':job_id}

@app.get('/api/jobs/{job_id}')
def status(job_id:str):
    if job_id not in statuses: raise HTTPException(404,'Job not found')
    return statuses[job_id]

@app.get('/api/jobs/{job_id}/video')
def video(job_id:str):
    if job_id not in statuses or statuses[job_id]['status']!='done': raise HTTPException(404,'Video not ready')
    return FileResponse(JOBS/job_id/'finished.mp4',media_type='video/mp4',filename='lipsync-video.mp4')
