from sqlalchemy import select
from app.core.enums import RoleCode
from app.db.session import SessionLocal
from app.models.entities import Department, Project, Role, User, Record
from app.core.security import hash_password

def test_head_sees_only_department_projects(client, head):
    with SessionLocal() as db:
        other_dept = Department(name="结构外协研发部")
        db.add(other_dept)
        db.flush()
        project = Project(
            name="外协部独立项目",
            code="EXT-2026",
            manager_id=None,
            department_id=other_dept.id,
        )
        db.add(project); db.commit()
    all_projects = client.get("/api/v1/projects", headers=head).json()["data"]
    names=[item["name"] for item in all_projects]
    assert "外协部独立项目" not in names
    assert any(name.startswith("研发中心-") for name in names)


def test_head_assignable_users_filter_by_department(client, head):
    with SessionLocal() as db:
        other_dept = db.scalar(select(Department).where(Department.name == "结构外协研发部"))
        if not other_dept:
            other_dept = Department(name="结构外协研发部")
            db.add(other_dept)
            db.flush()
        engineer_role = db.scalar(select(Role).where(Role.code == RoleCode.ENGINEER))
        if not engineer_role:
            db.rollback()
            raise AssertionError("工程师角色不存在，测试前置未加载")
        other_user = User(
            username="partner_engineer",
            name="外协部工程师",
            mobile="13922223333",
            password_hash=hash_password("Passw0rd!"),
            department_id=other_dept.id,
            roles=[engineer_role],
        )
        db.add(other_user)
        db.commit()
    users = client.get("/api/v1/users/assignable", headers=head).json()["data"]
    assert all(item["department"] != "结构外协研发部" for item in users)
    assert any(item["department"] == "研发部" for item in users)


def test_multiple_project_manager_scope_isolated_by_assignment(client):
    with SessionLocal() as db:
        manager_role = db.scalar(select(Role).where(Role.code == RoleCode.PROJECT_MANAGER))
        if not manager_role:
            raise AssertionError("PROJECT_MANAGER 角色不存在")

        depts=list(db.scalars(select(Department).where(Department.name.in_(["研发部","产品部"]))).all())
        if len(depts)<2:
            raise AssertionError("测试依赖部门种子")
        dept_a, dept_b = depts[0], depts[1]

        pm1 = User(
            username="pm_scope_a",
            name="PM_A",
            mobile="13811110001",
            password_hash=hash_password("Passw0rd!"),
            department_id=dept_a.id,
            roles=[manager_role],
        )
        pm2 = User(
            username="pm_scope_b",
            name="PM_B",
            mobile="13811110002",
            password_hash=hash_password("Passw0rd!"),
            department_id=dept_b.id,
            roles=[manager_role],
        )
        db.add_all([pm1, pm2]); db.flush()

        project_a = Project(name="PM专属项目A", code="PM-SCOPE-A", manager_id=pm1.id, department_id=dept_a.id, members=[])
        project_b = Project(name="PM专属项目B", code="PM-SCOPE-B", manager_id=pm2.id, department_id=dept_b.id, members=[])
        db.add_all([project_a, project_b]); db.commit()

    pm1_login = client.post("/api/v1/auth/login", json={"username":"pm_scope_a", "password":"Passw0rd!"})
    assert pm1_login.status_code == 200
    pm1_headers = {"Authorization": f"Bearer {pm1_login.json()['data']['access_token']}"}
    pm2_login = client.post("/api/v1/auth/login", json={"username":"pm_scope_b", "password":"Passw0rd!"})
    assert pm2_login.status_code == 200
    pm2_headers = {"Authorization": f"Bearer {pm2_login.json()['data']['access_token']}"}

    projects_a = [item["name"] for item in client.get("/api/v1/projects", headers=pm1_headers).json()["data"]]
    projects_b = [item["name"] for item in client.get("/api/v1/projects", headers=pm2_headers).json()["data"]]
    assert "PM专属项目A" in projects_a
    assert "PM专属项目B" not in projects_a
    assert "PM专属项目B" in projects_b
    assert "PM专属项目A" not in projects_b
