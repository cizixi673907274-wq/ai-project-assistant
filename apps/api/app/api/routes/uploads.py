from datetime import timedelta
from io import BytesIO
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from minio import Minio
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user, is_admin
from app.core.config import settings
from app.core.enums import MediaType
from app.db.session import get_db
from app.models.entities import Record, RecordMedia, RecordTask, User
from app.services.ai import AIProviderError, provider
from app.services.observability import log_invocation, notify_admins_of_failure
import time

router = APIRouter(prefix="/uploads", tags=["文件"])


def client():
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def public_client():
    return Minio(
        settings.minio_public_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_public_secure,
    )


def can_access(db: Session, record: Record, user: User):
    return is_admin(user) or record.creator_id == user.id or bool(
        db.scalar(
            select(RecordTask.id).where(
                RecordTask.record_id == record.id,
                RecordTask.assignee_id == user.id,
            )
        )
    )


def ensure_image(name: str, mime: str):
    suffix = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    supported = {"jpg", "jpeg", "png", "bmp", "pdf"}
    if not (mime.startswith("image/") or mime == "application/pdf" or suffix in supported):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "OCR_FILE_UNSUPPORTED",
                "message": "OCR 仅支持 JPG、JPEG、PNG、BMP 或 PDF 文件",
            },
        )


@router.post("/presign", summary="获取对象存储签名上传地址")
def presign(
    filename: str,
    mime: str = "application/octet-stream",
    user: User = Depends(current_user),
):
    key = f"{user.id}/{uuid4()}-{filename}"
    c = client()
    try:
        if not c.bucket_exists(settings.minio_bucket):
            c.make_bucket(settings.minio_bucket)
        url = public_client().presigned_put_object(
            settings.minio_bucket, key, expires=timedelta(minutes=15)
        )
        return {"storage_key": key, "upload_url": url, "expires_in": 900}
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "STORAGE_UNAVAILABLE",
                "message": "文件服务暂不可用，请稍后重试",
                "details": {"reason": str(e)},
            },
        )


@router.post("/complete", summary="登记已上传文件")
def complete(
    record_id: str,
    storage_key: str,
    original_name: str,
    mime: str,
    size: int,
    media_type: MediaType,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    record = db.get(Record, record_id)
    if not record or (record.creator_id != user.id and not is_admin(user)):
        raise HTTPException(
            status_code=404,
            detail={"code": "RECORD_NOT_FOUND", "message": "记录不存在或无权上传"},
        )
    if not storage_key.startswith(f"{user.id}/") and not is_admin(user):
        raise HTTPException(
            status_code=403,
            detail={"code": "STORAGE_KEY_FORBIDDEN", "message": "不能登记其他用户上传的文件"},
        )
    if size > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "FILE_TOO_LARGE",
                "message": f"单个文件不能超过{settings.max_upload_mb}MB",
            },
        )
    media = RecordMedia(
        record_id=record_id,
        storage_key=storage_key,
        original_name=original_name,
        mime=mime,
        size=size,
        type=media_type,
    )
    db.add(media)
    db.commit()
    db.refresh(media)
    return {
        "id": media.id,
        "storage_key": media.storage_key,
    }


@router.post("/direct", summary="小程序直传文件")
async def direct_upload(
    record_id: str = Form(...),
    media_type: MediaType = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    record = db.get(Record, record_id)
    if not record or (record.creator_id != user.id and not is_admin(user)):
        raise HTTPException(
            status_code=404,
            detail={"code": "RECORD_NOT_FOUND", "message": "记录不存在或无权上传"},
        )
    data = await file.read()
    size = len(data)
    if not size:
        raise HTTPException(
            status_code=422,
            detail={"code": "EMPTY_FILE", "message": "不能上传空文件"},
        )
    if size > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "FILE_TOO_LARGE",
                "message": f"单个文件不能超过{settings.max_upload_mb}MB",
            },
        )
    mime = file.content_type or "application/octet-stream"
    key = f"{user.id}/{uuid4()}-{file.filename or 'upload'}"
    storage = client()
    try:
        if not storage.bucket_exists(settings.minio_bucket):
            storage.make_bucket(settings.minio_bucket)
        storage.put_object(
            settings.minio_bucket,
            key,
            BytesIO(data),
            size,
            content_type=mime,
        )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "STORAGE_UNAVAILABLE",
                "message": "文件服务暂不可用，请稍后重试",
                "details": {"reason": str(e)},
            },
        )
    media = RecordMedia(
        record_id=record.id,
        storage_key=key,
        original_name=file.filename or "upload",
        mime=mime,
        size=size,
        type=media_type,
    )
    db.add(media)
    db.commit()
    db.refresh(media)
    return {
        "id": media.id,
        "storage_key": media.storage_key,
        "original_name": media.original_name,
        "mime": media.mime,
        "size": media.size,
        "type": media.type.value,
    }


