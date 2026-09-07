from fastapi import APIRouter, Depends
from app.api.deps import current_user
from app.models.entities import User
from app.api.routes.auth import user_out
from app.api.routes import admin, auth, dashboard, phase2, phase3, records, system, uploads
router=APIRouter(); router.include_router(auth.router); router.include_router(records.router); router.include_router(uploads.router); router.include_router(dashboard.router); router.include_router(admin.router); router.include_router(phase2.router); router.include_router(phase3.router); router.include_router(system.router)
@router.get("/me",tags=["认证"],summary="当前用户与权限")
def me(user:User=Depends(current_user)): return user_out(user)
