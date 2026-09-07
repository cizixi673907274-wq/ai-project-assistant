from fastapi import APIRouter, Depends
from redis import Redis
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

from app.api.deps import current_user
from app.api.deps import require_roles
from app.core.enums import RoleCode
from app.core.config import settings
from app.db.session import get_db
from app.models.entities import ExportJob, Notification, User
from app.services.observability import collect_observability

router=APIRouter(prefix="/system",tags=["系统"])


@router.get("/integrations",summary="外部服务配置状态（不返回密钥）")
def integrations(_:User=Depends(require_roles(RoleCode.SUPER_ADMIN))):
    ai_ready=settings.ai_provider=="mock" or bool(settings.ai_api_key)
    tencent_ready=bool(settings.tencent_secret_id and settings.tencent_secret_key)
    asr_ready=settings.asr_provider=="mock" or (tencent_ready if settings.asr_provider=="tencent_cloud" else bool(settings.ai_api_key))
    ocr_ready=settings.ocr_provider=="mock" or (tencent_ready if settings.ocr_provider=="tencent_cloud" else False)
    wechat_ready=settings.wechat_mock or bool(settings.wechat_app_id and settings.wechat_app_secret)
    return {
        "environment":settings.app_env,
        "ai":{"provider":settings.ai_provider,"model":settings.ai_model if settings.ai_provider!="mock" else "mock-structured-v2","configured":ai_ready,"mock":settings.ai_provider=="mock"},
        "asr":{"provider":settings.asr_provider,"model":settings.asr_model if settings.asr_provider!="mock" else "mock-transcript-v1","configured":asr_ready,"mock":settings.asr_provider=="mock"},
        "ocr":{"provider":settings.ocr_provider,"model":"GeneralBasicOCR" if settings.ocr_provider=="tencent_cloud" else "mock-ocr-v1","configured":ocr_ready,"mock":settings.ocr_provider=="mock"},
        "wechat":{"provider":"mock" if settings.wechat_mock else "code2session","configured":wechat_ready,"mock":settings.wechat_mock},
        "storage":{"provider":"minio","configured":bool(settings.minio_endpoint and settings.minio_bucket)},
        "production_issues":settings.production_issues() if settings.is_production else [],
    }


@router.get("/runtime",summary="任务队列与导出运行状态")
def runtime(db:Session=Depends(get_db),_:User=Depends(require_roles(RoleCode.SUPER_ADMIN))):
    redis_ok=False; queue_depth=0; worker_online=settings.task_queue_mode=="inline"
    try:
        client=Redis.from_url(settings.redis_url,decode_responses=True,socket_connect_timeout=.5)
        redis_ok=bool(client.ping()); queue_depth=client.llen(settings.task_queue_name)
        if settings.task_queue_mode=="redis": worker_online=bool(client.get(settings.task_worker_heartbeat_key))
    except Exception: pass
    counts=dict(db.execute(select(ExportJob.status,func.count()).group_by(ExportJob.status)).all())
    return {
        "queue":{"mode":settings.task_queue_mode,"redis":"ok" if redis_ok else "unavailable","worker_online":worker_online,"depth":queue_depth},
        "exports":{"pending":counts.get("PENDING",0),"processing":counts.get("PROCESSING",0),"completed":counts.get("COMPLETED",0),"failed":counts.get("FAILED",0),"expired":counts.get("EXPIRED",0),"retention_days":settings.export_retention_days,"max_attempts":settings.export_job_max_attempts},
    }


@router.get("/observability",summary="AI / ASR 可观测指标与最近告警")
def observability(
    days:int=7,
    db:Session=Depends(get_db),
    _:User=Depends(require_roles(RoleCode.SUPER_ADMIN)),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    alerts = db.scalars(
        select(Notification)
        .where(
            Notification.type == "AI_ALERT",
            Notification.created_at >= since,
        )
        .order_by(Notification.created_at.desc())
        .limit(20)
    ).all()
    unread = db.scalar(
        select(func.count(Notification.id)).where(
            Notification.type == "AI_ALERT",
            Notification.is_read.is_(False),
        )
    ) or 0
    return {
        "window":{"days":days},
        "invocations":collect_observability(db,days=days),
        "alert_summary":{"recent_unread_count":unread},
        "recent_alerts":[
            {
                "id":item.id,
                "title":item.title,
                "content":item.content,
                "related_record_id":item.related_record_id,
                "is_read":item.is_read,
                "created_at":item.created_at,
            }
            for item in alerts
        ],
    }
