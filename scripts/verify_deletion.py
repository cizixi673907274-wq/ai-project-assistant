#!/usr/bin/env python3
"""Verify soft-delete flows for PC Web record center and project management."""

from __future__ import annotations

import argparse
import json
from uuid import uuid4

from verify_workflow import call, login


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000/api/v1")
    args = parser.parse_args()

    admin = login(args.base, "admin")
    engineer = login(args.base, "engineer")

    project = call(args.base, "/projects", token=engineer)[0]
    record = call(
        args.base,
        "/records",
        "POST",
        engineer,
        {
            "title": "删除功能验收记录",
            "content": "用于确认记录中心删除功能是否生效。",
            "project_id": project["id"],
            "priority": "LOW",
        },
    )
    call(args.base, f"/records/{record['id']}", "DELETE", engineer)
    records_after_delete = call(args.base, "/records", token=engineer)
    record_visible = any(item["id"] == record["id"] for item in records_after_delete)

    empty_project = call(
        args.base,
        "/projects",
        "POST",
        admin,
        {
            "name": "删除功能验收空项目",
            "code": f"DELETE-{uuid4().hex[:8].upper()}",
            "region": "深圳",
        },
    )
    call(args.base, f"/projects/{empty_project['id']}", "DELETE", admin)
    projects_after_delete = call(args.base, "/projects", token=admin)
    project_visible = any(item["id"] == empty_project["id"] for item in projects_after_delete)

    if record_visible:
        raise RuntimeError("记录删除后仍在记录中心列表中可见")
    if project_visible:
        raise RuntimeError("空项目删除后仍在项目管理列表中可见")

    print(
        json.dumps(
            {
                "record_deleted": record["id"],
                "project_deleted": empty_project["id"],
                "record_visible_after_delete": record_visible,
                "project_visible_after_delete": project_visible,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