@router.post("/transcribe-direct", summary="小程序语音输入即时转写")
async def transcribe_direct(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    data = await file.read()
    size = len(data)
    if not size:
        raise HTTPException(
            status_code=422,
            detail={"code": "EMPTY_AUDIO", "message": "录音内容为空，请重新录制"},
        )
    if size > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=422,
            detail={"code": "FILE_TOO_LARGE", "message": f"单段录音不能超过{settings.max_upload_mb}MB"},
        )
    started = time.time()
    try:
        transcript = provider("asr").transcribe(
            file.filename or "voice.mp3", data, file.content_type or "audio/mpeg"
        )
    except AIProviderError as e:
        error = str(e)
        attempts = getattr(e, "attempt_count", 1)
        log_invocation(
            db,
            service="asr",
            provider=settings.asr_provider,
            model=settings.asr_model,
            status="failed",
            latency_ms=int((time.time() - started) * 1000),
            request_id=None,
            record_id=None,
            error=error,
            attempt_count=attempts,
        )
        if attempts >= settings.ai_failure_alert_threshold:
            notify_admins_of_failure(
                db,
                "ASR 转写失败",
                f"小程序转写失败：{error}",
                related_record_id=None,
                type="AI_ALERT",
            )
        raise HTTPException(
            status_code=502,
            detail={
                "code": "ASR_FAILED",
                "message": "语音识别失败，请重试或改用文字输入",
                "details": {"reason": error},
            },
        )
    except Exception as e:  # pragma: no cover
        error = str(e)
        log_invocation(
            db,
            service="asr",
            provider=settings.asr_provider,
            model=settings.asr_model,
            status="failed",
            latency_ms=int((time.time() - started) * 1000),
            request_id=None,
            record_id=None,
            error=error,
        )
        notify_admins_of_failure(
            db,
            "ASR 转写失败",
            f"小程序转写失败：{error}",
            related_record_id=None,
            type="AI_ALERT",
        )
        raise HTTPException(
            status_code=502,
            detail={
                "code": "ASR_FAILED",
                "message": "语音识别失败，请重试或改用文字输入",
                "details": {"reason": error},
            },
            )
    log_invocation(
        db,
        service="asr",
        provider=settings.asr_provider,
        model=settings.asr_model,
        status="success",
        latency_ms=int((time.time() - started) * 1000),
        request_id=None,
        record_id=None,
        error=None,
        token_usage={},
        cost_estimate=0,
    )
    return {"transcript": transcript, "provider": settings.asr_provider}


