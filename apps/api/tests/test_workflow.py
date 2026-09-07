from app.db.session import SessionLocal
from app.models.entities import User
from sqlalchemy import select
from io import BytesIO
from zipfile import ZipFile
def test_complete_record_workflow(client,engineer,manager):
    created=client.post("/api/v1/records",headers=engineer,json={"content":"猫眼灯结构试装时透镜卡扣与前壳加强筋干涉，需要结构工程师确认改模方案"})
    assert created.status_code==201
    rid=created.json()["data"]["id"]
    submitted=client.post(f"/api/v1/records/{rid}/submit",headers=engineer)
    assert submitted.status_code==200
    detail=client.get(f"/api/v1/records/{rid}",headers=manager).json()["data"]
    assert detail["status"]=="READY_TO_ASSIGN"
    assert detail["confidence"]>=.85
    confirmed=client.post(f"/api/v1/records/{rid}/ai/confirm",headers=manager,json={"category":"研发技术问题","priority":"HIGH"})
    assert confirmed.status_code==200
    db=SessionLocal(); assignee=db.scalar(select(User).where(User.username=="engineer")); assignee_id=assignee.id; db.close()
    assigned=client.post(f"/api/v1/records/{rid}/assign",headers=manager,json={"assignee_id":assignee_id})
    assert assigned.json()["data"]["status"]=="ASSIGNED"
    processed=client.post(f"/api/v1/records/{rid}/process",headers=engineer,json={"response":"已检查前壳加强筋位置，并输出改模建议"})
    assert processed.json()["data"]["status"]=="IN_PROGRESS"
    resolved=client.post(f"/api/v1/records/{rid}/resolve",headers=engineer,json={"response":"试模件复装后卡扣扣合正常，问题已解决"})
    assert resolved.json()["data"]["status"]=="RESOLVED"
    closed=client.post(f"/api/v1/records/{rid}/close",headers=manager,json={"note":"工程师确认后关闭"})
    assert closed.json()["data"]["status"]=="CLOSED"
    events=client.get(f"/api/v1/records/{rid}/events",headers=manager).json()["data"]
    assert len(events)>=8
    assert events[-1]["event_type"]=="CLOSE_NOTE"
    exported=client.get(f"/api/v1/records/{rid}/export",headers=manager)
    assert exported.status_code==200
    assert exported.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert "attachment" in exported.headers["content-disposition"]
    with ZipFile(BytesIO(exported.content)) as archive:
        document_xml=archive.read("word/document.xml").decode("utf-8")
    assert "研发记录归档" in document_xml
    assert "试模件复装后卡扣扣合正常" in document_xml
    second=client.post(
        "/api/v1/records",
        headers=engineer,
        json={
            "title":"批量汇总第二条记录",
            "content":"用于验证多条记录能够按选择顺序整理到同一个表格文档。",
        },
    )
    assert second.status_code==201
    second_id=second.json()["data"]["id"]
    batch=client.post("/api/v1/records/batch-export",headers=manager,json={"record_ids":[rid,second_id]})
    assert batch.status_code==200
    assert batch.headers["content-type"].startswith("application/vnd.openxmlformats")
    with ZipFile(BytesIO(batch.content)) as archive:
        batch_xml=archive.read("word/document.xml").decode("utf-8")
    assert "研发记录批量汇总表" in batch_xml
    assert "研发技术问题" in batch_xml
    assert "批量汇总第二条记录" in batch_xml
    assert batch_xml.index("猫眼灯结构试装时透镜卡扣") < batch_xml.index("批量汇总第二条记录")
def test_invalid_state_transition(client,engineer):
    r=client.post("/api/v1/records",headers=engineer,json={"content":"草稿不能直接再次提交以外的状态"})
    rid=r.json()["data"]["id"]
    assert client.post(f"/api/v1/records/{rid}/submit",headers=engineer).status_code==200
    assert client.post(f"/api/v1/records/{rid}/submit",headers=engineer).status_code==409
