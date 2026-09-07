from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config=SettingsConfigDict(env_file="../../.env",extra="ignore")
    app_env:str="development"; app_name:str="AI项目助手"; api_prefix:str="/api/v1"
    secret_key:str="dev-secret-change-me-at-least-32-bytes"; access_token_expire_minutes:int=30; refresh_token_expire_days:int=7
    database_url:str="sqlite:///./ai_field.db"; redis_url:str="redis://localhost:6379/0"
    minio_endpoint:str="localhost:9000"; minio_public_endpoint:str="localhost:9000"; minio_access_key:str="minioadmin"; minio_secret_key:str="minioadmin"
    minio_bucket:str="ai-field-media"; minio_secure:bool=False; minio_public_secure:bool=False
    ai_provider:str="mock"; asr_provider:str="mock"; ocr_provider:str="mock"; ai_review_threshold:float=.85
    ai_base_url:str="https://api.openai.com/v1"; ai_api_style:str="chat_completions"; ai_api_key:str=""; ai_model:str="gpt-4o-mini"; asr_model:str="whisper-1"; ai_timeout_seconds:int=60
    ai_max_retries:int=1; ai_prompt_version:str="phase3-v1"; ai_input_cost_per_million:float=0; ai_output_cost_per_million:float=0
    ai_failure_streak_minutes:int=10; ai_failure_alert_threshold:int=3
    tencent_secret_id:str=""; tencent_secret_key:str=""; tencent_region:str="ap-guangzhou"; tencent_app_id:str=""
    tencent_asr_engine:str="16k_zh"; tencent_asr_hotword_list:str="猫眼灯|10,防爆标志灯|10,吸顶灯|10,结构干涉|8,模具试模|8,OTA|8"
    tencent_asr_max_mb:int=3; ocr_language_type:str="zh"; ocr_max_mb:int=7
    wechat_mock:bool=True; wechat_app_id:str=""; wechat_app_secret:str=""; wechat_api_base_url:str="https://api.weixin.qq.com"
    sms_mock:bool=True; sms_code_expire_seconds:int=300
    allow_mock_in_production:bool=False; max_upload_mb:int=20
    export_storage:str="local"; export_dir:str="./generated_exports"; max_export_records:int=5000
    task_queue_mode:str="inline"; task_queue_name:str="ai-project:exports"; task_worker_heartbeat_key:str="ai-project:worker:heartbeat"
    export_job_max_attempts:int=3; export_retention_days:int=7; export_cleanup_interval_seconds:int=3600; export_stale_minutes:int=15
    cors_origins:str="http://localhost:5173,http://127.0.0.1:5173,http://localhost:10086,http://127.0.0.1:10086,http://localhost:10087,http://127.0.0.1:10087"
    @property
    def sync_database_url(self): return self.database_url.replace("+asyncpg","+psycopg")
    @property
    def cors_list(self): return [v.strip() for v in self.cors_origins.split(",") if v.strip()]
    @property
    def is_production(self): return self.app_env.lower()=="production"
    def production_issues(self):
        issues=[]
        if len(self.secret_key)<32 or "change-me" in self.secret_key or "dev-secret" in self.secret_key: issues.append("SECRET_KEY 必须替换为至少 32 位随机值")
        if not self.allow_mock_in_production and (self.ai_provider=="mock" or self.asr_provider=="mock"): issues.append("生产环境禁止使用 Mock AI/ASR")
        if (self.asr_provider=="tencent_cloud" or self.ocr_provider=="tencent_cloud") and not (self.tencent_secret_id and self.tencent_secret_key): issues.append("腾讯云 ASR/OCR 已启用但 SecretId 或 SecretKey 未配置")
        if self.wechat_mock: issues.append("生产环境必须关闭 WECHAT_MOCK")
        if self.sms_mock: issues.append("生产环境必须关闭 SMS_MOCK 并接入真实短信服务")
        if not self.wechat_app_id or not self.wechat_app_secret: issues.append("生产环境必须配置微信 AppID 与 Secret")
        if self.task_queue_mode!="redis": issues.append("生产环境必须使用 Redis 持久任务队列")
        return issues
@lru_cache
def get_settings(): return Settings()
settings=get_settings()
