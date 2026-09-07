# API

FastAPI 入口为 `app.main:app`，Swagger 位于 `/docs`。本地开发可使用 SQLite 默认值；完整环境使用根目录 `.env` 的 PostgreSQL、Redis、MinIO。

```bash
pip install -e '.[dev]'
alembic upgrade head
python -m app.db.seed
uvicorn app.main:app --reload
pytest
```
