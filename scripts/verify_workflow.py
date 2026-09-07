#!/usr/bin/env python3
"""Run the complete record lifecycle against a running development API."""

from __future__ import annotations

import argparse
from io import BytesIO
import json
import time
import urllib.error
import urllib.request
from zipfile import ZipFile


def call(base: str, path: str, method: str = "GET", token: str | None = None, data=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data, ensure_ascii=False).encode() if data is not None else None
    request = urllib.request.Request(f"{base}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"{method} {path} -> HTTP {exc.code}: {detail}") from exc
    return payload.get("data", payload)


def login(base: str, username: str) -> str:
    return call(
        base,
        "/auth/login",
        "POST",
        data={"username": username, "password": "Passw0rd!"},
    )["access_token"]


def download(base: str, path: str, token: str, data) -> tuple[bytes, str]:
    request = urllib.request.Request(
        f"{base}{path}",
        data=json.dumps(data, ensure_ascii=False).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.read(), response.headers.get_content_type()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"POST {path} -> HTTP {exc.code}: {detail}") from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000/api/v1")
    args = parser.parse_args()

    engineer = login(args.base, "engineer")
    manager = login(args.base, "manager")
    project = call(args.base, "/projects", token=engineer)[0]
    engineer_user = next(
        user for user in call(args.base, "/users/assignable", token=manager)
        if user["username"] == "engineer"
    )

    record = call(
        args.base,
        "/records",
        "POST",
        engineer,
        {
            "title": "自动化闭环验收记录",
            "content": "猫眼灯结构试装时透镜卡扣与前壳加强筋干涉，需结构工程师确认改模方案。",
            "project_id": project["id"],
            "priority": "HIGH",
        },
    )
    record_id = record["id"]
    states = [record["status"]]

    record = call(args.base, f"/records/{record_id}/submit", "POST", engineer, {})
    states.append(record["status"])
    for _ in range(300):
        record = call(args.base, f"/records/{record_id}", token=engineer)
        if record["status"] not in {"SUBMITTED", "AI_PROCESSING"}:
            break
        time.sleep(0.5)
    states.append(record["status"])

    if record["status"] in {"SUBMITTED", "AI_PROCESSING"}:
        raise RuntimeError("等待 AI 分析超时")

    if record["status"] in {"AI_REVIEW_REQUIRED", "READY_TO_ASSIGN"}:
        record = call(
            args.base,
            f"/records/{record_id}/ai/confirm",
            "POST",
            manager,
            {"category": "研发技术问题", "priority": "HIGH"},
        )
        states.append(record["status"])

    record = call(
        args.base,
        f"/records/{record_id}/assign",
        "POST",
        manager,
        {"assignee_id": engineer_user["id"]},
    )
    states.append(record["status"])
    record = call(
        args.base,
        f"/records/{record_id}/process",
        "POST",
        engineer,
        {"response": "已检查接线并更换通讯模块。"},
    )
    states.append(record["status"])
    record = call(
        args.base,
        f"/records/{record_id}/resolve",
        "POST",
        engineer,
        {"response": "连续运行测试通过，问题已解决。"},
    )
    states.append(record["status"])
    record = call(
        args.base,
        f"/records/{record_id}/close",
        "POST",
        manager,
        {"note": "闭环验收通过。"},
    )
    states.append(record["status"])
    events = call(args.base, f"/records/{record_id}/events", token=manager)
    visible_records = call(args.base, "/records", token=manager)
    first_export_record = next(item for item in visible_records if item["id"] == record_id)
    second_export_record = next(
        (
            item
            for item in visible_records
            if item["id"] != record_id and item["title"] != first_export_record["title"]
        ),
        None,
    )
    export_records = [first_export_record]
    if second_export_record:
        export_records.append(second_export_record)
    if len(export_records) < 2:
        raise RuntimeError("批量导出验收至少需要两条可见记录")
    document, content_type = download(
        args.base,
        "/records/batch-export",
        manager,
        {"record_ids": [item["id"] for item in export_records]},
    )
    with ZipFile(BytesIO(document)) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
    missing_titles = [
        item["title"] for item in export_records if item["title"] not in document_xml
    ]
    if missing_titles:
        raise RuntimeError(f"批量汇总文档缺少记录：{missing_titles}")

    print(json.dumps({
        "record_id": record_id,
        "title": record["title"],
        "project": project["name"],
        "states": states,
        "final_status": record["status"],
        "event_count": len(events),
        "event_types": [item["event_type"] for item in events],
        "batch_export": {
            "record_count": len(export_records),
            "record_titles": [item["title"] for item in export_records],
            "content_type": content_type,
            "document_bytes": len(document),
            "contains_table": "<w:tbl" in document_xml,
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
