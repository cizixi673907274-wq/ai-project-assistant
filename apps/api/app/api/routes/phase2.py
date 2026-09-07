from datetime import datetime, timezone
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from urllib.parse import quote

from app.api.deps import can_manage_project, current_user, managed_project_ids, require_roles, role_codes
from app.api.routes.records import get_visible
from app.core.enums import RecordStatus, RoleCode, TaskStatus
from app.db.session import get_db
from app.models.entities import Department, Notification, Project, Record, RecordComment, RecordEvent, RecordTask, ReportExport, User
from app.services.documents import build_project_report

router=APIRouter(tags=["第二阶段"])

class ProjectCreate(BaseModel):
    name:str=Field(min_length=2,max_length=150)
    code:str=Field(min_length=2,max_length=50)
    manager_id:str|None=None
    department_id:str|None=None
    member_ids:list[str]=[]

class ProjectPatch(BaseModel):
    name:str|None=Field(default=None,min_length=2,max_length=150)
    manager_id:str|None=None
    department_id:str|None=None
    status:str|None=Field(default=None,max_length=30)
    member_ids:list[str]|None=None

class CommentCreate(BaseModel): content:str=Field(min_length=1,max_length=3000)
class ReminderCreate(BaseModel): user_ids:list[str]=[]; message:str|None=Field(default=None,max_length=500)
class ReassignCreate(BaseModel): assignee_id:str; due_at:datetime|None=None; note:str|None=Field(default=None,max_length=500)

def task_out(task:RecordTask,record:Record):
    due=task.due_at
    if due and due.tzinfo is None: due=due.replace(tzinfo=timezone.utc)
    overdue=bool(due and due<datetime.now(timezone.utc) and task.status not in {TaskStatus.DONE,TaskStatus.CANCELLED})
    return {"id":task.id,"record_id":record.id,"title":record.title,"summary":record.summary or record.content,"record_status":record.status.value,"priority":record.priority.value,"project_name":record.project.name if record.project else None,"creator_name":record.creator.name,"creator_id":record.creator_id,"task_status":task.status.value,"due_at":task.due_at,"overdue":overdue,"reminder_count":task.reminder_count,"last_reminded_at":task.last_reminded_at,"created_at":task.created_at}

@router.get("/tasks/my",summary="当前用户待办任务")
def my_tasks(include_done:bool=True,db:Session=Depends(get_db),user:User=Depends(current_user)):
    q=select(RecordTask,Record).join(Record,Record.id==RecordTask.record_id).where(RecordTask.assignee_id==user.id,Record.deleted_at.is_(None)).order_by(RecordTask.created_at.desc())
    if not include_done: q=q.where(RecordTask.status.notin_([TaskStatus.DONE,TaskStatus.CANCELLED]))
    return [task_out(task,record) for task,record in db.execute(q).all()]

def notify(db:Session,user_id:str,title:str,content:str,record_id:str|None=None,type:str="SYSTEM"):
    db.add(Notification(user_id=user_id,type=type,title=title,content=content,related_record_id=record_id))

def project_out(db:Session,p:Project):
    total=db.scalar(select(func.count(Record.id)).where(Record.project_id==p.id,Record.deleted_at.is_(None))) or 0
    open_count=db.scalar(select(func.count(Record.id)).where(Record.project_id==p.id,Record.deleted_at.is_(None),Record.status.notin_([RecordStatus.CLOSED,RecordStatus.CANCELLED]))) or 0
    return {"id":p.id,"name":p.name,"code":p.code,"status":p.status,"manager_id":p.manager_id,
            "manager_name":db.get(User,p.manager_id).name if p.manager_id and db.get(User,p.manager_id) else None,
            "department_id":p.department_id,"department_name":db.get(Department,p.department_id).name if p.department_id else None,
            "members":[{"id":u.id,"name":u.name,"username":u.username} for u in p.members],
            "record_count":total,"open_record_count":open_count,"created_at":p.created_at}

