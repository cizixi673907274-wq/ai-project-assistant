from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timedelta, timezone
import secrets
from sqlalchemy import select
from sqlalchemy.orm import Session
import httpx
from app.core.config import settings
from app.core.enums import UserStatus
from app.core.security import create_token, decode_token, verify_password
from app.db.session import get_db
from app.models.entities import User
from app.schemas.auth import LoginRequest, MobileLoginRequest, RefreshTokenRequest, SmsCodeRequest, WechatLoginRequest
from app.api.deps import current_user
def user_out(user:User):
    return {"id":user.id,"username":user.username,"name":user.name,"mobile":user.mobile,"department_id":user.department_id,"department_name":user.department.name if user.department else None,"roles":[r.code.value for r in user.roles],"permissions":sorted({p.code for r in user.roles for p in r.permissions})}

router=APIRouter(prefix="/auth",tags=["认证"])
_sms_codes:dict[str,tuple[str,datetime]]={}
def tokens(user:User): return {"access_token":create_token(user.id),"refresh_token":create_token(user.id,"refresh"),"token_type":"bearer"}
@router.post("/refresh",summary="使用刷新令牌续期登录")
def refresh_token(payload:RefreshTokenRequest,db:Session=Depends(get_db)):
 try:
  claims=decode_token(payload.refresh_token)
  if claims.get("type")!="refresh": raise ValueError("wrong token type")
  user_id=claims["sub"]
 except Exception: raise HTTPException(status_code=401,detail={"code":"REFRESH_TOKEN_INVALID","message":"登录已失效，请重新登录"})
 user=db.get(User,user_id)
 if not user or user.status!=UserStatus.ACTIVE: raise HTTPException(status_code=401,detail={"code":"USER_DISABLED","message":"账号不存在或已停用"})
 return tokens(user)
@router.post("/login",summary="PC 账号密码登录")
def login(payload:LoginRequest,db:Session=Depends(get_db)):
 user=db.scalar(select(User).where(User.username==payload.username))
 if not user or not verify_password(payload.password,user.password_hash): raise HTTPException(status_code=401,detail={"code":"LOGIN_FAILED","message":"账号或密码不正确"})
 if user.status!=UserStatus.ACTIVE: raise HTTPException(status_code=403,detail={"code":"ACCOUNT_DISABLED","message":"账号已停用，请联系管理员"})
 return tokens(user)
@router.post("/sms/send",summary="发送手机验证码（开发环境支持 Mock）")
def send_sms_code(payload:SmsCodeRequest,db:Session=Depends(get_db)):
 user=db.scalar(select(User).where(User.mobile==payload.mobile))
 if user and user.status!=UserStatus.ACTIVE: raise HTTPException(status_code=403,detail={"code":"ACCOUNT_DISABLED","message":"账号已停用，请联系管理员"})
 if not settings.sms_mock: raise HTTPException(status_code=503,detail={"code":"SMS_NOT_CONFIGURED","message":"短信服务尚未配置，请使用微信登录或联系管理员"})
 code="123456" if settings.sms_mock else f"{secrets.randbelow(1000000):06d}"
 _sms_codes[payload.mobile]=(code,datetime.now(timezone.utc)+timedelta(seconds=settings.sms_code_expire_seconds))
 result={"expires_in":settings.sms_code_expire_seconds}
 if not settings.is_production: result["dev_code"]=code
 return result
@router.post("/mobile/login",summary="手机号验证码登录")
def mobile_login(payload:MobileLoginRequest,db:Session=Depends(get_db)):
 stored=_sms_codes.get(payload.mobile)
 mock_code_valid=settings.sms_mock and secrets.compare_digest(payload.code.strip(),"123456")
 if not mock_code_valid and (not stored or stored[1]<datetime.now(timezone.utc) or not secrets.compare_digest(stored[0],payload.code.strip())):
  raise HTTPException(status_code=401,detail={"code":"SMS_CODE_INVALID","message":"验证码不正确或已失效"})
 user=db.scalar(select(User).where(User.mobile==payload.mobile))
 if not user: raise HTTPException(status_code=404,detail={"code":"EMPLOYEE_NOT_FOUND","message":"该手机号尚未登记，请联系管理员创建员工账号"})
 if user.status!=UserStatus.ACTIVE: raise HTTPException(status_code=403,detail={"code":"ACCOUNT_DISABLED","message":"账号已停用，请联系管理员"})
 _sms_codes.pop(payload.mobile,None)
 return tokens(user)
@router.post("/wechat/login",summary="微信 code 登录（支持开发 Mock 与正式 code2session）")
def wechat_login(payload:WechatLoginRequest,db:Session=Depends(get_db)):
 if settings.wechat_mock: openid=f"mock_{payload.code}"
 else:
  if not settings.wechat_app_id or not settings.wechat_app_secret: raise HTTPException(503,detail={"code":"WECHAT_NOT_CONFIGURED","message":"微信登录参数尚未配置"})
  try:
   response=httpx.get(f"{settings.wechat_api_base_url.rstrip('/')}/sns/jscode2session",params={"appid":settings.wechat_app_id,"secret":settings.wechat_app_secret,"js_code":payload.code,"grant_type":"authorization_code"},timeout=10); response.raise_for_status(); result=response.json()
  except Exception: raise HTTPException(502,detail={"code":"WECHAT_LOGIN_FAILED","message":"微信登录服务暂不可用，请稍后重试"})
  if not result.get("openid"): raise HTTPException(401,detail={"code":"WECHAT_CODE_INVALID","message":result.get("errmsg","微信登录凭证无效")})
  openid=result["openid"]
 user=db.scalar(select(User).where(User.wechat_openid==openid))
 if not user and settings.wechat_mock:
  user=db.scalar(select(User).where(User.username=="engineer")); user.wechat_openid=openid
 elif not user:
  if not payload.employee_mobile: raise HTTPException(403,detail={"code":"EMPLOYEE_BINDING_REQUIRED","message":"首次登录需要填写已登记的员工手机号完成绑定"})
  user=db.scalar(select(User).where(User.mobile==payload.employee_mobile))
  if not user: raise HTTPException(404,detail={"code":"EMPLOYEE_NOT_FOUND","message":"未找到对应员工，请联系管理员先创建账号"})
  if user.wechat_openid and user.wechat_openid!=openid: raise HTTPException(409,detail={"code":"WECHAT_ALREADY_BOUND","message":"该员工账号已绑定其他微信，请联系管理员重置绑定"})
  user.wechat_openid=openid
 if user.status!=UserStatus.ACTIVE: raise HTTPException(403,detail={"code":"ACCOUNT_DISABLED","message":"账号已停用，请联系管理员"})
 db.commit()
 return tokens(user)
@router.get("/me",summary="当前用户")
def me(user:User=Depends(current_user)):
 return user_out(user)
