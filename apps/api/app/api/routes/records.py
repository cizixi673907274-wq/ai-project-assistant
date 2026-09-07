from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from urllib.parse import quote
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from app.api.deps import can_manage_project, current_user, is_admin, managed_project_ids, require_roles, role_codes
from app.core.enums import Priority, RecordStatus, RoleCode, TaskStatus
from app.db.session import SessionLocal, get_db
from app.models.entities import AIAnalysis, Notification, Project, Record, RecordEvent, RecordTask, User
from app.schemas.records import AIConfirm, AssignRequest, CloseRequest, ProcessRequest, RecordCreate, RecordUpdate
from app.services.records import event, run_analysis, transition
from app.services.documents import build_record_document, build_records_table_document
router=APIRouter(prefix="/records",tags=["记录闭环"])
class BatchExportRequest(BaseModel): record_ids:list[str]
class ManagerRecordCreate(BaseModel):
 title:str=Field(min_length=1,max_length=200)
 content:str=Field(min_length=1,max_length=10000)
 project_id:str
 assignee_id:str
 priority:Priority=Priority.MEDIUM
 due_at:datetime|None=None
def visible_query(db:Session,user:User):
    q=select(Record).where(Record.deleted_at.is_(None)).order_by(Record.created_at.desc())
    roles=role_codes(user)
    if {RoleCode.PROJECT_MANAGER,RoleCode.DEPARTMENT_HEAD} & roles:
        managed_ids=managed_project_ids(db,user)
        team_creator=Record.creator.has(User.department_id==user.department_id) if user.department_id else Record.creator_id==user.id
        conditions=[team_creator,Record.creator_id==user.id]
        if managed_ids: conditions.append(Record.project_id.in_(managed_ids))
        q=q.outerjoin(RecordTask,RecordTask.record_id==Record.id).where(or_(*conditions,RecordTask.assignee_id==user.id)).distinct()
    elif RoleCode.SUPER_ADMIN not in roles:
        q=q.outerjoin(RecordTask,RecordTask.record_id==Record.id).where(or_(Record.creator_id==user.id,RecordTask.assignee_id==user.id)).distinct()
    return q

def ensure_project_manager_scope(user:User,record:Record):
    roles=role_codes(user)
    if not record.project:
        return
    if {RoleCode.PROJECT_MANAGER,RoleCode.DEPARTMENT_HEAD} & roles and not can_manage_project(user,record.project):
        raise HTTPException(status_code=403,detail={"code":"FORBIDDEN","message":"仅管理员或当前项目负责人可执行该操作"})

def get_visible(db:Session,id:str,user:User):
 record=db.scalar(visible_query(db,user).where(Record.id==id))
 if not record: raise HTTPException(status_code=404,detail={"code":"RECORD_NOT_FOUND","message":"记录不存在或无权查看"})
 return record
def serialize(r:Record):
 return {"id":r.id,"title":r.title,"content":r.content,"summary":r.summary,"status":r.status,"priority":r.priority,"project_id":r.project_id,"project_name":r.project.name if r.project else None,"creator_id":r.creator_id,"creator_name":r.creator.name,"category_snapshot":r.category_snapshot,"stage_snapshot":r.stage_snapshot,"product_snapshot":r.product_snapshot,"confidence":r.analyses[-1].confidence if r.analyses else None,"media":[{"id":m.id,"type":m.type.value,"original_name":m.original_name,"mime":m.mime,"size":m.size,"transcript":m.transcript,"extracted_text":m.extracted_text,"created_at":m.created_at} for m in r.media],"created_at":r.created_at,"updated_at":r.updated_at}
@router.post("",status_code=201,summary="创建研发记录草稿")
def create(payload:RecordCreate,db:Session=Depends(get_db),user:User=Depends(current_user)):
 if payload.project_id:
  project=db.scalar(select(Project).where(Project.id==payload.project_id,Project.deleted_at.is_(None)))
  if not project: raise HTTPException(404,detail={"code":"PROJECT_NOT_FOUND","message":"项目不存在"})
  roles=role_codes(user)
  supervisor_forbidden={RoleCode.PROJECT_MANAGER,RoleCode.DEPARTMENT_HEAD} & roles and not can_manage_project(user,project)
  engineer_forbidden=RoleCode.ENGINEER in roles and not any(member.id==user.id for member in project.members)
  if supervisor_forbidden or engineer_forbidden:
   raise HTTPException(403,detail={"code":"PROJECT_SCOPE_FORBIDDEN","message":"只能在自己参与或管理的项目中创建记录"})
 r=Record(creator_id=user.id,project_id=payload.project_id,title=payload.title or "待AI生成标题",content=payload.content,priority=payload.priority); db.add(r); db.flush(); event(db,r,user.id,"RECORD_CREATED",after={"status":r.status.value}); db.commit(); db.refresh(r); return serialize(r)

