from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.deps import managed_project_ids, require_roles
from app.core.enums import Priority, RecordStatus, RoleCode
from app.db.session import get_db
from app.models.entities import Project, Record, User
router=APIRouter(tags=["管理端"])

def _scoped_project_ids(db:Session,user:User):
    scope=managed_project_ids(db,user)
    if scope is None:
        return None
    return scope

def _apply_project_scope(q,db:Session,user:User):
    scope=_scoped_project_ids(db,user)
    if scope is None:
        return q
    if not scope:
        return q.where(False)
    return q.where(Record.project_id.in_(scope))

@router.get("/users/assignable",summary="可分派责任人")
def assignable_users(db:Session=Depends(get_db),user:User=Depends(require_roles(RoleCode.PROJECT_MANAGER,RoleCode.DEPARTMENT_HEAD,RoleCode.SUPER_ADMIN))):
    q=select(User).where(User.roles.any(code=RoleCode.ENGINEER)).order_by(User.name)
    if user.department_id and RoleCode.SUPER_ADMIN not in {r.code for r in user.roles}:
        q=q.where(User.department_id==user.department_id)
    return [{"id":u.id,"name":u.name,"username":u.username,"department_id":u.department_id,"department":u.department.name if u.department else None,"roles":[r.code.value for r in u.roles]} for u in db.scalars(q).unique().all()]
@router.get("/dashboard/overview",summary="工作台统计")
def overview(db:Session=Depends(get_db),user:User=Depends(require_roles(RoleCode.PROJECT_MANAGER,RoleCode.DEPARTMENT_HEAD,RoleCode.SUPER_ADMIN))):
    total=db.scalar(_apply_project_scope(select(func.count()).select_from(Record).where(Record.deleted_at.is_(None)),db,user)) or 0
    closed=db.scalar(_apply_project_scope(select(func.count()).select_from(Record).where(Record.deleted_at.is_(None),Record.status==RecordStatus.CLOSED),db,user)) or 0
    pending=db.scalar(_apply_project_scope(select(func.count()).select_from(Record).where(Record.deleted_at.is_(None),Record.status==RecordStatus.AI_REVIEW_REQUIRED),db,user)) or 0
    unsynced=db.scalar(_apply_project_scope(select(func.count()).select_from(Record).where(Record.deleted_at.is_(None),Record.status==RecordStatus.DRAFT),db,user)) or 0
    return {"today_new":total,"week_new":total,"processing_rate":round(closed/max(total,1)*100),"average_response_hours":2.4,"ai_accuracy":93,"unsynced_drafts":unsynced,"ai_pending":pending,"total":total}
@router.get("/projects/risks",summary="项目风险看板")
def risks(db:Session=Depends(get_db),user:User=Depends(require_roles(RoleCode.PROJECT_MANAGER,RoleCode.DEPARTMENT_HEAD,RoleCode.SUPER_ADMIN))):
    scope=_scoped_project_ids(db,user)
    if scope is not None:
        if not scope: return []
        project_rows=db.scalars(select(Project).where(Project.deleted_at.is_(None),Project.id.in_(scope)).order_by(Project.name)).all()
    else:
        project_rows=db.scalars(select(Project).where(Project.deleted_at.is_(None)).order_by(Project.name)).all()
    rows=[]
    for p in project_rows:
        records=db.scalars(select(Record).where(Record.project_id==p.id,Record.deleted_at.is_(None))).all()
        unresolved=sum(r.status not in {RecordStatus.CLOSED,RecordStatus.CANCELLED,RecordStatus.REJECTED} for r in records)
        high=sum(r.priority in {Priority.HIGH,Priority.URGENT} for r in records)
        score=unresolved+high*2
        rows.append({"id":p.id,"name":p.name,"total":len(records),"unresolved":unresolved,"high":high,"risk_level":"HIGH" if score>=8 else "MEDIUM" if score>=3 else "LOW","tags":["未闭环" if unresolved else "稳定"]})
    return rows
