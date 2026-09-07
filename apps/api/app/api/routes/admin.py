from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles, role_codes
from app.core.enums import RoleCode, UserStatus
from app.core.security import hash_password
from app.db.session import get_db
from app.models.entities import Department, Project, Role, User, project_members

router = APIRouter(prefix="/admin", tags=["成员权限"])


class UserCreate(BaseModel):
    username: str
    name: str
    mobile: str | None = None
    password: str = Field(min_length=8, max_length=128)
    department_id: str | None = None
    role: RoleCode


class UserPatch(BaseModel):
    name: str | None = None
    mobile: str | None = None
    department_id: str | None = None
    status: UserStatus | None = None
    role: RoleCode | None = None


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class DepartmentPatch(BaseModel):
    name: str = Field(min_length=1, max_length=100)


def output(u: User):
    return {
        "id": u.id,
        "username": u.username,
        "name": u.name,
        "mobile": ("***" + u.mobile[-4:]) if u.mobile else None,
        "department": u.department.name if u.department else None,
        "department_id": u.department_id,
        "roles": [r.code.value for r in u.roles],
        "status": u.status.value,
        "last_active": u.updated_at,
    }


PROJECT_MANAGER_ROLES = {RoleCode.PROJECT_MANAGER, RoleCode.DEPARTMENT_HEAD}
MEMBER_MANAGER_ROLES = (RoleCode.SUPER_ADMIN, *PROJECT_MANAGER_ROLES)
SUPERVISOR_MANAGER_ROLES = {RoleCode.PROJECT_MANAGER, RoleCode.DEPARTMENT_HEAD}


def _is_super_admin(user: User):
    return RoleCode.SUPER_ADMIN in role_codes(user)


def _validate_department(db: Session, department_id: str | None):
    if not department_id:
        raise HTTPException(
            status_code=422,
            detail={"code": "DEPARTMENT_REQUIRED", "message": "请选择所属团队"},
        )
    department = db.get(Department, department_id)
    if not department:
        raise HTTPException(
            status_code=422,
            detail={"code": "DEPARTMENT_NOT_FOUND", "message": "所属团队不存在"},
        )
    return department


def _managed_user_query(user: User):
    q = select(User).order_by(User.created_at)
    if _is_super_admin(user):
        return q.where(User.roles.any(Role.code.in_(PROJECT_MANAGER_ROLES)))
    visible_scopes = []
    if user.department_id:
        visible_scopes.append(User.department_id == user.department_id)
    if RoleCode.PROJECT_MANAGER in role_codes(user):
        project_member_ids = (
            select(project_members.c.user_id)
            .join(Project, Project.id == project_members.c.project_id)
            .where(Project.manager_id == user.id, Project.deleted_at.is_(None))
        )
        visible_scopes.append(User.id.in_(project_member_ids))
    if not visible_scopes:
        return q.where(False)
    return q.where(User.roles.any(Role.code == RoleCode.ENGINEER), or_(*visible_scopes))


def _ensure_managed_target(db: Session, actor: User, target: User):
    target_roles = role_codes(target)
    if _is_super_admin(actor):
        allowed = bool(target_roles & PROJECT_MANAGER_ROLES)
    else:
        manages_target_project = False
        if RoleCode.PROJECT_MANAGER in role_codes(actor):
            manages_target_project = db.scalar(
                select(Project.id)
                .join(project_members, project_members.c.project_id == Project.id)
                .where(
                    Project.manager_id == actor.id,
                    Project.deleted_at.is_(None),
                    project_members.c.user_id == target.id,
                )
                .limit(1)
            ) is not None
        allowed = (
            RoleCode.ENGINEER in target_roles
            and (
                (bool(actor.department_id) and target.department_id == actor.department_id)
                or manages_target_project
            )
        )
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail={"code": "USER_SCOPE_FORBIDDEN", "message": "只能管理权限范围内的成员"},
        )


@router.get("/users")
def users(db: Session = Depends(get_db), user: User = Depends(require_roles(*MEMBER_MANAGER_ROLES))):
    return [output(u) for u in db.scalars(_managed_user_query(user)).unique().all()]


@router.get("/departments")
def departments(db: Session = Depends(get_db), user: User = Depends(require_roles(*MEMBER_MANAGER_ROLES))):
    q = select(Department).order_by(Department.name)
    if not _is_super_admin(user):
        if not user.department_id:
            return []
        q = q.where(Department.id == user.department_id)
    return [{"id": d.id, "name": d.name, "parent_id": d.parent_id} for d in db.scalars(q).all()]


