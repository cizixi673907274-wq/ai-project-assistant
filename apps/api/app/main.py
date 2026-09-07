from uuid import uuid4
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import json
import logging
import time
from app.api.router import router
from app.core.config import settings
from app.db.session import engine
from sqlalchemy import text
from redis import Redis
logger=logging.getLogger("ai_project_api")

@asynccontextmanager
async def lifespan(_:FastAPI):
 if settings.is_production:
  issues=settings.production_issues()
  if issues: raise RuntimeError("生产环境配置检查失败："+"；".join(issues))
 yield

app=FastAPI(title=settings.app_name,version="0.2.0",description="研发中心产品开发问题记录、AI结构化分析与闭环 API",docs_url="/docs",redoc_url="/redoc",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=settings.cors_list,allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
@app.middleware("http")
async def request_context(request:Request,call_next):
 started=time.perf_counter(); request.state.request_id=request.headers.get("X-Request-ID",str(uuid4())); response=await call_next(request); elapsed_ms=int((time.perf_counter()-started)*1000); response.headers["X-Request-ID"]=request.state.request_id; response.headers["X-Response-Time-Ms"]=str(elapsed_ms)
 logger.info(json.dumps({"event":"http_request","request_id":request.state.request_id,"method":request.method,"path":request.url.path,"status":response.status_code,"latency_ms":elapsed_ms},ensure_ascii=False))
 if response.status_code<400 and response.headers.get("content-type","").startswith("application/json") and request.url.path.startswith(settings.api_prefix):
  chunks=[chunk async for chunk in response.body_iterator]; raw=b"".join(chunks); data=json.loads(raw or b"null")
  wrapped=json.dumps({"success":True,"data":data,"message":"ok","request_id":request.state.request_id},ensure_ascii=False,default=str).encode()
  headers=dict(response.headers); headers.pop("content-length",None); return Response(wrapped,status_code=response.status_code,headers=headers,media_type="application/json")
 return response
@app.exception_handler(HTTPException)
async def http_error(request:Request,exc:HTTPException):
 detail=exc.detail if isinstance(exc.detail,dict) else {"code":"HTTP_ERROR","message":str(exc.detail)}; return JSONResponse(status_code=exc.status_code,content={"success":False,"error":detail,"request_id":getattr(request.state,"request_id","")})
@app.exception_handler(RequestValidationError)
async def validation_error(request:Request,exc:RequestValidationError): return JSONResponse(status_code=422,content={"success":False,"error":{"code":"VALIDATION_ERROR","message":"请求参数不正确","details":{"errors":exc.errors()}},"request_id":getattr(request.state,"request_id","")})
@app.get("/health",tags=["系统"])
def health():
 checks={"database":"down","redis":"down"}
 try:
  with engine.connect() as conn: conn.execute(text("select 1")); checks["database"]="ok"
 except Exception: pass
 try: Redis.from_url(settings.redis_url,socket_connect_timeout=.2).ping(); checks["redis"]="ok"
 except Exception: pass
 required_redis=settings.task_queue_mode=="redis"
 healthy=checks["database"]=="ok" and (not required_redis or checks["redis"]=="ok")
 return {"status":"ok" if healthy else "degraded","service":"api","checks":checks}
app.include_router(router,prefix=settings.api_prefix)