@router.get("/projects",summary="项目列表与项目问题统计")
def projects(db:Session=Depends(get_db),user:User=Depends(current_user)):
    scope=managed_project_ids(db,user)
    q=select(Project).where(Project.deleted_at.is_(None))
    if scope is not None:
        if scope:
            q=q.where(Project.id.in_(scope))
        elif RoleCode.ENGINEER in role_codes(user):
            q=q.where(Project.members.any(User.id==user.id))
        else:
            return []
    return [project_out(db,p) for p in db.scalars(q.order_by(Project.created_at.desc())).unique().all()]

@router.post("/projects",status_code=201,summary="创建项目")
def create_project(payload:ProjectCreate,db:Session=Depends(get_db),user:User=Depends(require_roles(RoleCode.PROJECT_MANAGER,RoleCode.DEPARTMENT_HEAD))):
    user_roles=role_codes(user)
    manager_id=payload.manager_id
    if not manager_id:
        manager_id=user.id
    manager=db.get(User,manager_id) if manager_id else None
    if manager_id:
        if not manager:
            raise HTTPException(status_code=404,detail={"code":"MANAGER_NOT_FOUND","message":"负责人不存在"})
        if not ({RoleCode.PROJECT_MANAGER,RoleCode.DEPARTMENT_HEAD} & {r.code for r in manager.roles}):
            raise HTTPException(status_code=422,detail={"code":"INVALID_MANAGER_ROLE","message":"负责人必须是项目负责人角色"})
        if user.department_id and manager.department_id and manager.department_id!=user.department_id:
            raise HTTPException(status_code=422,detail={"code":"INVALID_MANAGER_DEPARTMENT","message":"负责人不属于你的部门"})
    if db.scalar(select(Project).where(Project.code==payload.code)):
        raise HTTPException(409,detail={"code":"PROJECT_CODE_EXISTS","message":"项目编号已存在"})
    if payload.department_id:
        department=db.get(Department,payload.department_id)
        if not department:
            raise HTTPException(status_code=404,detail={"code":"DEPARTMENT_NOT_FOUND","message":"部门不存在"})
        if user.department_id and department.id!=user.department_id:
            raise HTTPException(status_code=422,detail={"code":"INVALID_DEPARTMENT_SCOPE","message":"只能创建所属部门范围内项目"})
        if manager and manager.department_id and manager.department_id!=department.id:
            raise HTTPException(status_code=422,detail={"code":"INVALID_MANAGER_DEPARTMENT","message":"负责人不属于该项目部门"})
        department_id=department.id
    else:
        department_id=manager.department_id if manager else user.department_id
    if not department_id:
        raise HTTPException(status_code=422,detail={"code":"DEPARTMENT_REQUIRED","message":"项目创建需要部门信息"})
    members=list(db.scalars(select(User).where(User.id.in_(payload.member_ids))).unique().all()) if payload.member_ids else []
    if len(members)!=len(set(payload.member_ids)) or any(u.department_id!=user.department_id or RoleCode.ENGINEER not in role_codes(u) for u in members):
        raise HTTPException(status_code=422,detail={"code":"INVALID_PROJECT_MEMBERS","message":"项目成员只能选择本团队工程师"})
    p=Project(name=payload.name,code=payload.code,manager_id=manager_id,department_id=department_id,members=members)
    db.add(p); db.commit(); db.refresh(p); return project_out(db,p)

