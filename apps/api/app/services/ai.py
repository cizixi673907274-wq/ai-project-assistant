import base64
import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.config import settings
from app.services.tencent_cloud import TencentCloudAPIError, TencentCloudClient


class NamedValue(BaseModel):
    model_config=ConfigDict(extra="ignore")
    name:str=Field(min_length=1,max_length=100)


class StructuredAnalysis(BaseModel):
    model_config=ConfigDict(extra="ignore")
    title:str=Field(min_length=1,max_length=80)
    summary:str=Field(min_length=1,max_length=500)
    category:NamedValue
    stage:NamedValue
    product:NamedValue
    priority:Literal["LOW","MEDIUM","HIGH","URGENT"]
    suggested_department:NamedValue
    need_follow_up:bool=True
    confidence:float=Field(ge=0,le=1)
    reasoning_summary:str=Field(default="",max_length=500)
    missing_fields:list[str]=Field(default_factory=list)


@dataclass
class AnalysisResponse:
    result:dict
    provider:str
    model:str
    token_usage:dict=field(default_factory=dict)
    attempt_count:int=1
    cost_estimate:float=0
    raw_response_hash:str=""


@dataclass
class OCRResponse:
    text:str
    lines:list[dict]
    provider:str
    model:str
    request_id:str=""


class AIProviderError(RuntimeError):
    def __init__(self,message:str,attempt_count:int=1):
        super().__init__(message); self.attempt_count=attempt_count


class LLMProvider(ABC):
    @abstractmethod
    def analyze(self,text:str)->AnalysisResponse: ...


class ASRProvider(ABC):
    @abstractmethod
    def transcribe(self,name:str,data:bytes|None=None,mime:str="audio/mpeg")->str: ...


class OCRProvider(ABC):
    @abstractmethod
    def recognize(self,name:str,data:bytes,mime:str="image/jpeg")->OCRResponse: ...


class MockProvider(LLMProvider,ASRProvider,OCRProvider):
    def analyze(self,text:str)->AnalysisResponse:
        urgent=any(k in text for k in ("故障","不亮","重启","断连","停机","危险","压缩量不足","拉力不足")); confidence=.92 if len(text)>12 else .72
        title=(text.replace("\n"," ")[:24] or "研发记录")+("…" if len(text)>24 else "")
        product="待确认产品"
        for keyword,name in (("猫眼", "猫眼灯"),("防爆", "防爆标志灯"),("吸顶", "吸顶灯"),("应急", "应急照明模块"),("控制板", "嵌入式控制板")):
            if keyword in text:
                product=name; break
        if any(k in text for k in ("卡扣","外壳","孔位","筋位","导光","密封")):
            category="结构设计问题"
        elif any(k in text for k in ("软件","OTA","蓝牙","通信","重启","参数","日志")):
            category="软件联调问题"
        elif any(k in text for k in ("模具","试模","缩水","顶针","注塑","压接","工装")):
            category="模具/工艺问题"
        else:
            category="研发技术问题"
        stage="样机测试" if any(k in text for k in ("样机","测试","验证")) else "研发评审"
        result=StructuredAnalysis.model_validate({"title":title,"summary":text[:120] or "研发记录待补充","category":{"name":category},"stage":{"name":stage},"product":{"name":product},"priority":"HIGH" if urgent else "MEDIUM","suggested_department":{"name":"研发部"},"need_follow_up":True,"confidence":confidence,"reasoning_summary":"Mock 根据产品、结构/软件/模具关键词和问题紧急程度生成结构化结果。","missing_fields":[]}).model_dump()
        raw=json.dumps(result,ensure_ascii=False,sort_keys=True)
        return AnalysisResponse(result=result,provider="mock",model="mock-structured-v2",raw_response_hash=hashlib.sha256(raw.encode()).hexdigest())

    def transcribe(self,name:str,data:bytes|None=None,mime:str="audio/mpeg")->str:
        return f"Mock语音转写：{name} 中描述了产品开发验证问题，需要结构、软件或模具工程师协同排查。"

    def recognize(self,name:str,data:bytes,mime:str="image/jpeg")->OCRResponse:
        text=f"Mock文字识别：{name} 中包含产品开发问题记录。"
        return OCRResponse(
            text=text,
            lines=[{"text":text,"confidence":100}],
            provider="mock",
            model="mock-ocr-v1",
        )