@router.post("/ocr-direct", summary="图片即时文字识别")
async def ocr_direct(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    data = await file.read()
    name = file.filename or "image.jpg"
    mime = file.content_type or "application/octet-stream"
    if not data:
        raise HTTPException(
            status_code=422,
            detail={"code": "EMPTY_IMAGE", "message": "图片内容为空，请重新选择"},
        )
    ensure_image(name, mime)
    if len(data) > settings.ocr_max_mb * 1024 * 1024:
        raise HTTPException(
            status_code=422,
            detail={"code": "FILE_TOO_LARGE", "message": f"OCR 文件不能超过{settings.ocr_max_mb}MB"},
        )
    started = time.time()
    try:
        result = provider("ocr").recognize(name, data, mime)
    except AIProviderError as e:
        error = str(e)
        attempts = getattr(e, "attempt_count", 1)
        log_invocation(
            db,
            service="ocr",
            provider=settings.ocr_provider,
            model="GeneralBasicOCR" if settings.ocr_provider == "tencent_cloud" else "mock-ocr-v1",
            status="failed",
            latency_ms=int((time.time() - started) * 1000),
            request_id=None,
            error=error,
            attempt_count=attempts,
        )
        raise HTTPException(
            status_code=502,
            detail={
                "code": "OCR_FAILED",
                "message": "图片文字识别失败，请重试或手动输入",
                "details": {"reason": error},
            },
        )
    log_invocation(
        db,
        service="ocr",
        provider=result.provider,
        model=result.model,
        status="success",
        latency_ms=int((time.time() - started) * 1000),
        request_id=result.request_id or None,
        token_usage={},
        cost_estimate=0,
    )
    return {
        "text": result.text,
        "lines": result.lines,
        "provider": result.provider,
        "model": result.model,
        "request_id": result.request_id or None,
    }


@router.post("/{media_id}/transcribe", summary="语音转写（支持 Mock/真实服务切换）")
def transcribe(
    media_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    media = db.get(RecordMedia, media_id)
    if not media or media.type != MediaType.AUDIO:
        raise HTTPException(
            status_code=404,
            detail={"code": "AUDIO_NOT_FOUND", "message": "语音文件不存在"},
        )
    record = db.get(Record, media.record_id)
    if not record or not can_access(db, record, user):
        raise HTTPException(
            status_code=404,
            detail={"code": "AUDIO_NOT_FOUND", "message": "语音文件不存在或无权访问"},
        )
    data = None
    if settings.asr_provider != "mock":
        try:
            response = client().get_object(settings.minio_bucket, media.storage_key)
            data = response.read()
            response.close()
            response.release_conn()
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "AUDIO_READ_FAILED",
                    "message": "无法读取音频文件",
                    "details": {"reason": str(e)},
                },
            )
    started = time.time()
    try:
        media.transcript = provider("asr").transcribe(
            media.original_name, data, media.mime
        )
    except AIProviderError as e:
        error = str(e)
        attempts = getattr(e, "attempt_count", 1)
        db.add(media)
        log_invocation(
            db,
            service="asr",
            provider=settings.asr_provider,
            model=settings.asr_model,
            status="failed",
            latency_ms=int((time.time() - started) * 1000),
            request_id=None,
            media_id=media.id,
            error=error,
            attempt_count=attempts,
        )
        if attempts >= settings.ai_failure_alert_threshold:
            notify_admins_of_failure(
                db,
                "ASR 转写失败",
                f"记录 {media.record_id} 的语音转写失败，文件 {media.original_name}：{error}",
                related_record_id=media.record_id,
                type="AI_ALERT",
            )
        db.commit()
        raise HTTPException(
            status_code=502,
            detail={
                "code": "ASR_FAILED",
                "message": "语音转写失败",
                "details": {"reason": error},
            },
        )
    except Exception as e:  # pragma: no cover
        error = str(e)
        db.add(media)
        log_invocation(
            db,
            service="asr",
            provider=settings.asr_provider,
            model=settings.asr_model,
            status="failed",
            latency_ms=int((time.time() - started) * 1000),
            request_id=None,
            media_id=media.id,
            error=error,
        )
        notify_admins_of_failure(
            db,
            "ASR 转写失败",
            f"记录 {media.record_id} 的语音转写失败，文件 {media.original_name}：{error}",
            related_record_id=media.record_id,
            type="AI_ALERT",
        )
        db.commit()
        raise HTTPException(
            status_code=502,
            detail={
                "code": "ASR_FAILED",
                "message": "语音转写失败",
                "details": {"reason": error},
            },
        )
    log_invocation(
        db,
        service="asr",
        provider=settings.asr_provider,
        model=settings.asr_model,
        status="success",
        latency_ms=int((time.time() - started) * 1000),
        request_id=None,
        media_id=media.id,
        error=None,
        token_usage={},
        cost_estimate=0,
    )
    db.commit()
    return {"media_id": media.id, "transcript": media.transcript, "provider": settings.asr_provider}