@router.post("/departments", status_code=201)
def create_department(
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(RoleCode.SUPER_ADMIN)),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(
            status_code=422,
            detail={"code": "DEPARTMENT_NAME_REQUIRED", "message": "请输入团队名称"},
        )
    if db.scalar(select(Department).where(Department.name == name)):
        raise HTTPException(
            status_code=409,
            detail={"code": "DEPARTMENT_NAME_EXISTS", "message": "团队名称已存在"},
        )
    department = Department(name=name)
    db.add(department)
    db.commit()
    db.refresh(department)
    return {"id": department.id, "name": department.name, "parent_id": department.parent_id}


@router.patch("/departments/{id}")
def patch_department(
    id: str,
    payload: DepartmentPatch,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(RoleCode.SUPER_ADMIN)),
):
    department = db.get(Department, id)
    if not department:
        raise HTTPException(
            status_code=404,
            detail={"code": "DEPARTMENT_NOT_FOUND", "message": "团队不存在"},
        )
    name = payload.name.strip()
    if not name:
        raise HTTPException(
            status_code=422,
            detail={"code": "DEPARTMENT_NAME_REQUIRED", "message": "请输入团队名称"},
        )
    duplicate = db.scalar(select(Department).where(Department.name == name, Department.id != id))
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail={"code": "DEPARTMENT_NAME_EXISTS", "message": "团队名称已存在"},
        )
    department.name = name
    db.commit()
    return {"id": department.id, "name": department.name, "parent_id": department.parent_id}


@router.post("/users", status_code=201)
def create(
    payload: UserCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MEMBER_MANAGER_ROLES)),
):
    if db.scalar(select(User).where(User.username == payload.username)):
        raise HTTPException(
            status_code=409,
            detail={"code": "USERNAME_EXISTS", "message": "账号已存在"},
        )
    department_id = payload.department_id
    if _is_super_admin(user):
        if payload.role not in SUPERVISOR_MANAGER_ROLES:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "ROLE_FORBIDDEN",
                    "message": "管理员只能创建团队主管（项目经理）",
                },
            )
        _validate_department(db, department_id)
    else:
        if payload.role != RoleCode.ENGINEER:
            raise HTTPException(
                status_code=403,
                detail={"code": "ROLE_FORBIDDEN", "message": "主管只能创建本团队工程师"},
            )
        department_id = user.department_id
        _validate_department(db, department_id)

    role = db.scalar(select(Role).where(Role.code == payload.role))
    if not role:
        raise HTTPException(
            status_code=422,
            detail={"code": "ROLE_NOT_FOUND", "message": "角色不存在"},
        )
    u = User(
        username=payload.username,
        name=payload.name,
        mobile=payload.mobile,
        password_hash=hash_password(payload.password),
        department_id=department_id,
        roles=[role],
    )
    db.add(u)
    db.commit()
    return output(u)


@router.patch("/users/{id}")
def patch(
    id: str,
    payload: UserPatch,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MEMBER_MANAGER_ROLES)),
):
    u = db.get(User, id)
    if not u:
        raise HTTPException(
            status_code=404,
            detail={"code": "USER_NOT_FOUND", "message": "成员不存在"},
        )
    _ensure_managed_target(db, user, u)
    values = payload.model_dump(exclude_unset=True, exclude={"role", "department_id"})
    for k, v in values.items():
        setattr(u, k, v)
    if _is_super_admin(user):
        if payload.department_id is not None:
            _validate_department(db, payload.department_id)
            u.department_id = payload.department_id
        if payload.role is not None:
            if payload.role not in SUPERVISOR_MANAGER_ROLES:
                raise HTTPException(
                    status_code=403,
                    detail={"code": "ROLE_FORBIDDEN", "message": "管理员只能配置主管角色"},
                )
            u.roles = [db.scalar(select(Role).where(Role.code == payload.role))]
    else:
        if (
            payload.department_id is not None
            and payload.department_id != user.department_id
        ):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "DEPARTMENT_SCOPE_FORBIDDEN",
                    "message": "不能将工程师调整到其他团队",
                },
            )
        if payload.role is not None and payload.role != RoleCode.ENGINEER:
            raise HTTPException(
                status_code=403,
                detail={"code": "ROLE_FORBIDDEN", "message": "主管不能修改工程师的角色"},
            )
    db.commit()
    return output(u)


@router.get("/roles")
def roles(db: Session = Depends(get_db), user: User = Depends(require_roles(*MEMBER_MANAGER_ROLES))):
    allowed = SUPERVISOR_MANAGER_ROLES if _is_super_admin(user) else {RoleCode.ENGINEER}
    q = select(Role).where(Role.code.in_(allowed))
    return [
        {
            "id": r.id,
            "code": r.code.value,
            "name": r.name,
            "permissions": [p.code for p in r.permissions],
        }
        for r in db.scalars(q).unique().all()
    ]
