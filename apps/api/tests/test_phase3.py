import json

from sqlalchemy import func, select

from app.core.config import settings
from app.core.enums import RecordStatus
from app.db.session import SessionLocal
from app.models.entities import AIAnalysis, AIInvocationLog, Notification, User
from app.services.ai import AIProviderError, OpenAICompatibleProvider, StructuredAnalysis


class FakeResponse:
    def __init__(self,body): self.body=body
    def raise_for_status(self): return None
    def json(self): return self.body


def test_integration_status_does_not_expose_secrets(client,admin):
    response=client.get("/api/v1/system/integrations",headers=admin)
    assert response.status_code==200
    data=response.json()["data"]
    assert data["ai"]["configured"] is True
    assert data["ai"]["mock"] is True
    assert data["ocr"]["configured"] is True
    assert data["ocr"]["mock"] is True
    assert "api_key" not in json.dumps(data).lower()
    assert settings.ai_api_key not in json.dumps(data) if settings.ai_api_key else True


def test_openai_provider_retries_and_validates(monkeypatch):
    calls=[]
    valid={"title":"蓝牙连接异常","summary":"防爆标志灯蓝牙配置偶发断连","category":{"name":"软件通信问题"},"stage":{"name":"功能联调"},"product":{"name":"防爆标志灯"},"priority":"HIGH","suggested_department":{"name":"研发部"},"need_follow_up":True,"confidence":.91,"reasoning_summary":"存在重复断连","missing_fields":[]}
    responses=[{"choices":[{"message":{"content":"not-json"}}]},{"choices":[{"message":{"content":json.dumps(valid,ensure_ascii=False)}}],"usage":{"prompt_tokens":100,"completion_tokens":40,"total_tokens":140}}]

    class FakeClient:
        def __init__(self,**_): pass
        def __enter__(self): return self
        def __exit__(self,*_): pass
        def post(self,*_,**__): calls.append(1); return FakeResponse(responses.pop(0))

    monkeypatch.setattr(settings,"ai_api_key","test-key")
    monkeypatch.setattr(settings,"ai_api_style","chat_completions")
    monkeypatch.setattr(settings,"ai_max_retries",1)
    monkeypatch.setattr("app.services.ai.httpx.Client",FakeClient)
    result=OpenAICompatibleProvider().analyze("防爆标志灯蓝牙配置偶发断连")
    assert StructuredAnalysis.model_validate(result.result).confidence==.91
    assert result.attempt_count==2
    assert result.token_usage["total_tokens"]==140
    assert len(calls)==2


def test_responses_provider_extracts_structured_output(monkeypatch):
    valid={"title":"卡扣装配干涉","summary":"猫眼灯透镜卡扣与前壳加强筋干涉","category":{"name":"结构设计问题"},"stage":{"name":"结构试装"},"product":{"name":"猫眼灯"},"priority":"HIGH","suggested_department":{"name":"研发部"},"need_follow_up":True,"confidence":.93,"reasoning_summary":"存在装配干涉","missing_fields":[]}
    body={"output":[{"type":"message","content":[{"type":"output_text","text":json.dumps(valid,ensure_ascii=False)}]}],"usage":{"input_tokens":90,"output_tokens":35,"total_tokens":125}}

    class FakeClient:
        def __init__(self,**_): pass
        def __enter__(self): return self
        def __exit__(self,*_): pass
        def post(self,url,**kwargs):
            assert url.endswith("/responses")
            assert kwargs["json"]["input"][0]["role"]=="system"
            assert kwargs["json"]["thinking"]=={"type":"disabled"}
            return FakeResponse(body)

    monkeypatch.setattr(settings,"ai_api_key","test-key")
    monkeypatch.setattr(settings,"ai_api_style","responses")
    monkeypatch.setattr("app.services.ai.httpx.Client",FakeClient)
    result=OpenAICompatibleProvider().analyze("猫眼灯透镜卡扣与前壳加强筋干涉")
    assert result.result["confidence"]==.93
    assert result.token_usage["total_tokens"]==125


def test_ai_failure_enters_manual_review_and_keeps_error(client,engineer,monkeypatch):
    class BrokenProvider:
        def analyze(self,_): raise AIProviderError("provider unavailable",attempt_count=2)
    monkeypatch.setattr("app.services.records.provider",lambda:BrokenProvider())
    monkeypatch.setattr(settings,"ai_failure_alert_threshold",1)
    created=client.post("/api/v1/records",headers=engineer,json={"content":"真实模型不可用时仍需保留研发记录并进入人工确认"})
    record_id=created.json()["data"]["id"]
    submitted=client.post(f"/api/v1/records/{record_id}/submit",headers=engineer)
    assert submitted.status_code==200
    detail=client.get(f"/api/v1/records/{record_id}",headers=engineer).json()["data"]
    assert detail["status"]==RecordStatus.AI_REVIEW_REQUIRED.value
    db=SessionLocal(); analysis=db.scalar(select(AIAnalysis).where(AIAnalysis.record_id==record_id)); db.close()
    assert analysis.error=="provider unavailable"
    assert analysis.attempt_count==2
    assert analysis.confidence==0
    db=SessionLocal()
    failed_count=db.scalar(select(func.count(AIInvocationLog.id)).where(AIInvocationLog.record_id==record_id,AIInvocationLog.service=="ai",AIInvocationLog.status=="failed"))
    alert_count=db.scalar(select(func.count(Notification.id)).where(Notification.type=="AI_ALERT",Notification.related_record_id==record_id,Notification.is_read.is_(False)))
    db.close()
    assert failed_count==1
    assert alert_count==1


def test_production_wechat_requires_employee_binding(client,monkeypatch):
    monkeypatch.setattr(settings,"wechat_mock",False)
    monkeypatch.setattr(settings,"wechat_app_id","app-id")
    monkeypatch.setattr(settings,"wechat_app_secret","app-secret")
    monkeypatch.setattr("app.api.routes.auth.httpx.get",lambda *_,**__:FakeResponse({"openid":"production-openid-head"}))
    missing=client.post("/api/v1/auth/wechat/login",json={"code":"real-code"})
    assert missing.status_code==403
    bound=client.post("/api/v1/auth/wechat/login",json={"code":"real-code","employee_mobile":"13700006789"})
    assert bound.status_code==200
    db=SessionLocal(); user=db.scalar(select(User).where(User.username=="head")); db.close()
    assert user.wechat_openid=="production-openid-head"


def test_observability_api_returns_invocation_summary_and_alerts(client,admin,engineer):
    db=SessionLocal()
    before=db.scalar(select(func.count(AIInvocationLog.id)))
    db.close()

    # 小程序端即时转写（Mock）应记录 ASR 成功调用
    files={"file":("voice.mp3",b"mock audio", "audio/mpeg")}
    asr=client.post("/api/v1/uploads/transcribe-direct",files=files,headers=engineer)
    assert asr.status_code==200
    assert asr.json()["data"]["provider"]=="mock"

    db=SessionLocal()
    after=db.scalar(select(func.count(AIInvocationLog.id)))
    db.close()
    assert after>=before+1
    detail=client.get("/api/v1/system/observability",headers=admin).json()["data"]
    assert detail["window"]["days"]==7
    assert detail["invocations"]["asr"]["total"]>=1
    assert detail["invocations"]["ai"]["total"]>=0
