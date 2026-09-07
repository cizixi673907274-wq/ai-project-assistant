def test_engineer_cannot_manage_users(client,engineer):
    assert client.get("/api/v1/admin/users",headers=engineer).status_code==403
def test_admin_can_list_users(client,admin):
    r=client.get("/api/v1/admin/users",headers=admin)
    assert r.status_code==200
    assert all(set(user["roles"])&{"PROJECT_MANAGER","DEPARTMENT_HEAD"} for user in r.json()["data"])
def test_record_visibility_is_filtered(client,engineer):
    assert client.get("/api/v1/records",headers=engineer).status_code==200

def test_manager_can_list_assignable_users(client,manager):
    r=client.get("/api/v1/users/assignable",headers=manager)
    assert r.status_code==200
    assert any(user["username"]=="engineer" for user in r.json()["data"])

def test_engineer_cannot_list_assignable_users(client,engineer):
    assert client.get("/api/v1/users/assignable",headers=engineer).status_code==403

def test_admin_creates_supervisor_and_manager_creates_team_engineer(client,admin,manager):
    department_id=client.get("/api/v1/me",headers=manager).json()["data"]["department_id"]
    rejected=client.post("/api/v1/admin/users",headers=admin,json={"username":"qa_wrong_role","name":"不应创建","password":"Passw0rd!","department_id":department_id,"role":"ENGINEER"})
    assert rejected.status_code==403

    created=client.post("/api/v1/admin/users",headers=admin,json={"username":"qa_supervisor","name":"验收主管","password":"Passw0rd!","department_id":department_id,"role":"PROJECT_MANAGER"})
    assert created.status_code==201
    member=created.json()["data"]
    assert member["roles"]==["PROJECT_MANAGER"]
    updated=client.patch(f"/api/v1/admin/users/{member['id']}",headers=admin,json={"name":"验收主管已更新","status":"DISABLED"})
    assert updated.status_code==200
    assert updated.json()["data"]["status"]=="DISABLED"

    engineer_created=client.post("/api/v1/admin/users",headers=manager,json={"username":"qa_engineer","name":"验收工程师","password":"Passw0rd!","role":"ENGINEER"})
    assert engineer_created.status_code==201
    engineer_user=engineer_created.json()["data"]
    assert engineer_user["roles"]==["ENGINEER"]
    assert engineer_user["department_id"]==department_id
    assert client.post("/api/v1/admin/users",headers=manager,json={"username":"qa_manager_forbidden","name":"越权主管","password":"Passw0rd!","role":"PROJECT_MANAGER"}).status_code==403
    manager_rows=client.get("/api/v1/admin/users",headers=manager).json()["data"]
    assert all(user["roles"]==["ENGINEER"] and user["department_id"]==department_id for user in manager_rows)

def test_manager_directly_creates_and_assigns_record_without_ai(client,manager,engineer):
    project=client.get("/api/v1/projects",headers=manager).json()["data"][0]
    assignee=next(user for user in client.get("/api/v1/users/assignable",headers=manager).json()["data"] if user["username"]=="engineer")
    created=client.post("/api/v1/records/manager-create",headers=manager,json={"title":"主管创建的联调任务","content":"检查猫眼灯主板与结构件装配间隙","project_id":project["id"],"assignee_id":assignee["id"],"priority":"HIGH"})
    assert created.status_code==201
    record=created.json()["data"]
    assert record["status"]=="ASSIGNED"
    assert record["summary"] is None
    my_tasks=client.get("/api/v1/tasks/my",headers=engineer).json()["data"]
    assert any(task["record_id"]==record["id"] for task in my_tasks)

def test_admin_can_create_and_rename_team_but_manager_cannot(client,admin,manager):
    assert client.post("/api/v1/admin/departments",headers=manager,json={"name":"越权团队"}).status_code==403
    created=client.post("/api/v1/admin/departments",headers=admin,json={"name":"研发验收团队"})
    assert created.status_code==201
    team=created.json()["data"]
    renamed=client.patch(f"/api/v1/admin/departments/{team['id']}",headers=admin,json={"name":"研发验收团队（已改名）"})
    assert renamed.status_code==200
    assert renamed.json()["data"]["name"]=="研发验收团队（已改名）"
    assert client.post("/api/v1/admin/departments",headers=admin,json={"name":"研发验收团队（已改名）"}).status_code==409
