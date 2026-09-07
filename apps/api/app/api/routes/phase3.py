from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user, require_roles
from app.api.routes.records import visible_query
from app.core.config import settings
from app.core.enums import RecordStatus, RoleCode
from app.db.session import SessionLocal, get_db
from app.models.entities import ExportJob, ExportTemplate, Record, User
from app.services.exports import FIELD_DEFINITIONS, cleanup_expired_exports, read_export, validate_fields
from app.services.task_queue import dispatch_export

router=APIRouter(tags=["导出与模板"])


class TemplateCreate(BaseModel):
    name:str=Field(min_length=2,max_length=120)
    fields:list[str]=Field(min_length=1,max_length=12)
    is_default:bool=False


class TemplatePatch(BaseModel):
    name:str|None=Field(default=None,min_length=2,max_length=120)
    fields:list[str]|None=Field(default=None,min_length=1,max_length=12)
    is_default:bool|None=None
    is_active:bool|None=None


class ExportCreate(BaseModel):
    template_id:str|None=None
    record_ids:list[str]|None=Field(default=None,max_length=5000)
    project_id:str|None=None
    status:RecordStatus|None=None


def template_out(item:ExportTemplate):
    return {"id":item.id,"name":item.name,"format":item.format,"fields":item.fields_json,"is_default":item.is_default,"is_active":item.is_active,"creator_name":item.creator.name if item.creator else "系统","created_at":item.created_at,"updated_at":item.updated_at}


def job_out(item:ExportJob):
    return {"id":item.id,"template_id":item.template_id,"template_name":item.template.name,"format":item.format,"status":item.status,"filename":item.filename,"record_count":item.record_count,"error":item.error,"attempt_count":item.attempt_count,"completed_at":item.completed_at,"expires_at":item.expires_at,"created_at":item.created_at,"download_ready":item.status=="COMPLETED" and bool(item.file_key)}

def can_read_job(item:ExportJob,user:User): return item.creator_id==user.id or RoleCode.SUPER_ADMIN in {role.code for role in user.roles}


@router.get("/export-templates/fields",summary="可配置的导出字段")
def export_fields(_:User=Depends(current_user)):
    return [{"key":key,"label":label} for key,(label,_) in FIELD_DEFINITIONS.items()]


@router.get("/export-templates",summary="导出模板列表")
def export_templates(include_inactive:bool=False,db:Session=Depends(get_db),_:User=Depends(current_user)):
    q=select(ExportTemplate).order_by(ExportTemplate.is_default.desc(),ExportTemplate.created_at)
    if not include_inactive: q=q.where(ExportTemplate.is_active.is_(True))
    return [template_out(item) for item in db.scalars(q).unique().all()]


@router.post("/export-templates",status_code=201,summary="创建 Excel 导出模板")
def create_template(payload:TemplateCreate,db:Session=Depends(get_db),user:User=Depends(require_roles(RoleCode.SUPER_ADMIN))):
    if db.scalar(select(ExportTemplate.id).where(ExportTemplate.name==payload.name)): raise HTTPException(409,detail={"code":"EXPORT_TEMPLATE_EXISTS","message":"模板名称已存在"})
    try: fields=validate_fields(payload.fields)
    except ValueError as exc: raise HTTPException(422,detail={"code":"EXPORT_FIELDS_INVALID","message":str(exc)})
    if payload.is_default:
        for item in db.scalars(select(ExportTemplate).where(ExportTemplate.is_default.is_(True))).all(): item.is_default=False
    item=ExportTemplate(name=payload.name,format="XLSX",fields_json=fields,is_default=payload.is_default,creator_id=user.id); db.add(item); db.commit(); db.refresh(item); return template_out(item)


@router.patch("/export-templates/{template_id}",summary="编辑或停用导出模板")
def patch_template(template_id:str,payload:TemplatePatch,db:Session=Depends(get_db),_:User=Depends(require_roles(RoleCode.SUPER_ADMIN))):
    item=db.get(ExportTemplate,template_id)
    if not item: raise HTTPException(404,detail={"code":"EXPORT_TEMPLATE_NOT_FOUND","message":"导出模板不存在"})
    values=payload.model_dump(exclude_unset=True,exclude={"fields"})
    if payload.name and db.scalar(select(ExportTemplate.id).where(ExportTemplate.name==payload.name,ExportTemplate.id!=item.id)): raise HTTPException(409,detail={"code":"EXPORT_TEMPLATE_EXISTS","message":"模板名称已存在"})
    if payload.fields is not None:
        try: item.fields_json=validate_fields(payload.fields)
        except ValueError as exc: raise HTTPException(422,detail={"code":"EXPORT_FIELDS_INVALID","message":str(exc)})
    if payload.is_default:
        for other in db.scalars(select(ExportTemplate).where(ExportTemplate.is_default.is_(True),ExportTemplate.id!=item.id)).all(): other.is_default=False
    for key,value in values.items(): setattr(item,key,value)
    db.commit(); return template_out(item)