class OpenAICompatibleProvider(LLMProvider,ASRProvider):
    def __init__(self):
        if not settings.ai_api_key: raise AIProviderError("已选择真实 AI 服务，但 AI_API_KEY 未配置")
        self.headers={"Authorization":f"Bearer {settings.ai_api_key}","Content-Type":"application/json"}

    def analyze(self,text:str)->AnalysisResponse:
        schema={"title":"24字以内标题","summary":"120字以内摘要","category":{"name":"问题分类"},"stage":{"name":"发生环节"},"product":{"name":"涉及产品"},"priority":"LOW|MEDIUM|HIGH|URGENT","suggested_department":{"name":"建议部门"},"need_follow_up":True,"confidence":0.9,"reasoning_summary":"简短判断依据","missing_fields":[]}
        minimized=text.strip()[:8000]
        system_prompt="你是研发中心产品开发问题分析助手，主要服务结构工程师、软件工程师、模具工程师，关注猫眼灯、防爆标志灯、吸顶灯等产品开发过程中的结构、软件、模具、工艺、可靠性问题。只输出合法 JSON，不添加 Markdown。字段结构必须与示例一致："+json.dumps(schema,ensure_ascii=False)
        api_style=settings.ai_api_style.strip().lower()
        if api_style=="chat_completions":
            path="/chat/completions"
            payload={"model":settings.ai_model,"temperature":0.1,"response_format":{"type":"json_object"},"messages":[{"role":"system","content":system_prompt},{"role":"user","content":minimized}]}
        elif api_style=="responses":
            path="/responses"
            payload={"model":settings.ai_model,"input":[{"role":"system","content":system_prompt},{"role":"user","content":minimized}],"thinking":{"type":"disabled"}}
        else:
            raise AIProviderError(f"不支持的 AI_API_STYLE：{settings.ai_api_style}")
        errors=[]
        for attempt in range(1,settings.ai_max_retries+2):
            try:
                with httpx.Client(timeout=settings.ai_timeout_seconds) as client:
                    response=client.post(f"{settings.ai_base_url.rstrip('/')}{path}",headers=self.headers,json=payload)
                    response.raise_for_status()
                body=response.json()
                if api_style=="chat_completions":
                    raw=body["choices"][0]["message"]["content"]
                else:
                    raw=next(
                        content["text"]
                        for output in body["output"] if output.get("type")=="message"
                        for content in output.get("content",[]) if content.get("type")=="output_text"
                    )
                parsed=StructuredAnalysis.model_validate_json(raw).model_dump()
                usage=body.get("usage") or {}; input_tokens=int(usage.get("prompt_tokens",usage.get("input_tokens",0))); output_tokens=int(usage.get("completion_tokens",usage.get("output_tokens",0)))
                cost=(input_tokens*settings.ai_input_cost_per_million+output_tokens*settings.ai_output_cost_per_million)/1_000_000
                return AnalysisResponse(result=parsed,provider="openai_compatible",model=settings.ai_model,token_usage=usage,attempt_count=attempt,cost_estimate=round(cost,8),raw_response_hash=hashlib.sha256(raw.encode()).hexdigest())
            except (httpx.HTTPError,KeyError,StopIteration,TypeError,ValueError,json.JSONDecodeError,ValidationError) as exc:
                errors.append(f"第{attempt}次：{type(exc).__name__}: {exc}")
        raise AIProviderError("；".join(errors),attempt_count=len(errors))

    def transcribe(self,name:str,data:bytes|None=None,mime:str="audio/mpeg")->str:
        if not data: raise AIProviderError("真实语音转写需要读取音频文件内容")
        headers={"Authorization":f"Bearer {settings.ai_api_key}"}; errors=[]
        for attempt in range(1,settings.ai_max_retries+2):
            try:
                with httpx.Client(timeout=settings.ai_timeout_seconds) as client:
                    response=client.post(f"{settings.ai_base_url.rstrip('/')}/audio/transcriptions",headers=headers,data={"model":settings.asr_model},files={"file":(name,data,mime)})
                    response.raise_for_status()
                text=(response.json().get("text") or "").strip()
                if not text: raise ValueError("服务未返回转写文字")
                return text
            except (httpx.HTTPError,ValueError,TypeError) as exc: errors.append(f"第{attempt}次：{type(exc).__name__}: {exc}")
        raise AIProviderError("；".join(errors),attempt_count=len(errors))


