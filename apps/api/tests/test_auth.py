def test_password_login_and_me(client,engineer):
    r=client.get("/api/v1/me",headers=engineer)
    assert r.status_code==200
    assert r.json()["data"]["username"]=="engineer"
    assert "ENGINEER" in r.json()["data"]["roles"]
def test_wechat_mock_login(client):
    r=client.post("/api/v1/auth/wechat/login",json={"code":"wx-code-001"})
    assert r.status_code==200
    assert r.json()["data"]["access_token"]
def test_bad_password(client):
    assert client.post("/api/v1/auth/login",json={"username":"admin","password":"wrong"}).status_code==401

def test_mobile_verification_login(client):
    sent=client.post("/api/v1/auth/sms/send",json={"mobile":"13800005678"})
    assert sent.status_code==200
    assert sent.json()["data"]["dev_code"]=="123456"
    invalid=client.post("/api/v1/auth/mobile/login",json={"mobile":"13800005678","code":"000000"})
    assert invalid.status_code==401
    logged_in=client.post("/api/v1/auth/mobile/login",json={"mobile":"13800005678","code":"123456"})
    assert logged_in.status_code==200
    token=logged_in.json()["data"]["access_token"]
    assert client.get("/api/v1/me",headers={"Authorization":f"Bearer {token}"}).json()["data"]["name"]=="陈工"
    direct=client.post("/api/v1/auth/mobile/login",json={"mobile":"13800005678","code":"123456"})
    assert direct.status_code==200
