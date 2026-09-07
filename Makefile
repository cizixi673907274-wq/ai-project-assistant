.PHONY: install up-local seed-local up down test build seed migrate
install:
	pnpm install
	cd apps/api && python -m pip install -e '.[dev]'

up-local:
	@bash scripts/run_local_stack.sh

seed-local:
	@cd apps/api && DATABASE_URL=$${DATABASE_URL:-sqlite:///./ai_field.db} TASK_QUEUE_MODE=$${TASK_QUEUE_MODE:-inline} WECHAT_MOCK=$${WECHAT_MOCK:-true} python -m app.db.seed

up:
	docker compose up --build
down:
	docker compose down
test:
	cd apps/api && pytest
	pnpm typecheck
build:
	pnpm build
migrate:
	cd apps/api && alembic upgrade head
seed:
	cd apps/api && python -m app.db.seed
