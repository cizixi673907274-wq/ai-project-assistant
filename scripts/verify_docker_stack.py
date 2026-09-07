#!/usr/bin/env python3
"""Verify the Docker stack, MinIO upload, Redis worker and XLSX download."""

from __future__ import annotations

import argparse
from io import BytesIO
import json
import time
import urllib.error
import urllib.request
from uuid import uuid4
from zipfile import ZipFile

from verify_workflow import call, login


def unwrap(raw: bytes):
    payload = json.loads(raw.decode())
    return payload.get("data", payload)


def health(origin: str):
    with urllib.request.urlopen(f"{origin}/health", timeout=10) as response:
        return json.loads(response.read().decode())


def upload_file(base: str, token: str, record_id: str):
    boundary = f"----ai-project-{uuid4().hex}"
    chunks: list[bytes] = []

    def field(name: str, value: str):
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            value.encode(),
            b"\r\n",
        ])

    field("record_id", record_id)
    field("media_type", "FILE")
    chunks.extend([
        f"--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="file"; filename="docker-smoke.txt"\r\n',
        b"Content-Type: text/plain\r\n\r\n",
        "AI项目助手 Docker MinIO 联调文件".encode(),
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ])
    request = urllib.request.Request(
        f"{base}/uploads/direct",
        data=b"".join(chunks),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return unwrap(response.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode(errors="replace")) from exc


def download(base: str, path: str, token: str) -> tuple[bytes, str]:
    request = urllib.request.Request(
        f"{base}{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read(), response.headers.get_content_type()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", default="http://127.0.0.1:5173")
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    origin = args.origin.rstrip("/")
    base = f"{origin}/api/v1"

    health_result = health(origin)
    if health_result.get("status") != "ok":
        raise RuntimeError(f"健康检查失败：{health_result}")

    admin = login(base, "admin")
    engineer = login(base, "engineer")
    runtime = call(base, "/system/runtime", token=admin)
    deadline = time.monotonic() + args.timeout
    while not runtime["queue"]["worker_online"] and time.monotonic() < deadline:
        time.sleep(0.5)
        runtime = call(base, "/system/runtime", token=admin)
    queue = runtime["queue"]
    if queue["mode"] != "redis" or queue["redis"] != "ok" or not queue["worker_online"]:
        raise RuntimeError(f"Redis/Worker 未就绪：{runtime['queue']}")

    project = call(base, "/projects", token=engineer)[0]
    record = call(
        base,
        "/records",
        "POST",
        engineer,
        {
            "title": "Docker 全栈联调记录",
            "content": "验证 PostgreSQL、Redis、MinIO、API、Worker 与 PC Web。",
            "project_id": project["id"],
            "priority": "MEDIUM",
        },
    )
    media = upload_file(base, engineer, record["id"])

    templates = call(base, "/export-templates", token=admin)
    if not templates:
        raise RuntimeError("缺少默认导出模板，请先运行种子脚本")
    job = call(
        base,
        "/exports",
        "POST",
        admin,
        {"template_id": templates[0]["id"], "record_ids": [record["id"]]},
    )
    deadline = time.monotonic() + args.timeout
    while job["status"] in {"PENDING", "PROCESSING"} and time.monotonic() < deadline:
        time.sleep(0.5)
        job = call(base, f"/exports/{job['id']}", token=admin)
    if job["status"] != "COMPLETED":
        raise RuntimeError(f"异步导出未完成：{job}")

    workbook, content_type = download(base, f"/exports/{job['id']}/download", admin)
    with ZipFile(BytesIO(workbook)) as archive:
        if "xl/workbook.xml" not in archive.namelist():
            raise RuntimeError("下载内容不是有效的 XLSX 文件")

    print(json.dumps({
        "health": health_result,
        "queue": runtime["queue"],
        "record_id": record["id"],
        "minio_media_id": media["id"],
        "export_job_id": job["id"],
        "export_status": job["status"],
        "export_content_type": content_type,
        "export_bytes": len(workbook),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
