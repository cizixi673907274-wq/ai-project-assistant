import json
import logging
import time
from datetime import datetime, timezone

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.exports import cleanup_expired_exports
from app.services.task_queue import execute_export, recover_stale_exports, redis_client

logging.basicConfig(level=logging.INFO)
logger=logging.getLogger("ai_project_worker")


def run():
    client=redis_client(); recover_stale_exports(SessionLocal); last_cleanup=0.0
    logger.info("export worker started queue=%s",settings.task_queue_name)
    while True:
        client.set(settings.task_worker_heartbeat_key,datetime.now(timezone.utc).isoformat(),ex=90)
        now=time.monotonic()
        if now-last_cleanup>=settings.export_cleanup_interval_seconds:
            cleaned=cleanup_expired_exports(SessionLocal); last_cleanup=now
            if cleaned: logger.info("expired exports cleaned=%s",cleaned)
        item=client.brpop(settings.task_queue_name,timeout=5)
        if not item: continue
        try:
            payload=json.loads(item[1])
            if payload.get("type")=="export": execute_export(payload["job_id"],SessionLocal)
        except Exception: logger.exception("worker task failed")


if __name__=="__main__": run()