@router.patch("/projects/{id}",summary="编辑项目与成员")
def patch_project(id:str,payload:ProjectPatch,db:Session=Depends(get_db),user:User=Depends(require_roles(RoleCode.PROJECT_MANAGER,RoleCode.DEPARTMENT_HEAD))):
    p=db.scalar(select(Project).where(Project.id==id,Project.deleted_at.is_(None)))
    user_roles=role_codes(user)
    if not p: raise HTTPException(404,detail={"code":"PROJECT_NOT_FOUND","message":"项目不存在"})
    if not can_manage_project(user,p): raise HTTPException(status_code=403,detail={"code":"FORBIDDEN","message":"仅管理员或项目负责人可编辑该项目"})
    if payload.department_id:
        department=db.get(Department,payload.department_id)
        if not department: raise HTTPException(status_code=404,detail={"code":"DEPARTMENT_NOT_FOUND","message":"部门不存在"})
        if {RoleCode.DEPARTMENT_HEAD} & user_roles and department.id!=p.department_id and user.department_id!=department.id:
            raise HTTPException(status_code=422,detail={"code":"INVALID_DEPARTMENT_SCOPE","message":"项目主管仅可维护所属部门项目"})
        if payload.manager_id:
            manager_by_payload=db.get(User,payload.manager_id)
            if manager_by_payload and manager_by_payload.department_id and payload.department_id!=manager_by_payload.department_id:
                raise HTTPException(status_code=422,detail={"code":"INVALID_MANAGER_DEPARTMENT","message":"负责人不属于该项目部门"})
    if payload.manager_id is not None and payload.manager_id:
        manager=db.get(User,payload.manager_id)
        if not manager:
            raise HTTPException(status_code=404,detail={"code":"MANAGER_NOT_FOUND","message":"负责人不存在"})
        if not ({RoleCode.PROJECT_MANAGER,RoleCode.DEPARTMENT_HEAD} & {r.code for r in manager.roles}):
            raise HTTPException(status_code=422,detail={"code":"INVALID_MANAGER_ROLE","message":"负责人必须是项目负责人角色"})
        if {RoleCode.DEPARTMENT_HEAD} & user_roles and manager.department_id and user.department_id and manager.department_id!=user.department_id:
            raise HTTPException(status_code=422,detail={"code":"INVALID_MANAGER_DEPARTMENT","message":"项目主管仅可选本部门负责人"})
    values=payload.model_dump(exclude_unset=True,exclude={"member_ids"})
    for key,value in values.items(): setattr(p,key,value)
    if payload.member_ids is not None:
        members=list(db.scalars(select(User).where(User.id.in_(payload.member_ids))).unique().all())
        if len(members)!=len(set(payload.member_ids)) or any(u.department_id!=user.department_id or RoleCode.ENGINEER not in role_codes(u) for u in members):
            raise HTTPException(status_code=422,detail={"code":"INVALID_PROJECT_MEMBERS","message":"项目成员只能选择本团队工程师"})
        p.members=members
    if payload.manager_id is not None and payload.manager_id and manager and manager.department_id:
        p.department_id=manager.department_id
    db.commit(); return project_out(db,p)

@router.delete("/projects/{id}",summary="删除空项目（软删除）")
def delete_project(id:str,db:Session=Depends(get_db),user:User=Depends(require_roles(RoleCode.PROJECT_MANAGER,RoleCode.DEPARTMENT_HEAD))):
    p=db.scalar(select(Project).where(Project.id==id,Project.deleted_at.is_(None)))
    if not p: raise HTTPException(404,detail={"code":"PROJECT_NOT_FOUND","message":"项目不存在"})
    if not can_manage_project(user,p): raise HTTPException(status_code=403,detail={"code":"FORBIDDEN","message":"仅管理员或项目负责人可删除该项目"})
    record_count=db.scalar(select(func.count(Record.id)).where(Record.project_id==p.id,Record.deleted_at.is_(None))) or 0
    if record_count: raise HTTPException(409,detail={"code":"PROJECT_HAS_RECORDS","message":f"该项目仍有 {record_count} 条有效记录，请先删除或迁移记录"})
    p.deleted_at=datetime.now(timezone.utc); p.status="DELETED"; db.commit(); return {"id":p.id,"deleted":True}

def notification_out(n:Notification):
    return {"id":n.id,"type":n.type,"title":n.title,"content":n.content,"related_record_id":n.related_record_id,"is_read":n.is_read,"read_at":n.read_at,"created_at":n.created_at}

@router.get("/notifications",summary="当前用户通知")
def notifications(unread_only:bool=False,db:Session=Depends(get_db),user:User=Depends(current_user)):
    q=select(Notification).where(Notification.user_id==user.id).order_by(Notification.created_at.desc())
    if unread_only: q=q.where(Notification.is_read.is_(False))
    return [notification_out(n) for n in db.scalars(q).all()]

@router.get("/notifications/unread-count",summary="未读通知数量")
def unread_count(db:Session=Depends(get_db),user:User=Depends(current_user)):
    return {"count":db.scalar(select(func.count(Notification.id)).where(Notification.user_id==user.id,Notification.is_read.is_(False))) or 0}

