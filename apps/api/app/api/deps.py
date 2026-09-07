from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from app.core.enums import RoleCode, UserStatus
from app.core.security import decode_token
from app.db.session import get_db
from app.models.entities import Project, User
bearer=HTTPBearer(auto_error=False)
def current_user(credentials:HTTPAuthorizationCredentials|None=Depends(bearer),db:Session=Depends(get_db)):
    if not credentials: raise HTTPException(status_code=401,detail={"code":"AUTH_REQUIRED","message":"请先登录"})
    try:
        claims=decode_token(credentials.credentials)
        if claims.get("type")!="access": raise ValueError("wrong token type")
        user_id=claims["sub"]
    except Exception: raise HTTPException(status_code=401,detail={"code":"TOKEN_INVALID","message":"登录已失效，请重新登录"})
    user=db.get(User,user_id)
    if not user or user.status!=UserStatus.ACTIVE: raise HTTPException(status_code=401,detail={"code":"USER_DISABLED","message":"账号不存在或已停用"})
    return user
def require_roles(*roles:RoleCode):
    def dependency(user:User=Depends(current_user)):
        if not ({r.code for r in user.roles}&set(roles)): raise HTTPException(status_code=403,detail={"code":"FORBIDDEN","message":"当前账号无权执行此操作"})
        return user
    return dependency
def is_admin(user:User): return bool({r.code for r in user.roles}&{RoleCode.SUPER_ADMIN,RoleCode.PROJECT_MANAGER,RoleCode.DEPARTMENT_HEAD})

def role_codes(user:User):
    return {r.code for r in user.roles}

def is_super_admin(user:User):
    return RoleCode.SUPER_ADMIN in role_codes(user)

def managed_project_ids(db:Session,user:User):
    if is_super_admin(user):
        return None
    roles=role_codes(user)
    if not ({RoleCode.PROJECT_MANAGER,RoleCode.DEPARTMENT_HEAD} & roles):
        return []
    conditions=[]
    if RoleCode.PROJECT_MANAGER in roles:
        conditions.append(Project.manager_id==user.id)
    if RoleCode.DEPARTMENT_HEAD in roles and user.department_id:
        conditions.append(Project.department_id==user.department_id)
    if not conditions:
        return []
    rows=db.scalars(select(Project.id).where(Project.deleted_at.is_(None),or_(*conditions))).all()
    return list(rows)

def can_manage_project(user:User, project:Project|None):
    if not project: return False
    if is_super_admin(user):
        return True
    if project.manager_id==user.id:
        return True
    roles=role_codes(user)
    if ({RoleCode.DEPARTMENT_HEAD} & roles) and project.department_id and user.department_id:
        return project.department_id==user.department_id
    return False
