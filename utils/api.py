# app/main.py
import asyncio
import base64
import uuid
from dataclasses import dataclass
from typing import List, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# 👉 기존 update_db를 그대로 사용
from utils.update_db import update_db  

# -----------------------------
# Pydantic 모델 정의
# -----------------------------
class IngestRecord(BaseModel):
    # streamlit이 /ingest로 보내는 json의 형식과 필수값을 엄격히 정의
    worker: str = Field(..., min_length=1)
    upload_type: str = Field(..., min_length=1)  # "ENR", "KOR", "ENG", "ENR+KOR"
    script: str = Field(..., min_length=1)
    tts_text: Optional[str] = None
    audio_name: Optional[str] = None
    audio_b64: str = Field(..., min_length=10)  # WAV base64 string

class IngestBatch(BaseModel):
    #여러건 묶음
    batch_id: Optional[str] = None
    records: List[IngestRecord]

# -----------------------------
# Job / Queue 구조
# -----------------------------
@dataclass
class Job:
    job_id: str
    batch_id: Optional[str]
    records: List[IngestRecord]
    status: str = "queued"       # queued | processing | done | failed
    processed: int = 0
    error: Optional[str] = None
    inserted_ids: Optional[List[int]] = None

class JobQueue:
    def __init__(self):
        self.queue: asyncio.Queue[Job] = asyncio.Queue()
        self.jobs: Dict[str, Job] = {}
        self.lock = asyncio.Lock()

    async def enqueue(self, batch_id: Optional[str], records: List[IngestRecord]) -> str:
        job_id = str(uuid.uuid4())
        job = Job(job_id=job_id, batch_id=batch_id, records=records)
        self.jobs[job_id] = job
        await self.queue.put(job)
        return job_id

    async def get(self, job_id: str) -> Optional[Job]:
        return self.jobs.get(job_id)

job_queue = JobQueue()

# -----------------------------
# Worker (순차 DB 삽입)
# -----------------------------
async def worker_loop():
    while True:
        job = await job_queue.queue.get()
        async with job_queue.lock:
            job.status = "processing"

        try:
            inserted_all = []
            for rec in job.records:
                # base64 → bytes 변환
                audio_bytes = base64.b64decode(rec.audio_b64)

                # update_db 호출 (여러 서버에 삽입 가능)
                ids = update_db(
                    rec.audio_name or f"tts_{uuid.uuid4().hex}.wav",
                    rec.script,
                    audio_bytes,
                    rec.upload_type,
                    rec.worker
                )
                inserted_all.extend(ids)

            async with job_queue.lock:
                job.status = "done"
                job.processed = len(job.records)
                job.inserted_ids = inserted_all
                job.error = None

        except Exception as e:
            async with job_queue.lock:
                job.status = "failed"
                job.error = str(e)

        finally:
            job_queue.queue.task_done()

# -----------------------------
# FastAPI 앱
# -----------------------------
app = FastAPI(title="TTS Ingest API", version="0.1.0")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(worker_loop())

@app.post("/ingest")
async def ingest(batch: IngestBatch):
    if not batch.records:
        raise HTTPException(status_code=400, detail="records is empty")

    # ✅ 간단 검증
    for i, r in enumerate(batch.records):
        if not r.script.strip():
            raise HTTPException(status_code=400, detail=f"row {i}: script is blank")
        if not r.worker.strip():
            raise HTTPException(status_code=400, detail=f"row {i}: worker is blank")
        if not r.upload_type.strip():
            raise HTTPException(status_code=400, detail=f"row {i}: upload_type is blank")

    # 큐 적재
    job_id = await job_queue.enqueue(batch.batch_id, batch.records)
    return JSONResponse({"job_id": job_id, "status": "queued", "total": len(batch.records)})

@app.get("/jobs/{job_id}")
async def job_status(job_id: str):
    job = await job_queue.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return {
        "job_id": job.job_id,
        "batch_id": job.batch_id,
        "status": job.status,
        "processed": job.processed,
        "error": job.error,
        "inserted_ids": job.inserted_ids,
    }