@router.post("/exports",status_code=202,summary="创建异步 Excel 导出任务")
def create_export(payload:ExportCreate,tasks:BackgroundTasks,db:Session=Depends(get_db),user:User=Depends(current_user)):
    template=db.get(ExportTemplate,payload.template_id) if payload.template_id else db.scalar(select(ExportTemplate).where(ExportTemplate.is_default.is_(True),ExportTemplate.is_active.is_(True)))
    if not template or not template.is_active: raise HTTPException(404,detail={"code":"EXPORT_TEMPLATE_NOT_FOUND","message":"请选择有效的导出模板"})
    q=visible_query(db,user)
    if payload.record_ids: q=q.where(Record.id.in_(payload.record_ids))
    if payload.project_id: q=q.where(Record.project_id==payload.project_id)
    if payload.status: q=q.where(Record.status==payload.status)
    records=list(db.scalars(q.limit(settings.max_export_records+1)).unique().all())
    if not records: raise HTTPException(404,detail={"code":"EXPORT_RECORDS_EMPTY","message":"当前条件下没有可导出的记录"})
    if len(records)>settings.max_export_records: raise HTTPException(422,detail={"code":"EXPORT_TOO_LARGE","message":f"单次最多导出 {settings.max_export_records} 条记录，请缩小筛选范围"})
    job=ExportJob(creator_id=user.id,template_id=template.id,format="XLSX",filters_json={"record_ids":[record.id for record in records],"project_id":payload.project_id,"status":payload.status.value if payload.status else None},status="PENDING"); db.add(job); db.commit(); db.refresh(job); dispatch_export(job.id,SessionLocal,tasks); return job_out(job)


@router.get("/exports",summary="当前用户导出任务")
def export_jobs(db:Session=Depends(get_db),user:User=Depends(current_user)):
    return [job_out(item) for item in db.scalars(select(ExportJob).where(ExportJob.creator_id==user.id).order_by(ExportJob.created_at.desc()).limit(100)).unique().all()]


@router.get("/exports/{job_id}",summary="导出任务详情")
def export_job(job_id:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    item=db.get(ExportJob,job_id)
    if not item or not can_read_job(item,user): raise HTTPException(404,detail={"code":"EXPORT_JOB_NOT_FOUND","message":"导出任务不存在"})
    return job_out(item)


@router.post("/exports/{job_id}/retry",status_code=202,summary="重试失败或过期的导出任务")
def retry_export(job_id:str,tasks:BackgroundTasks,db:Session=Depends(get_db),user:User=Depends(current_user)):
    item=db.get(ExportJob,job_id)
    if not item or not can_read_job(item,user): raise HTTPException(404,detail={"code":"EXPORT_JOB_NOT_FOUND","message":"导出任务不存在"})
    if item.status not in {"FAILED","EXPIRED"}: raise HTTPException(409,detail={"code":"EXPORT_RETRY_NOT_ALLOWED","message":"只有失败或已过期的任务可以重试"})
    item.status="PENDING"; item.file_key=None; item.filename=None; item.error=None; item.attempt_count=0; item.completed_at=None; item.expires_at=None; db.commit(); dispatch_export(item.id,SessionLocal,tasks); return job_out(item)


@router.post("/exports/maintenance/cleanup",summary="立即清理已过期的导出文件")
def cleanup_exports(_:User=Depends(require_roles(RoleCode.SUPER_ADMIN))):
    return {"cleaned":cleanup_expired_exports(SessionLocal),"retention_days":settings.export_retention_days}


@router.get("/exports/{job_id}/download",summary="下载已完成的 Excel 文件")
def download_export(job_id:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    item=db.get(ExportJob,job_id)
    if not item or not can_read_job(item,user): raise HTTPException(404,detail={"code":"EXPORT_JOB_NOT_FOUND","message":"导出任务不存在"})
    if item.status=="EXPIRED": raise HTTPException(410,detail={"code":"EXPORT_FILE_EXPIRED","message":"导出文件已过期，请重试该任务"})
    if item.status!="COMPLETED" or not item.file_key: raise HTTPException(409,detail={"code":"EXPORT_NOT_READY","message":"导出文件尚未生成完成"})
    try: content=read_export(item.file_key)
    except FileNotFoundError: raise HTTPException(410,detail={"code":"EXPORT_FILE_EXPIRED","message":"导出文件已过期，请重新创建任务"})
    filename=quote(item.filename or "项目记录汇总.xlsx")
    return StreamingResponse(BytesIO(content),media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition":f"attachment; filename=records.xlsx; filename*=UTF-8''{filename}"})
