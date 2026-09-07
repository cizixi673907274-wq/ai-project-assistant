def test_project_management(client,manager):
    members=client.get("/api/v1/users/assignable",headers=manager).json()["data"]
    payload={"name":"第二阶段验收项目","code":"P900","member_ids":[m["id"] for m in members[:2]]}
    created=client.post("/api/v1/projects",headers=manager,json=payload)
    assert created.status_code==201
    project=created.json()["data"]
    assert project["name"]=="第二阶段验收项目"
    assert len(project["members"])==len(payload["member_ids"])
    updated=client.patch(f"/api/v1/projects/{project['id']}",headers=manager,json={"status":"ARCHIVED"})
    assert updated.status_code==200
    assert updated.json()["data"]["status"]=="ARCHIVED"

def test_engineer_sees_projects_where_they_are_a_member(client,engineer):
    projects=client.get("/api/v1/projects",headers=engineer)
    assert projects.status_code==200
    rows=projects.json()["data"]
    assert rows
    assert all(any(member["username"]=="engineer" for member in row["members"]) for row in rows)


def test_record_and_project_soft_delete(client,manager,engineer):
    engineer_id=next(user["id"] for user in client.get("/api/v1/users/assignable",headers=manager).json()["data"] if user["username"]=="engineer")
    project=client.post("/api/v1/projects",headers=manager,json={"name":"删除功能验收项目","code":"DELETE-P900","member_ids":[engineer_id]}).json()["data"]
    record=client.post("/api/v1/records",headers=engineer,json={"project_id":project["id"],"content":"用于验证记录与项目删除权限和软删除过滤"}).json()["data"]

    blocked=client.delete(f"/api/v1/projects/{project['id']}",headers=manager)
    assert blocked.status_code==409
    assert blocked.json()["error"]["code"]=="PROJECT_HAS_RECORDS"

    deleted_record=client.delete(f"/api/v1/records/{record['id']}",headers=manager)
    assert deleted_record.status_code==200
    assert deleted_record.json()["data"]["deleted"] is True
    assert client.get(f"/api/v1/records/{record['id']}",headers=manager).status_code==404
    assert all(item["id"]!=record["id"] for item in client.get("/api/v1/records",headers=manager).json()["data"])

    deleted_project=client.delete(f"/api/v1/projects/{project['id']}",headers=manager)
    assert deleted_project.status_code==200
    assert deleted_project.json()["data"]["deleted"] is True
    assert all(item["id"]!=project["id"] for item in client.get("/api/v1/projects",headers=manager).json()["data"])

def test_notifications_and_collaboration(client,admin):
    notifications=client.get("/api/v1/notifications",headers=admin)
    assert notifications.status_code==200
    assert len(notifications.json()["data"])>=3
    unread=client.get("/api/v1/notifications/unread-count",headers=admin).json()["data"]["count"]
    assert unread>=3
    assert client.post("/api/v1/notifications/read-all",headers=admin).status_code==200
    assert client.get("/api/v1/notifications/unread-count",headers=admin).json()["data"]["count"]==0

    records=client.get("/api/v1/records",headers=admin).json()["data"]
    active=next(record for record in records if record["status"] in {"ASSIGNED","IN_PROGRESS"})
    comment=client.post(f"/api/v1/records/{active['id']}/comments",headers=admin,json={"content":"第二阶段协作评论测试"})
    assert comment.status_code==201
    comments=client.get(f"/api/v1/records/{active['id']}/comments",headers=admin).json()["data"]
    assert any(item["content"]=="第二阶段协作评论测试" for item in comments)
    reminded=client.post(f"/api/v1/records/{active['id']}/remind",headers=admin,json={})
    assert reminded.status_code==200
    assert reminded.json()["data"]["notified"]==1

    assignee=client.get("/api/v1/users/assignable",headers=admin).json()["data"][0]
    reassigned=client.post(f"/api/v1/records/{active['id']}/reassign",headers=admin,json={"assignee_id":assignee["id"],"note":"第二阶段转派测试"})
    assert reassigned.status_code==200
    assert reassigned.json()["data"]["status"]=="ASSIGNED"

