import json
from datetime import datetime, timedelta, timezone

from redis import Redis
from sqlalchemy import select

from app.core.config import settings
from app.models.entities import ExportJob
from app.services.exports import run_export_job


def redis_client():
    return Redis.from_url(settings.redis_url,decode_responses=True,socket_connect_timeout=1)


def enqueue_export(job_id:str):
    redis_client().lpush(settings.task_queue_name,json.dumps({"type":"export","job_id":job_id}))


def execute_export(job_id:str,session_factory):
    while True:
        result=run_export_job(job_id,session_factory)
        if result!="RETRY": return result


def dispatch_export(job_id:str,session_factory,background_tasks=None):
    if settings.task_queue_mode=="redis": enqueue_export(job_id); return "redis"
    if background_tasks is not None: background_tasks.add_task(execute_export,job_id,session_factory)
    else: execute_export(job_id,session_factory)
    return "inline"


def recover_stale_exports(session_factory)->int:
    db=session_factory(); recovered=0; cutoff=datetime.now(timezone.utc)-timedelta(minutes=settings.export_stale_minutes)
    try:
        jobs=list(db.scalars(select(ExportJob).where(ExportJob.status=="PROCESSING",ExportJob.updated_at<cutoff)).all())
        for job in jobs: job.status="PENDING"; recovered+=1
        db.commit()
    finally: db.close()
    for job in jobs: enqueue_export(job.id)
    return recovered
