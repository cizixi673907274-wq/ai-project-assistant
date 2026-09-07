from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, TypedDict

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import RoleCode
from app.models.entities import AIInvocationLog, Notification, User


class InvocationSummary(TypedDict, total=False):
    total: int
    success: int
    failed: int
    success_rate: float
    avg_latency_ms: int
    max_latency_ms: int
    p95_latency_ms: int
    total_cost: float
    avg_cost: float
    tokens: dict[str, int]
    recent_errors: list[dict[str, int]]


def log_invocation(
    db: Session,
    *,
    service:str,
    provider:str,
    model:str,
    status:str,
    latency_ms:int,
    request_id:str|None=None,
    record_id:str|None=None,
    media_id:str|None=None,
    token_usage:dict[str,Any]|None=None,
    cost_estimate:float=0.0,
    attempt_count:int=1,
    error:str|None=None,
):
    db.add(AIInvocationLog(
        service=service,
        provider=provider,
        model=model,
        status=status,
        latency_ms=max(0,int(latency_ms)),
        request_id=request_id,
        record_id=record_id,
        media_id=media_id,
        token_usage=token_usage or {},
        cost_estimate=cost_estimate or 0,
        attempt_count=attempt_count,
        error=error,
    ))
    db.commit()


def notify_admins_of_failure(
    db:Session,
    title:str,
    content:str,
    *,
    related_record_id:str|None=None,
    type:str="AI_ALERT",
):
    admin_ids=list(db.scalars(select(User.id).where(User.roles.any(code=RoleCode.SUPER_ADMIN))).all())
    if not admin_ids:
        return

    since=datetime.now(timezone.utc)-timedelta(minutes=settings.ai_failure_streak_minutes)
    for user_id in admin_ids:
        if related_record_id:
            exists=db.scalar(
                select(Notification.id).where(
                    and_(
                        Notification.user_id==user_id,
                        Notification.type==type,
                        Notification.related_record_id==related_record_id,
                        Notification.is_read.is_(False),
                        Notification.created_at>=since,
                    )
                )
            )
        else:
            exists=db.scalar(select(Notification.id).where(Notification.user_id==user_id,Notification.type==type,Notification.is_read.is_(False),Notification.created_at>=since))
        if exists:
            continue
        db.add(Notification(
            user_id=user_id,
            type=type,
            title=title,
            content=content,
            related_record_id=related_record_id,
        ))
    db.commit()


def _extract_tokens(usage:dict[str,Any]|None)->dict[str,int]:
    usage=usage or {}
    prompt=usage.get("prompt_tokens") or usage.get("input_tokens") or 0
    completion=usage.get("completion_tokens") or usage.get("output_tokens") or 0
    total=usage.get("total_tokens") or (prompt + completion)
    return {"prompt":int(prompt or 0),"completion":int(completion or 0),"total":int(total or 0)}


def summarize_invocations(rows:list[AIInvocationLog])->InvocationSummary:
    total=len(rows)
    if total==0:
        return {"total":0,"success":0,"failed":0,"success_rate":0.0,"avg_latency_ms":0,"max_latency_ms":0,"p95_latency_ms":0,"total_cost":0.0,"avg_cost":0.0,"tokens":{"prompt":0,"completion":0,"total":0},"recent_errors":[]}

    success_rows=[r for r in rows if r.status=="success"]
    failures=[r for r in rows if r.status!="success"]
    latencies=[r.latency_ms for r in rows]
    latencies_sorted=sorted(latencies)
    p95=latencies_sorted[max(0, int((len(latencies_sorted) - 1) * 0.95))] if latencies_sorted else 0
    token_totals={"prompt":0,"completion":0,"total":0}
    for item in rows:
        t=_extract_tokens(item.token_usage)
        token_totals["prompt"] += t["prompt"]
        token_totals["completion"] += t["completion"]
        token_totals["total"] += t["total"]
    errors=Counter((f.error or "未知错误")[:80] for f in failures)
    return {
        "total":total,
        "success":len(success_rows),
        "failed":len(failures),
        "success_rate":round(len(success_rows)/total*100,2),
        "avg_latency_ms":int(sum(latencies)/total),
        "max_latency_ms":max(latencies_sorted),
        "p95_latency_ms":p95,
        "total_cost":round(sum((item.cost_estimate or 0) for item in rows),8),
        "avg_cost":round(sum((item.cost_estimate or 0) for item in rows)/total,8),
        "tokens":token_totals,
        "recent_errors":[{"error":name,"count":count} for name,count in errors.most_common(5)],
    }


def collect_observability(db:Session,days:int=7)->dict[str,Any]:
    since=datetime.now(timezone.utc)-timedelta(days=days)
    rows=list(db.scalars(select(AIInvocationLog).where(AIInvocationLog.created_at>=since).order_by(AIInvocationLog.created_at.desc())).all())
    ai=summarize_invocations([r for r in rows if r.service=="ai"])
    asr=summarize_invocations([r for r in rows if r.service=="asr"])
    return {
        "window":{"days":days,"since":since,"to":datetime.now(timezone.utc)},
        "ai":ai,
        "asr":asr,
    }