def test_engineer_task_list_and_direct_upload(client,engineer,admin,monkeypatch):
    users=client.get("/api/v1/users/assignable",headers=admin).json()["data"]
    engineer_id=next(user["id"] for user in users if user["username"]=="engineer")
    overdue_record=client.post("/api/v1/records",headers=engineer,json={"content":"逾期任务识别验收记录，需要尽快处理"}).json()["data"]
    client.post(f"/api/v1/records/{overdue_record['id']}/submit",headers=engineer)
    client.post(f"/api/v1/records/{overdue_record['id']}/ai/confirm",headers=admin,json={})
    assigned=client.post(f"/api/v1/records/{overdue_record['id']}/assign",headers=admin,json={"assignee_id":engineer_id,"due_at":"2020-01-01T00:00:00Z"})
    assert assigned.status_code==200
    tasks=client.get("/api/v1/tasks/my",headers=engineer)
    assert tasks.status_code==200
    assert len(tasks.json()["data"])>=1
    assert {"due_at","overdue","reminder_count"}.issubset(tasks.json()["data"][0])
    assert any(task["record_id"]==overdue_record["id"] and task["overdue"] for task in tasks.json()["data"])

    record=client.post("/api/v1/records",headers=engineer,json={"content":"小程序直传附件验收记录"}).json()["data"]
    class Storage:
        def bucket_exists(self,_): return True
        def make_bucket(self,_): pass
        def put_object(self,*args,**kwargs): return None
    from app.api.routes import uploads
    monkeypatch.setattr(uploads,"client",lambda:Storage())
    uploaded=client.post("/api/v1/uploads/direct",headers=engineer,data={"record_id":record["id"],"media_type":"IMAGE"},files={"file":("现场照片.jpg",b"image-bytes","image/jpeg")})
    assert uploaded.status_code==200
    assert uploaded.json()["data"]["type"]=="IMAGE"
    transcribed=client.post("/api/v1/uploads/transcribe-direct",headers=engineer,files={"file":("现场语音.mp3",b"audio-bytes","audio/mpeg")})
    assert transcribed.status_code==200
    assert "transcript" in transcribed.json()["data"]

def test_project_report_export_and_overdue_scan(client,admin):
    projects=client.get("/api/v1/projects",headers=admin).json()["data"]
    project=next(item for item in projects if item["record_count"]>0)
    overview=client.get(f"/api/v1/reports/overview?project_id={project['id']}",headers=admin)
    assert overview.status_code==200
    assert overview.json()["data"]["record_count"]==project["record_count"]
    exported=client.post(f"/api/v1/reports/projects/{project['id']}/export",headers=admin)
    assert exported.status_code==200
    assert exported.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert exported.content[:2]==b"PK"
    history=client.get(f"/api/v1/reports/exports?project_id={project['id']}",headers=admin).json()["data"]
    assert history[0]["project_id"]==project["id"]
    assert history[0]["record_count"]==project["record_count"]

    first=client.post("/api/v1/tasks/scan-overdue",headers=admin)
    second=client.post("/api/v1/tasks/scan-overdue",headers=admin)
    assert first.status_code==200 and second.status_code==200
    assert second.json()["data"]["notifications_created"]==0


def test_departments_and_project_department_scoping(client,admin):
    depts=client.get("/api/v1/admin/departments",headers=admin).json()["data"]
    assert len(depts)>=2
    headquarter,dept2=depts[0],depts[1]
    manager_payload={"username":"pm_extra","name":"额外项目经理","mobile":"13899990000","password":"Passw0rd!","department_id":dept2["id"],"role":"PROJECT_MANAGER"}
    manager=client.post("/api/v1/admin/users",headers=admin,json=manager_payload)
    assert manager.status_code==201
    token=client.post("/api/v1/auth/login",json={"username":"pm_extra","password":"Passw0rd!"}).json()["data"]["access_token"]
    pm_headers={"Authorization":f"Bearer {token}"}
    mismatch=client.post("/api/v1/projects",headers=pm_headers,json={"name":"部门校验项目","code":"DEPT-VAL","department_id":headquarter["id"]})
    assert mismatch.status_code==422
    assert mismatch.json()["error"]["code"]=="INVALID_DEPARTMENT_SCOPE"

    created=client.post("/api/v1/projects",headers=pm_headers,json={"name":"部门一致项目","code":"DEPT-CHECK","department_id":dept2["id"]})
    assert created.status_code==201
    assert created.json()["data"]["department_id"]==dept2["id"]
