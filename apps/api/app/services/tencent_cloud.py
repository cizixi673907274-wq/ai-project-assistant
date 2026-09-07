import hashlib
import hmac
import json
import time
from datetime import datetime, timezone

import httpx


class TencentCloudAPIError(RuntimeError):
    def __init__(self, message: str, code: str = "", request_id: str = ""):
        super().__init__(message)
        self.code = code
        self.request_id = request_id


class TencentCloudClient:
    """Small Tencent Cloud API v3 client using the official TC3-HMAC-SHA256 flow."""

    def __init__(
        self,
        secret_id: str,
        secret_key: str,
        service: str,
        version: str,
        endpoint: str,
        region: str = "",
        timeout: int = 60,
    ):
        if not secret_id or not secret_key:
            raise TencentCloudAPIError("腾讯云 SecretId 或 SecretKey 未配置")
        self.secret_id = secret_id
        self.secret_key = secret_key
        self.service = service
        self.version = version
        self.endpoint = endpoint
        self.region = region
        self.timeout = timeout

    @staticmethod
    def _sha256(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _hmac(key: bytes, value: str) -> bytes:
        return hmac.new(key, value.encode("utf-8"), hashlib.sha256).digest()

    def signed_headers(self, action: str, payload: str, timestamp: int | None = None) -> dict[str, str]:
        timestamp = timestamp or int(time.time())
        date = datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d")
        content_type = "application/json; charset=utf-8"
        canonical_headers = f"content-type:{content_type}\nhost:{self.endpoint}\n"
        signed_headers = "content-type;host"
        canonical_request = "\n".join(
            ["POST", "/", "", canonical_headers, signed_headers, self._sha256(payload)]
        )
        credential_scope = f"{date}/{self.service}/tc3_request"
        string_to_sign = "\n".join(
            [
                "TC3-HMAC-SHA256",
                str(timestamp),
                credential_scope,
                self._sha256(canonical_request),
            ]
        )
        secret_date = self._hmac(("TC3" + self.secret_key).encode("utf-8"), date)
        secret_service = self._hmac(secret_date, self.service)
        secret_signing = self._hmac(secret_service, "tc3_request")
        signature = hmac.new(
            secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        authorization = (
            "TC3-HMAC-SHA256 "
            f"Credential={self.secret_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        headers = {
            "Authorization": authorization,
            "Content-Type": content_type,
            "Host": self.endpoint,
            "X-TC-Action": action,
            "X-TC-Timestamp": str(timestamp),
            "X-TC-Version": self.version,
        }
        if self.region:
            headers["X-TC-Region"] = self.region
        return headers

    def call(self, action: str, data: dict) -> dict:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        headers = self.signed_headers(action, payload)
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"https://{self.endpoint}", headers=headers, content=payload.encode("utf-8")
                )
                response.raise_for_status()
                body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise TencentCloudAPIError(f"腾讯云 {action} 请求失败：{exc}") from exc
        result = body.get("Response") or {}
        request_id = result.get("RequestId", "")
        if error := result.get("Error"):
            raise TencentCloudAPIError(
                f"腾讯云 {action} 返回错误：{error.get('Message', '未知错误')}",
                code=error.get("Code", ""),
                request_id=request_id,
            )
        return result