@router.post("/manager-create",status_code=201,summary="主管直接创建并分派人工任务记录")
def manager_create(payload:ManagerRecordCreate,db:Session=Depends(get_db),user:User=Depends(require_roles(RoleCode.PROJECT_MANAGER,RoleCode.DEPARTMENT_HEAD))):
 project=db.scalar(select(Project).where(Project.id==payload.project_id,Project.deleted_at.is_(None)))
 if not project or not can_manage_project(user,project):
  raise HTTPException(403,detail={"code":"PROJECT_SCOPE_FORBIDDEN","message":"只能为自己管理的项目创建记录"})
 assignee=db.get(User,payload.assignee_id)
 if not assignee or RoleCode.ENGINEER not in role_codes(assignee):
  raise HTTPException(422,detail={"code":"INVALID_ASSIGNEE","message":"责任人必须是工程师"})
 if not user.department_id or assignee.department_id!=user.department_id:
  raise HTTPException(403,detail={"code":"ASSIGNEE_SCOPE_FORBIDDEN","message":"只能分派给本团队工程师"})
 r=Record(creator_id=user.id,project_id=project.id,title=payload.title,content=payload.content,priority=payload.priority,status=RecordStatus.ASSIGNED)
 db.add(r); db.flush()
 event(db,r,user.id,"RECORD_CREATED",after={"source":"PC_MANAGER","status":RecordStatus.ASSIGNED.value})
 event(db,r,user.id,"RECORD_ASSIGNED",after={"assignee_id":assignee.id,"ai_skipped":True})
 db.add(RecordTask(record_id=r.id,assignee_id=assignee.id,department_id=assignee.department_id,due_at=payload.due_at))
 db.add(Notification(user_id=assignee.id,type="ASSIGNMENT",title="新的项目记录待处理",content=f"{user.name} 将《{r.title}》分派给你",related_record_id=r.id))
 db.commit(); db.refresh(r); return serialize(r)
@router.get("",summary="按权限查询记录")
def list_records(status:RecordStatus|None=None,keyword:str|None=None,db:Session=Depends(get_db),user:User=Depends(current_user)):
 q=visible_query(db,user); q=q.where(Record.status==status) if status else q; q=q.where(or_(Record.title.contains(keyword),Record.content.contains(keyword))) if keyword else q
 return [serialize(x) for x in db.scalars(q).unique().all()]
@router.get("/summary",summary="当前用户记录统计")
def records_summary(db:Session=Depends(get_db),user:User=Depends(current_user)):
 q=visible_query(db,user).subquery()
 total=db.scalar(select(func.count()).select_from(q)) or 0
 created=db.scalar(select(func.count()).select_from(q).where(q.c.creator_id==user.id)) or 0
 drafts=db.scalar(select(func.count()).select_from(q).where(q.c.status==RecordStatus.DRAFT)) or 0
 return {"total":total,"created":created,"drafts":drafts}