class TencentASRProvider(ASRProvider):
    format_by_mime={
        "audio/mpeg":"mp3",
        "audio/mp3":"mp3",
        "audio/mp4":"m4a",
        "audio/x-m4a":"m4a",
        "audio/aac":"aac",
        "audio/wav":"wav",
        "audio/x-wav":"wav",
        "audio/ogg":"ogg-opus",
        "audio/amr":"amr",
    }

    def __init__(self):
        self.client=TencentCloudClient(
            settings.tencent_secret_id,
            settings.tencent_secret_key,
            service="asr",
            version="2019-06-14",
            endpoint="asr.tencentcloudapi.com",
            region=settings.tencent_region,
            timeout=settings.ai_timeout_seconds,
        )

    def transcribe(self,name:str,data:bytes|None=None,mime:str="audio/mpeg")->str:
        if not data: raise AIProviderError("腾讯云语音转写需要读取音频文件内容")
        if len(data)>settings.tencent_asr_max_mb*1024*1024:
            raise AIProviderError(f"腾讯云一句话识别单段音频不能超过 {settings.tencent_asr_max_mb}MB")
        suffix=name.rsplit(".",1)[-1].lower() if "." in name else ""
        voice_format=self.format_by_mime.get(mime.split(";")[0].lower(),suffix or "mp3")
        if voice_format=="ogg": voice_format="ogg-opus"
        payload={
            "EngSerViceType":settings.tencent_asr_engine,
            "SourceType":1,
            "VoiceFormat":voice_format,
            "Data":base64.b64encode(data).decode("ascii"),
            "DataLen":len(data),
            "WordInfo":0,
            "FilterDirty":0,
            "FilterModal":0,
            "FilterPunc":0,
            "ConvertNumMode":1,
        }
        if settings.tencent_asr_hotword_list:
            payload["HotwordList"]=settings.tencent_asr_hotword_list
        errors=[]
        for attempt in range(1,settings.ai_max_retries+2):
            try:
                result=self.client.call("SentenceRecognition",payload)
                text=(result.get("Result") or "").strip()
                if not text: raise TencentCloudAPIError("腾讯云 ASR 未返回转写文字")
                return text
            except TencentCloudAPIError as exc:
                errors.append(f"第{attempt}次：{exc}")
        raise AIProviderError("；".join(errors),attempt_count=len(errors))


class TencentOCRProvider(OCRProvider):
    def __init__(self):
        self.client=TencentCloudClient(
            settings.tencent_secret_id,
            settings.tencent_secret_key,
            service="ocr",
            version="2018-11-19",
            endpoint="ocr.tencentcloudapi.com",
            region=settings.tencent_region,
            timeout=settings.ai_timeout_seconds,
        )

    def recognize(self,name:str,data:bytes,mime:str="image/jpeg")->OCRResponse:
        if not data: raise AIProviderError("腾讯云文字识别需要读取图片内容")
        if len(data)>settings.ocr_max_mb*1024*1024:
            raise AIProviderError(f"OCR 图片不能超过 {settings.ocr_max_mb}MB")
        payload={
            "ImageBase64":base64.b64encode(data).decode("ascii"),
            "LanguageType":settings.ocr_language_type,
        }
        errors=[]
        for attempt in range(1,settings.ai_max_retries+2):
            try:
                result=self.client.call("GeneralBasicOCR",payload)
                lines=[
                    {
                        "text":item.get("DetectedText",""),
                        "confidence":item.get("Confidence"),
                        "polygon":item.get("Polygon"),
                    }
                    for item in result.get("TextDetections",[])
                    if item.get("DetectedText")
                ]
                text="\n".join(item["text"] for item in lines).strip()
                if not text: raise TencentCloudAPIError("腾讯云 OCR 未识别到文字")
                return OCRResponse(
                    text=text,
                    lines=lines,
                    provider="tencent_cloud",
                    model="GeneralBasicOCR",
                    request_id=result.get("RequestId",""),
                )
            except TencentCloudAPIError as exc:
                errors.append(f"第{attempt}次：{exc}")
        raise AIProviderError("；".join(errors),attempt_count=len(errors))


def provider(mode:str="ai"):
    selected=settings.asr_provider if mode=="asr" else settings.ocr_provider if mode=="ocr" else settings.ai_provider
    if selected=="mock": return MockProvider()
    try:
        if selected=="tencent_cloud" and mode=="asr": return TencentASRProvider()
        if selected=="tencent_cloud" and mode=="ocr": return TencentOCRProvider()
    except TencentCloudAPIError as exc:
        raise AIProviderError(str(exc)) from exc
    if selected=="openai_compatible": return OpenAICompatibleProvider()
    raise AIProviderError(f"不支持的服务类型：{selected}")


def analysis_metadata(response:AnalysisResponse,started:float):
    return {"provider":response.provider,"model":response.model,"prompt_version":settings.ai_prompt_version,"latency_ms":int((time.time()-started)*1000),"raw_response_hash":response.raw_response_hash,"token_usage":response.token_usage,"attempt_count":response.attempt_count,"cost_estimate":response.cost_estimate}
