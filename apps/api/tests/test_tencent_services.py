import base64
import json

from app.core.config import settings
from app.services.ai import TencentASRProvider, TencentOCRProvider
from app.services.tencent_cloud import TencentCloudClient


def configure_tencent(monkeypatch):
    monkeypatch.setattr(settings, "tencent_secret_id", "test-secret-id")
    monkeypatch.setattr(settings, "tencent_secret_key", "test-secret-key")
    monkeypatch.setattr(settings, "ai_max_retries", 0)


def test_tc3_headers_are_deterministic_and_do_not_expose_secret_key():
    client = TencentCloudClient(
        "test-secret-id",
        "test-secret-key",
        service="ocr",
        version="2018-11-19",
        endpoint="ocr.tencentcloudapi.com",
        region="ap-guangzhou",
    )
    payload = json.dumps({"ImageBase64": "YWJj"}, separators=(",", ":"))
    headers = client.signed_headers("GeneralBasicOCR", payload, timestamp=1595230290)
    assert headers["X-TC-Action"] == "GeneralBasicOCR"
    assert headers["X-TC-Version"] == "2018-11-19"
    assert headers["X-TC-Timestamp"] == "1595230290"
    assert "Credential=test-secret-id/" in headers["Authorization"]
    assert "SignedHeaders=content-type;host" in headers["Authorization"]
    assert "test-secret-key" not in json.dumps(headers)


def test_tencent_asr_maps_audio_and_returns_text(monkeypatch):
    configure_tencent(monkeypatch)
    provider = TencentASRProvider()
    captured = {}

    def fake_call(action, payload):
        captured.update(payload)
        assert action == "SentenceRecognition"
        return {"Result": "猫眼灯卡扣与外壳存在干涉。", "RequestId": "asr-request"}

    monkeypatch.setattr(provider.client, "call", fake_call)
    audio = b"test-audio"
    assert provider.transcribe("voice.mp3", audio, "audio/mpeg") == "猫眼灯卡扣与外壳存在干涉。"
    assert captured["VoiceFormat"] == "mp3"
    assert captured["DataLen"] == len(audio)
    assert base64.b64decode(captured["Data"]) == audio
    assert captured["EngSerViceType"] == settings.tencent_asr_engine


def test_tencent_ocr_uses_general_basic_and_merges_lines(monkeypatch):
    configure_tencent(monkeypatch)
    provider = TencentOCRProvider()
    captured = {}

    def fake_call(action, payload):
        captured.update(payload)
        assert action == "GeneralBasicOCR"
        return {
            "TextDetections": [
                {"DetectedText": "防爆标志灯", "Confidence": 99},
                {"DetectedText": "结构样机验证记录", "Confidence": 98},
            ],
            "RequestId": "ocr-request",
        }

    monkeypatch.setattr(provider.client, "call", fake_call)
    result = provider.recognize("研发记录.jpg", b"image-bytes", "image/jpeg")
    assert result.text == "防爆标志灯\n结构样机验证记录"
    assert result.model == "GeneralBasicOCR"
    assert result.request_id == "ocr-request"
    assert base64.b64decode(captured["ImageBase64"]) == b"image-bytes"
    assert captured["LanguageType"] == "zh"


def test_ocr_direct_mock_endpoint(client, engineer):
    response = client.post(
        "/api/v1/uploads/ocr-direct",
        headers=engineer,
        files={"file": ("研发问题.jpg", b"image-bytes", "image/jpeg")},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["provider"] == "mock"
    assert data["model"] == "mock-ocr-v1"
    assert "研发问题.jpg" in data["text"]
    assert data["lines"]


def test_ocr_direct_rejects_non_image(client, engineer):
    response = client.post(
        "/api/v1/uploads/ocr-direct",
        headers=engineer,
        files={"file": ("notes.txt", b"text", "text/plain")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "OCR_FILE_UNSUPPORTED"