@router.post("/batch-export",summary="批量导出记录 Word 汇总表")
def batch_export(payload:BatchExportRequest,db:Session=Depends(get_db),user:User=Depends(current_user)):
 if not payload.record_ids: raise HTTPException(422,detail={"code":"RECORD_IDS_REQUIRED","message":"请至少选择一条记录"})
 records=list(db.scalars(visible_query(db,user).where(Record.id.in_(payload.record_ids))).unique().all())
 by_id={r.id:r for r in records}; ordered=[by_id[id] for id in payload.record_ids if id in by_id]
 if not ordered: raise HTTPException(404,detail={"code":"RECORD_NOT_FOUND","message":"未找到可导出的记录"})
 stream=build_records_table_document(ordered); filename=quote(f"研发记录批量汇总-{datetime.now().strftime('%Y%m%d-%H%M')}.docx")
 return StreamingResponse(stream,media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",headers={"Content-Disposition":f"attachment; filename*=UTF-8''{filename}"})
@router.get("/{id}",summary="记录详情")
def detail(id:str,db:Session=Depends(get_db),user:User=Depends(current_user)): return serialize(get_visible(db,id,user))
@router.get("/{id}/events",summary="记录流转与审计事件")
def events(id:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
 get_visible(db,id,user); return [{"id":e.id,"event_type":e.event_type,"actor_id":e.actor_id,"before":e.before_json,"after":e.after_json,"created_at":e.created_at} for e in db.scalars(select(RecordEvent).where(RecordEvent.record_id==id).order_by(RecordEvent.created_at)).all()]
@router.get("/{id}/export",summary="导出记录为 Word 文档")
def export_record(id:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
 r=get_visible(db,id,user)
 events=list(db.scalars(select(RecordEvent).where(RecordEvent.record_id==id).order_by(RecordEvent.created_at)).all())
 task=db.scalar(select(RecordTask).where(RecordTask.record_id==id).order_by(RecordTask.created_at.desc()))
 actor_ids={e.actor_id for e in events if e.actor_id}; actors={u.id:u.name for u in db.scalars(select(User).where(User.id.in_(actor_ids))).all()} if actor_ids else {}
 stream=build_record_document(r,events,actors,task); filename=quote(f"研发记录-{r.title[:40]}.docx")
 return StreamingResponse(stream,media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",headers={"Content-Disposition":f"attachment; filename*=UTF-8''{filename}"})
@router.patch("/{id}",summary="编辑草稿")
def update(id:str,payload:RecordUpdate,db:Session=Depends(get_db),user:User=Depends(current_user)):
 r=get_visible(db,id,user)
 if r.creator_id!=user.id and not is_admin(user): raise HTTPException(403,detail={"code":"FORBIDDEN","message":"仅创建人可编辑"})
 if r.status not in {RecordStatus.DRAFT,RecordStatus.WAITING_SUPPLEMENT}: raise HTTPException(409,detail={"code":"RECORD_STATUS_INVALID","message":"当前状态不能编辑"})
 for k,v in payload.model_dump(exclude_unset=True).items(): setattr(r,k,v)
 event(db,r,user.id,"RECORD_UPDATED",after=payload.model_dump(mode="json",exclude_unset=True)); db.commit(); return serialize(r)
@router.delete("/{id}",summary="删除记录（软删除）")
def delete_record(id:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
 r=get_visible(db,id,user)
 roles={role.code for role in user.roles}; can_manage=bool(roles&{RoleCode.PROJECT_MANAGER,RoleCode.DEPARTMENT_HEAD,RoleCode.SUPER_ADMIN}); can_delete_draft=r.creator_id==user.id and r.status in {RecordStatus.DRAFT,RecordStatus.WAITING_SUPPLEMENT}
 if {RoleCode.PROJECT_MANAGER,RoleCode.DEPARTMENT_HEAD} & roles and not can_manage_project(user,r.project): can_manage=False
 if not can_manage and not can_delete_draft: raise HTTPException(403,detail={"code":"FORBIDDEN","message":"仅创建人可删除自己的草稿，项目经理或超级管理员可删除其他记录"})
 event(db,r,user.id,"RECORD_DELETED",before={"status":r.status.value,"title":r.title})
 r.deleted_at=datetime.now(timezone.utc); db.commit(); return {"id":r.id,"deleted":True}
@router.post("/{id}/submit",summary="提交并异步触发 AI 分析")
def submit(id:str,tasks:BackgroundTasks,request:Request,db:Session=Depends(get_db),user:User=Depends(current_user)):
 r=get_visible(db,id,user)
 if r.creator_id!=user.id: raise HTTPException(403,detail={"code":"FORBIDDEN","message":"仅创建人可提交"})
 transition(db,r,RecordStatus.SUBMITTED,user.id,"RECORD_SUBMITTED",getattr(request.state,"request_id",None)); db.commit(); tasks.add_task(run_analysis,r.id,SessionLocal); return serialize(r)
@router.post("/{id}/ai/retry",summary="重新运行 AI")
def retry(id:str,tasks:BackgroundTasks,db:Session=Depends(get_db),user:User=Depends(require_roles(RoleCode.PROJECT_MANAGER,RoleCode.DEPARTMENT_HEAD,RoleCode.SUPER_ADMIN))):
 r=get_visible(db,id,user); ensure_project_manager_scope(user,r)
 if r.status==RecordStatus.AI_REVIEW_REQUIRED: r.status=RecordStatus.WAITING_SUPPLEMENT
 tasks.add_task(run_analysis,r.id,SessionLocal); db.commit(); return serialize(r)
@router.post("/{id}/ai/confirm",summary="确认或修正 AI 结果")
def confirm(id:str,payload:AIConfirm,db:Session=Depends(get_db),user:User=Depends(require_roles(RoleCode.PROJECT_MANAGER,RoleCode.DEPARTMENT_HEAD,RoleCode.SUPER_ADMIN))):
 r=get_visible(db,id,user); ensure_project_manager_scope(user,r)
 if r.status==RecordStatus.AI_REVIEW_REQUIRED: transition(db,r,RecordStatus.READY_TO_ASSIGN,user.id,"AI_CONFIRMED")
 elif r.status!=RecordStatus.READY_TO_ASSIGN: raise HTTPException(409,detail={"code":"RECORD_STATUS_INVALID","message":"当前记录无需确认"})
 values=payload.model_dump(exclude_unset=True); mapping={"category":"category_snapshot","stage":"stage_snapshot","product":"product_snapshot","department_id":"assigned_department_id"}
 for k,v in values.items(): setattr(r,mapping.get(k,k),v)
 if r.analyses: r.analyses[-1].confirmed=True
 event(db,r,user.id,"AI_RESULT_EDITED",after=payload.model_dump(mode="json",exclude_unset=True)); db.commit(); return serialize(r)
@router.post("/{id}/assign",summary="分派责任人")
def assign(id:str,payload:AssignRequest,db:Session=Depends(get_db),user:User=Depends(require_roles(RoleCode.PROJECT_MANAGER,RoleCode.DEPARTMENT_HEAD,RoleCode.SUPER_ADMIN))):
 r=get_visible(db,id,user); ensure_project_manager_scope(user,r); assignee=db.get(User,payload.assignee_id)
 if not assignee: raise HTTPException(404,detail={"code":"ASSIGNEE_NOT_FOUND","message":"责任人不存在"})
 if RoleCode.ENGINEER not in role_codes(assignee): raise HTTPException(422,detail={"code":"INVALID_ASSIGNEE","message":"责任人必须是工程师"})
 if RoleCode.SUPER_ADMIN not in role_codes(user) and assignee.department_id!=user.department_id: raise HTTPException(403,detail={"code":"ASSIGNEE_SCOPE_FORBIDDEN","message":"只能分派给本团队工程师"})
 transition(db,r,RecordStatus.ASSIGNED,user.id,"RECORD_ASSIGNED"); db.add(RecordTask(record_id=r.id,assignee_id=payload.assignee_id,department_id=payload.department_id,due_at=payload.due_at)); db.add(Notification(user_id=assignee.id,type="ASSIGNMENT",title="新的项目记录待处理",content=f"{user.name} 将《{r.title}》分派给你",related_record_id=r.id)); db.commit(); return serialize(r)
@router.post("/{id}/process",summary="责任人开始处理并回复")
def process(id:str,payload:ProcessRequest,db:Session=Depends(get_db),user:User=Depends(current_user)):
 r=get_visible(db,id,user); task=db.scalar(select(RecordTask).where(RecordTask.record_id==id,RecordTask.assignee_id==user.id).order_by(RecordTask.created_at.desc()))
 if not task and not is_admin(user): raise HTTPException(403,detail={"code":"FORBIDDEN","message":"仅当前责任人可处理"})
 if r.status==RecordStatus.ASSIGNED: transition(db,r,RecordStatus.IN_PROGRESS,user.id,"PROCESS_STARTED")
 if task: task.status=TaskStatus.IN_PROGRESS; task.response=payload.response
 event(db,r,user.id,"PROCESS_COMMENTED",after={"response":payload.response}); db.commit(); return serialize(r)
@router.post("/{id}/resolve",summary="标记处理完成")
def resolve(id:str,payload:ProcessRequest,db:Session=Depends(get_db),user:User=Depends(current_user)):
 r=get_visible(db,id,user); task=db.scalar(select(RecordTask).where(RecordTask.record_id==id,RecordTask.assignee_id==user.id).order_by(RecordTask.created_at.desc()))
 if not task and not is_admin(user): raise HTTPException(403,detail={"code":"FORBIDDEN","message":"仅责任人可标记解决"})
 if r.status==RecordStatus.ASSIGNED: transition(db,r,RecordStatus.IN_PROGRESS,user.id,"PROCESS_STARTED")
 transition(db,r,RecordStatus.RESOLVED,user.id,"RECORD_RESOLVED");
 if task: task.status=TaskStatus.DONE; task.response=payload.response
 db.commit(); return serialize(r)
@router.post("/{id}/close",summary="项目经理关闭记录")
def close(id:str,payload:CloseRequest,db:Session=Depends(get_db),user:User=Depends(require_roles(RoleCode.PROJECT_MANAGER,RoleCode.DEPARTMENT_HEAD,RoleCode.SUPER_ADMIN))):
 r=get_visible(db,id,user); ensure_project_manager_scope(user,r); transition(db,r,RecordStatus.CLOSED,user.id,"RECORD_CLOSED"); event(db,r,user.id,"CLOSE_NOTE",after={"note":payload.note}); db.commit(); return serialize(r)
