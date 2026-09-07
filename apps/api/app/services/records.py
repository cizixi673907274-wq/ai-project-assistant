from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import RecordStatus
from app.models.entities import AIAnalysis, Record, RecordEvent
from app.services.ai import AIProviderError, analysis_metadata, provider
from app.services.observability import log_invocation, notify_admins_of_failure
from app.services.state_machine import ensure_transition
import time


def event(
    db: Session,
    record: Record,
    actor_id: str | None,
    event_type: str,
    before: dict | None = None,
    after: dict | None = None,
    request_id: str | None = None,
):
    db.add(
        RecordEvent(
            record_id=record.id,
            actor_id=actor_id,
            event_type=event_type,
            before_json=before,
            after_json=after,
            request_id=request_id,
        )
    )


def transition(
    db: Session,
    record: Record,
    target: RecordStatus,
    actor_id: str | None,
    event_type: str,
    request_id: str | None = None,
):
    ensure_transition(record.status, target)
    before = record.status.value
    record.status = target
    event(db, record, actor_id, event_type, {"status": before}, {"status": target.value}, request_id)


def run_analysis(record_id: str, session_factory):
    db = session_factory()
    try:
        record = db.get(Record, record_id)
        if not record or record.status not in {RecordStatus.SUBMITTED, RecordStatus.WAITING_SUPPLEMENT}:
            return
        transition(db, record, RecordStatus.AI_PROCESSING, None, "AI_PROCESSING")
        db.commit()
        started = time.time()
        try:
            result_response = provider().analyze(record.content)
            result = result_response.result
            meta = analysis_metadata(result_response, started)
            log_invocation(
                db,
                service="ai",
                provider=result_response.provider,
                model=result_response.model,
                status="success",
                latency_ms=meta["latency_ms"],
                request_id=None,
                record_id=record.id,
                token_usage=result_response.token_usage,
                cost_estimate=result_response.cost_estimate,
                attempt_count=result_response.attempt_count,
            )
            record.title = result["title"]
            record.summary = result["summary"]
            record.category_snapshot = result["category"]["name"]
            record.stage_snapshot = result["stage"]["name"]
            record.product_snapshot = result["product"]["name"]
            db.add(
                AIAnalysis(
                    record_id=record.id,
                    result_json=result,
                    confidence=result["confidence"],
                    reasoning_summary=result["reasoning_summary"],
                    **meta,
                )
            )
            target = RecordStatus.READY_TO_ASSIGN if result["confidence"] >= settings.ai_review_threshold else RecordStatus.AI_REVIEW_REQUIRED
            transition(db, record, target, None, "AI_ANALYSIS_COMPLETED")
        except Exception as exc:
            error = str(exc)[:4000]
            attempts = exc.attempt_count if isinstance(exc, AIProviderError) else 1
            log_invocation(
                db,
                service="ai",
                provider=settings.ai_provider,
                model=settings.ai_model,
                status="failed",
                latency_ms=int((time.time() - started) * 1000),
                request_id=None,
                record_id=record.id,
                error=error,
                attempt_count=attempts,
            )
            if attempts >= settings.ai_failure_alert_threshold:
                notify_admins_of_failure(
                    db,
                    "AI 分析连续失败",
                    f"记录 {record.title}（{record.id}）AI 分析失败，最近错误：{error}",
                    related_record_id=record.id,
                )
            result = {
                "title": record.title,
                "summary": record.content[:500],
                "category": {"name": "待人工确认"},
                "stage": {"name": "待人工确认"},
                "product": {"name": "待人工确认"},
                "priority": record.priority.value,
                "suggested_department": {"name": "待人工确认"},
                "need_follow_up": True,
                "confidence": 0,
                "reasoning_summary": "AI 服务暂不可用，请人工确认。",
                "missing_fields": ["category", "stage", "product"],
            }
            db.add(
                AIAnalysis(
                    record_id=record.id,
                    result_json=result,
                    confidence=0,
                    provider=settings.ai_provider,
                    model=settings.ai_model,
                    prompt_version=settings.ai_prompt_version,
                    reasoning_summary=result["reasoning_summary"],
                    latency_ms=int((time.time() - started) * 1000),
                    token_usage={},
                    cost_estimate=0,
                    attempt_count=attempts,
                    error=error,
                )
            )
            transition(db, record, RecordStatus.AI_REVIEW_REQUIRED, None, "AI_ANALYSIS_FAILED")
            event(db, record, None, "AI_ERROR_RECORDED", after={"message": error, "attempt_count": attempts})
        db.commit()
    finally:
        db.close()
