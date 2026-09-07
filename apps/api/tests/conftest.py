import os
os.environ["DATABASE_URL"]="sqlite:///./test_ai_field.db"
os.environ["SECRET_KEY"]="test-secret-key-with-at-least-32-bytes"
os.environ["AI_PROVIDER"]="mock"
os.environ["ASR_PROVIDER"]="mock"
os.environ["OCR_PROVIDER"]="mock"
os.environ["AI_API_KEY"]=""
import pytest
from fastapi.testclient import TestClient
from app.db.base import Base
from app.db.session import engine
from app.db.seed import seed
from app.main import app

@pytest.fixture(scope="session",autouse=True)
def database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    seed()
    yield
    Base.metadata.drop_all(engine)

@pytest.fixture
def client():
    return TestClient(app)

def login(client,username):
    r=client.post("/api/v1/auth/login",json={"username":username,"password":"Passw0rd!"})
    assert r.status_code==200
    return {"Authorization":f"Bearer {r.json()['data']['access_token']}"}

@pytest.fixture
def engineer(client): return login(client,"engineer")
@pytest.fixture
def manager(client): return login(client,"manager")
@pytest.fixture
def admin(client): return login(client,"admin")
@pytest.fixture
def head(client): return login(client,"head")