@router.post("/{media_id}/ocr", summary="识别已上传图片中的文字")
def recognize_media(
    media_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    media = db.get(RecordMedia, media_id)
    if not media or media.type != MediaType.IMAGE:
        raise HTTPException(
            status_code=404,
            detail={"code": "IMAGE_NOT_FOUND", "message": "图片文件不存在"},
        )
    record = db.get(Record, media.record_id)
    if not record or not can_access(db, record, user):
        raise HTTPException(
            status_code=404,
            detail={"code": "IMAGE_NOT_FOUND", "message": "图片文件不存在或无权访问"},
        )
    ensure_image(media.original_name, media.mime)
    try:
        response = client().get_object(settings.minio_bucket, media.storage_key)
        data = response.read()
        response.close()
        response.release_conn()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "IMAGE_READ_FAILED",
                "message": "无法读取图片文件",
                "details": {"reason": str(e)},
            },
        )
    started = time.time()
    try:
        result = provider("ocr").recognize(media.original_name, data, media.mime)
        media.extracted_text = result.text
    except AIProviderError as e:
        error = str(e)
        attempts = getattr(e, "attempt_count", 1)
        log_invocation(
            db,
            service="ocr",
            provider=settings.ocr_provider,
            model="GeneralBasicOCR" if settings.ocr_provider == "tencent_cloud" else "mock-ocr-v1",
            status="failed",
            latency_ms=int((time.time() - started) * 1000),
            request_id=None,
            media_id=media.id,
            error=error,
            attempt_count=attempts,
        )
        db.commit()
        raise HTTPException(
            status_code=502,
            detail={
                "code": "OCR_FAILED",
                "message": "图片文字识别失败",
                "details": {"reason": error},
            },
        )
    log_invocation(
        db,
        service="ocr",
        provider=result.provider,
        model=result.model,
        status="success",
        latency_ms=int((time.time() - started) * 1000),
        request_id=result.request_id or None,
        media_id=media.id,
        token_usage={},
        cost_estimate=0,
    )
    db.commit()
    return {
        "media_id": media.id,
        "text": media.extracted_text,
        "lines": result.lines,
        "provider": result.provider,
        "model": result.model,
        "request_id": result.request_id or None,
    }


@router.get("/{media_id}/download-url", summary="获取带有效期的文件下载地址")
def download_url(
    media_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    media = db.get(RecordMedia, media_id)
    if not media:
        raise HTTPException(
            status_code=404,
            detail={"code": "MEDIA_NOT_FOUND", "message": "文件不存在"},
        )
    record = db.get(Record, media.record_id)
    if not record or not can_access(db, record, user):
        raise HTTPException(
            status_code=404,
            detail={"code": "MEDIA_NOT_FOUND", "message": "文件不存在或无权访问"},
        )
    try:
        url = public_client().presigned_get_object(
            settings.minio_bucket, media.storage_key, expires=timedelta(minutes=15)
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "STORAGE_UNAVAILABLE",
                "message": "文件服务暂不可用，请稍后重试",
            },
        )
    return {"media_id": media.id, "download_url": url, "expires_in": 900}


@router.get("/{media_id}/content", summary="读取文件内容")
def media_content(
    media_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    media = db.get(RecordMedia, media_id)
    if not media:
        raise HTTPException(
            status_code=404,
            detail={"code": "MEDIA_NOT_FOUND", "message": "文件不存在"},
        )
    record = db.get(Record, media.record_id)
    if not record or not can_access(db, record, user):
        raise HTTPException(
            status_code=404,
            detail={"code": "MEDIA_NOT_FOUND", "message": "文件不存在或无权访问"},
        )
    try:
        response = client().get_object(settings.minio_bucket, media.storage_key)
    except Exception:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "STORAGE_UNAVAILABLE",
                "message": "文件服务暂不可用，请稍后重试",
            },
        )

    def stream():
        try:
            yield from response.stream(64 * 1024)
        finally:
            response.close()
            response.release_conn()

    mime = media.mime or "application/octet-stream"
    previewable = (
        mime.startswith(("image/", "text/", "audio/", "video/"))
        or mime == "application/pdf"
    )
    disposition = "inline" if previewable else "attachment"
    encoded_name = quote(media.original_name or "file")
    return StreamingResponse(
        stream(),
        media_type=mime,
        headers={
            "Content-Disposition": (
                f"{disposition}; filename=file; filename*=UTF-8''{encoded_name}"
            ),
            "Cache-Control": "private, max-age=300",
            "X-Content-Type-Options": "nosniff",
        },
    )