@router.post("/notifications/read-all",summary="全部标记已读")
def read_all(db:Session=Depends(get_db),user:User=Depends(current_user)):
    now=datetime.now(timezone.utc); items=db.scalars(select(Notification).where(Notification.user_id==user.id,Notification.is_read.is_(False))).all()
    for n in items: n.is_read=True; n.read_at=now
    db.commit(); return {"updated":len(items)}

@router.patch("/notifications/{id}/read",summary="通知标记已读")
def read_notification(id:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    n=db.scalar(select(Notification).where(Notification.id==id,Notification.user_id==user.id))
    if not n: raise HTTPException(404,detail={"code":"NOTIFICATION_NOT_FOUND","message":"通知不存在"})
    n.is_read=True; n.read_at=datetime.now(timezone.utc); db.commit(); return notification_out(n)

@router.get("/records/{record_id}/comments",summary="记录协作评论")
def comments(record_id:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    get_visible(db,record_id,user)
    return [{"id":c.id,"content":c.content,"kind":c.kind,"author_id":c.author_id,"author_name":c.author.name,"created_at":c.created_at} for c in db.scalars(select(RecordComment).where(RecordComment.record_id==record_id).order_by(RecordComment.created_at)).all()]

@router.post("/records/{record_id}/comments",status_code=201,summary="添加协作评论")
def add_comment(record_id:str,payload:CommentCreate,db:Session=Depends(get_db),user:User=Depends(current_user)):
    record=get_visible(db,record_id,user); c=RecordComment(record_id=record.id,author_id=user.id,content=payload.content); db.add(c)
    db.add(RecordEvent(record_id=record.id,actor_id=user.id,event_type="COMMENT_ADDED",after_json={"content":payload.content}))
    db.commit(); db.refresh(c); return {"id":c.id,"content":c.content,"kind":c.kind,"author_id":user.id,"author_name":user.name,"created_at":c.created_at}

@router.post("/records/{record_id}/remind",summary="催办记录责任人")
def remind(record_id:str,payload:ReminderCreate,db:Session=Depends(get_db),user:User=Depends(require_roles(RoleCode.PROJECT_MANAGER,RoleCode.DEPARTMENT_HEAD,RoleCode.SUPER_ADMIN))):
    record=get_visible(db,record_id,user); target_ids=payload.user_ids; task=None
    if {RoleCode.PROJECT_MANAGER,RoleCode.DEPARTMENT_HEAD} & role_codes(user) and not can_manage_project(user,record.project):
        raise HTTPException(status_code=403,detail={"code":"FORBIDDEN","message":"仅项目负责人可催办该项目记录"})
    if not target_ids:
        task=db.scalar(select(RecordTask).where(RecordTask.record_id==record.id,RecordTask.status.in_([TaskStatus.PENDING,TaskStatus.IN_PROGRESS])).order_by(RecordTask.created_at.desc()))
        target_ids=[task.assignee_id] if task else []
    if not target_ids: raise HTTPException(409,detail={"code":"NO_REMINDER_TARGET","message":"当前记录没有可催办的责任人"})
    message=payload.message or f"{user.name} 提醒你及时处理《{record.title}》"
    for uid in set(target_ids): notify(db,uid,"记录催办",message,record.id,"REMINDER")
    if task: task.reminder_count+=1; task.last_reminded_at=datetime.now(timezone.utc)
    db.add(RecordComment(record_id=record.id,author_id=user.id,content=message,kind="REMINDER")); db.add(RecordEvent(record_id=record.id,actor_id=user.id,event_type="RECORD_REMINDED",after_json={"user_ids":target_ids,"message":message})); db.commit()
    return {"notified":len(set(target_ids))}

@router.post("/records/{record_id}/reassign",summary="转派记录责任人")
def reassign(record_id:str,payload:ReassignCreate,db:Session=Depends(get_db),user:User=Depends(require_roles(RoleCode.PROJECT_MANAGER,RoleCode.DEPARTMENT_HEAD,RoleCode.SUPER_ADMIN))):
    record=get_visible(db,record_id,user); assignee=db.get(User,payload.assignee_id)
    if {RoleCode.PROJECT_MANAGER,RoleCode.DEPARTMENT_HEAD} & role_codes(user) and not can_manage_project(user,record.project):
        raise HTTPException(status_code=403,detail={"code":"FORBIDDEN","message":"仅项目负责人可转派该项目记录"})
    if not assignee: raise HTTPException(404,detail={"code":"ASSIGNEE_NOT_FOUND","message":"责任人不存在"})
    previous=db.scalar(select(RecordTask).where(RecordTask.record_id==record.id,RecordTask.status.in_([TaskStatus.PENDING,TaskStatus.IN_PROGRESS])).order_by(RecordTask.created_at.desc()))
    if previous: previous.status=TaskStatus.CANCELLED
    db.add(RecordTask(record_id=record.id,assignee_id=assignee.id,department_id=assignee.department_id,due_at=payload.due_at))
    record.status=RecordStatus.ASSIGNED
    note=payload.note or f"已转派给{assignee.name}"
    db.add(RecordEvent(record_id=record.id,actor_id=user.id,event_type="RECORD_REASSIGNED",before_json={"assignee_id":previous.assignee_id if previous else None},after_json={"assignee_id":assignee.id,"note":note}))
    notify(db,assignee.id,"新的项目记录待处理",f"{user.name} 将《{record.title}》转派给你。{note}",record.id,"ASSIGNMENT"); db.commit()
    return {"record_id":record.id,"assignee_id":assignee.id,"assignee_name":assignee.name,"status":record.status.value}

def report_export_out(item:ReportExport):
    return {"id":item.id,"project_id":item.project_id,"project_name":item.project.name,"format":item.format,"status":item.status,"filename":item.filename,"record_count":item.record_count,"generated_by":item.user.name,"completed_at":item.completed_at,"created_at":item.created_at}

@router.get("/reports/overview",summary="项目报告中心概览")
def report_overview(project_id:str|None=None,db:Session=Depends(get_db),user:User=Depends(current_user)):
    scope=managed_project_ids(db,user)
    project_query=select(Project).where(Project.deleted_at.is_(None))
    if scope is not None:
        if not scope:
            return {"project_id":project_id,"project_count":0,"record_count":0,"open_count":0,"closed_count":0,"high_risk_count":0,"completion_rate":100,"projects":[],"recent_records":[]}
        project_query=project_query.where(Project.id.in_(scope))
    if project_id:
        if scope is not None and project_id not in scope:
            raise HTTPException(status_code=404,detail={"code":"PROJECT_NOT_FOUND","message":"项目不存在"})
        if not db.scalar(select(Project.id).where(Project.id==project_id,Project.deleted_at.is_(None))): raise HTTPException(status_code=404,detail={"code":"PROJECT_NOT_FOUND","message":"项目不存在"})
    projects=list(db.scalars(project_query.order_by(Project.created_at.desc())).unique().all())
    q=select(Record).where(Record.deleted_at.is_(None)).order_by(Record.created_at.desc())
    if scope is not None and scope:
        q=q.where(Record.project_id.in_(scope))
    if project_id: q=q.where(Record.project_id==project_id)
    records=list(db.scalars(q).unique().all())
    closed=sum(r.status in {RecordStatus.CLOSED,RecordStatus.CANCELLED} for r in records)
    high=sum(r.priority.value in {"HIGH","URGENT"} and r.status not in {RecordStatus.CLOSED,RecordStatus.CANCELLED} for r in records)
    return {"project_id":project_id,"project_count":len(projects),"record_count":len(records),"open_count":len(records)-closed,"closed_count":closed,"high_risk_count":high,"completion_rate":round(closed/len(records)*100) if records else 100,"projects":[project_out(db,p) for p in projects],"recent_records":[{"id":r.id,"title":r.title,"project_name":r.project.name if r.project else "未关联项目","status":r.status.value,"priority":r.priority.value,"created_at":r.created_at} for r in records[:8]]}

@router.get("/reports/exports",summary="报告导出历史")
def report_exports(project_id:str|None=None,db:Session=Depends(get_db),user:User=Depends(current_user)):
    scope=managed_project_ids(db,user)
    q=select(ReportExport).order_by(ReportExport.created_at.desc()).limit(100)
    if scope is not None:
        if not scope:
            return []
        q=q.where(ReportExport.project_id.in_(scope))
    if project_id: q=q.where(ReportExport.project_id==project_id)
    if project_id and scope is not None and project_id not in scope:
        raise HTTPException(status_code=404,detail={"code":"PROJECT_NOT_FOUND","message":"项目不存在"})
    return [report_export_out(item) for item in db.scalars(q).unique().all()]

@router.post("/reports/projects/{project_id}/export",summary="导出研发项目闭环 Word 报告")
def export_project_report(project_id:str,db:Session=Depends(get_db),user:User=Depends(require_roles(RoleCode.PROJECT_MANAGER,RoleCode.DEPARTMENT_HEAD,RoleCode.SUPER_ADMIN))):
    project=db.scalar(select(Project).where(Project.id==project_id,Project.deleted_at.is_(None)))
    if not project: raise HTTPException(404,detail={"code":"PROJECT_NOT_FOUND","message":"项目不存在"})
    if {RoleCode.PROJECT_MANAGER,RoleCode.DEPARTMENT_HEAD} & role_codes(user) and not can_manage_project(user,project):
        raise HTTPException(status_code=403,detail={"code":"FORBIDDEN","message":"仅项目负责人可导出该项目报告"})
    records=list(db.scalars(select(Record).where(Record.project_id==project.id,Record.deleted_at.is_(None)).order_by(Record.created_at.desc())).unique().all())
    tasks=list(db.scalars(select(RecordTask).where(RecordTask.record_id.in_([r.id for r in records]))).unique().all()) if records else []
    tasks_by_record={record.id:[] for record in records}
    for task in tasks: tasks_by_record.setdefault(task.record_id,[]).append(task)
    for record in records: record.report_tasks=tasks_by_record.get(record.id,[])
    now=datetime.now(timezone.utc); filename=f"{project.code}-{project.name}-研发问题闭环报告-{now:%Y%m%d}.docx"
    output=build_project_report(project,records,user.name,now)
    db.add(ReportExport(user_id=user.id,project_id=project.id,format="DOCX",status="COMPLETED",filename=filename,record_count=len(records),filters_json={"project_id":project.id},completed_at=now)); db.commit()
    encoded=quote(filename)
    return StreamingResponse(output,media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",headers={"Content-Disposition":f"attachment; filename=project-report.docx; filename*=UTF-8''{encoded}"})

@router.post("/tasks/scan-overdue",summary="扫描逾期任务并生成通知")
def scan_overdue(db:Session=Depends(get_db),user:User=Depends(require_roles(RoleCode.PROJECT_MANAGER,RoleCode.DEPARTMENT_HEAD,RoleCode.SUPER_ADMIN))):
    now=datetime.now(timezone.utc); start=now.replace(hour=0,minute=0,second=0,microsecond=0); created=0
    task_query=select(RecordTask).join(Record,RecordTask.record_id==Record.id).where(Record.deleted_at.is_(None),RecordTask.due_at.is_not(None),RecordTask.status.in_([TaskStatus.PENDING,TaskStatus.IN_PROGRESS]))
    scope=managed_project_ids(db,user)
    if scope is not None:
        if not scope: return {"scanned":0,"notifications_created":0,"scanned_by":user.name}
        task_query=task_query.where(Record.project_id.in_(scope))
    tasks=list(db.scalars(task_query).all())
    for task in tasks:
        due=task.due_at.replace(tzinfo=timezone.utc) if task.due_at and task.due_at.tzinfo is None else task.due_at
        if not due or due>=now: continue
        exists=db.scalar(select(Notification.id).where(Notification.user_id==task.assignee_id,Notification.related_record_id==task.record_id,Notification.type=="OVERDUE",Notification.created_at>=start))
        if exists: continue
        record=db.get(Record,task.record_id)
        notify(db,task.assignee_id,"任务已逾期",f"《{record.title if record else '项目记录'}》已超过截止时间，请尽快处理。",task.record_id,"OVERDUE")
        task.reminder_count+=1; task.last_reminded_at=now; created+=1
    db.commit(); return {"scanned":len(tasks),"notifications_created":created,"scanned_by":user.name}
