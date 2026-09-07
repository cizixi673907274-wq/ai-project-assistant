# AI 项目助手

MIT 开源版 · PC 管理端 / 微信小程序 / H5 / FastAPI 后端

> **使用前请先启动项目。** 本仓库发布的是源码，未提供在线演示站。文中的 `localhost` 指访问者自己的电脑，只有在该电脑上启动本项目后才能使用；直接打开这些地址可能进入电脑上运行的其他应用。

本仓库提供可自部署的应用源码。默认使用 Mock AI 与演示账号，适合本地体验；真实 AI、微信和对象存储需自行配置。GitHub Pages 只能承载静态前端，完整应用需要独立运行后端及数据服务。

原始归档中的生产配置、数据库、历史附件和私人部署资料不属于本仓库。

面向研发中心产品开发的记录与问题闭环 Monorepo。结构工程师、软件工程师、模具工程师通过微信小程序提交文字、语音、图片或附件；AI 异步完成结构化分析；项目负责人在 PC Web 确认、分派、跟进并关闭记录。

## 已实现范围

- FastAPI + SQLAlchemy + Alembic + PostgreSQL，Redis 与 MinIO 基础设施
- JWT access/refresh token、微信 `code2session` Mock、四角色 RBAC 与后端数据范围过滤
- `records`、`record_media`、`ai_analyses`、`tasks`、`record_events` 及组织/项目模型
- MinIO 15 分钟签名上传、文件登记、Mock/腾讯云语音转写与图片文字识别
- 可替换的 `LLMProvider` / `ASRProvider` / `OCRProvider`；真实服务支持结构校验、自动重试、失败留痕和调用指标
- 后端校验的“提交—AI分析—确认—分派—处理—关闭”状态机和完整审计事件
- Taro 微信小程序：微信登录、项目选择、文字/录音/图片/文件提交、个人待办、逾期提示和订阅通知
- React 管理端：工作台、记录中心、项目管理、AI待确认、项目风险、报告中心、Excel 模板中心、成员与权限、集成设置
- 第二阶段协作：真实通知中心、项目成员维护、协作评论、催办、转派和任务通知
- 项目运营闭环：项目 Word 报告、导出历史留痕、闭环指标和幂等逾期任务扫描
- P3 导出能力：可配置 Excel 字段模板、后台导出任务、完成通知、权限化下载和公式注入防护
- Swagger、初始迁移、种子数据、认证/状态机/AI分派/越权测试

## 目录

```text
apps/api             FastAPI 服务、迁移、种子与测试
apps/admin-web       React + Vite + Ant Design 管理端
apps/miniapp         Taro + React 微信小程序
packages/api-client  共享 API Client
packages/shared-types 共享状态和前端类型
packages/ui-tokens   视觉设计令牌
infra                部署与种子扩展目录
docs                 架构与接口扩展目录
```

## 下载并在本机启动（Docker）

要求 Docker Desktop 与 Docker Compose v2。

```bash
git clone https://github.com/cizixi673907274-wq/ai-project-assistant.git
cd ai-project-assistant
cp .env.example .env
docker compose up --build
```

开发 Compose 的端口仅绑定本机回环地址。真机联调需自行调整绑定、CORS 与 API 地址，并限制访问范围。

确认上述命令启动成功、容器健康后，在同一台电脑访问以下地址（本地入口，不是线上链接）：

- PC Web：`http://localhost:5173`
- API：`http://localhost:8000`
- Swagger：`http://localhost:8000/docs`
- ReDoc：`http://localhost:8000/redoc`
- MinIO Console：`http://localhost:9001`（`minioadmin` / `minioadmin`）
- PostgreSQL：`localhost:5432`
- Redis：`localhost:6379`

API 容器启动时会自动运行 `alembic upgrade head` 和幂等种子脚本。

容器全部健康后，执行完整 Docker Smoke Test：

```bash
python scripts/verify_docker_stack.py
python scripts/verify_workflow.py
python scripts/verify_deletion.py
```

第一条命令会验证 Nginx、API、PostgreSQL、Redis Worker、MinIO 文件上传和异步 Excel 下载；第二条命令验证“提交—AI分析—确认—分派—处理—关闭”以及多记录 Word 汇总；第三条命令验证 PC Web 记录中心删除记录、项目管理删除空项目。

## 本地开发

需要 Node.js 22+、pnpm 11（项目固定为 11.9.0）、Python 3.11+，以及通过 Compose 启动 PostgreSQL/Redis/MinIO。

```bash
cp .env.example .env
corepack enable
pnpm install --frozen-lockfile
python3 -m venv .venv
source .venv/bin/activate
pip install -e 'apps/api[dev]'

docker compose up -d postgres redis minio
# 容器内主机名不可用于本机进程；覆盖为本机地址。
export DATABASE_URL=postgresql+psycopg://ai_field:ai_field@localhost:5432/ai_field
export REDIS_URL=redis://localhost:6379/0
export MINIO_ENDPOINT=localhost:9000
cd apps/api && alembic upgrade head && python -m app.db.seed
uvicorn app.main:app --reload
```

新终端启动管理端：

```bash
pnpm dev:admin
```

新终端持续构建微信小程序：

```bash
pnpm dev:miniapp
```

手机真机预览前，先让小程序产物使用当前电脑局域网 API 地址：

```bash
pnpm miniapp:preview
```

然后在微信开发者工具中导入 `apps/miniapp`，小程序目录选择 `dist`。开发 AppID 使用 `touristappid`，真实联调时请替换 `project.config.json` 的 AppID，并把 API 域名加入微信后台合法域名。

需要在浏览器中验收小程序三页时，执行 `pnpm --filter @ai-field/miniapp build:h5`，再将 `apps/miniapp/dist-h5` 作为静态站点目录。H5 与微信产物分目录保存，不会相互覆盖。

## 演示账号

以下均为源码中生成的演示数据，不用于真实业务。种子用户密码统一为 `Passw0rd!`：

| 账号 | 姓名 | 角色 |
| --- | --- | --- |
| `engineer` | 陈工 | 工程师 |
| `manager` | 李工 | 项目经理 |
| `head` | 王工 | 部门负责人 |
| `admin` | 赵主管 | 超级管理员 |

微信 Mock 登录请求 `POST /api/v1/auth/wechat/login`，任意开发 `code` 会绑定种子工程师账号。

种子项目与记录默认使用研发中心产品开发场景，覆盖猫眼灯、防爆标志灯、吸顶灯、应急照明模块、嵌入式控制板等项目，以及结构设计、软件联调、模具工艺和可靠性测试类问题。

## 测试与构建

```bash
cd apps/api && pytest
cd ../.. && pnpm typecheck
pnpm build
```

### 本地服务排查

如果 `localhost:5173` 显示其他应用，说明访问到了该端口上的其他服务，不能据此判断本项目已启动。Docker 遇到端口占用会报错；Vite 开发服务也可能自动换用其他端口，应以终端输出的实际地址为准。

Docker 管理端端口冲突时，可将 `docker-compose.yml` 中 `admin-web` 的 `127.0.0.1:5173:80` 改为一个未占用的端口，例如 `127.0.0.1:5183:80`，重新启动后访问 `http://localhost:5183`。不要停止不属于本项目的服务。

如果 5173/8000 无法访问，先检查启动日志。在已安装依赖且端口可用的情况下，可运行：

```bash
make up-local
```

这会使用本地 SQLite 与内联队列模式，在当前机器启动：

- API：`http://127.0.0.1:8000`
- PC Web：`http://127.0.0.1:5173`

运行时可快速自检：

```bash
curl -I http://127.0.0.1:8000/health
curl -I http://127.0.0.1:5173
```

如仍打不开，检查：

1. 当前机器端口是否被占用；
2. `.env` 中 `VITE_API_BASE_URL`、`TARO_APP_API_BASE_URL`；
3. 防火墙/代理是否拦截 8000/5173。

发布检查结果见 [发布说明](docs/release-notes.md)。

Excel 导出在直接运行 API 时默认采用 `TASK_QUEUE_MODE=inline`，便于无 Redis 的本地开发；Docker Compose 会强制切换为 `redis`，由独立 Worker 持久处理。任务失败最多自动重试 3 次，默认保留导出文件 7 天，过期后自动删除文件但保留任务记录，可在模板中心重新生成。管理端“集成设置”会显示 Worker、队列深度、失败任务和保留策略。

## 第三阶段 AI / 语音 / OCR 配置

默认配置保持 `AI_PROVIDER=mock`、`ASR_PROVIDER=mock`、`OCR_PROVIDER=mock`，无需外部密钥即可完整运行。接入兼容接口时设置：

```bash
AI_PROVIDER=openai_compatible
ASR_PROVIDER=openai_compatible
AI_BASE_URL=https://api.openai.com/v1
AI_API_STYLE=chat_completions
AI_API_KEY=your-api-key
AI_MODEL=gpt-4o-mini
ASR_MODEL=whisper-1
AI_MAX_RETRIES=1
AI_PROMPT_VERSION=phase3-v1
```

`AI_API_STYLE` 支持 `chat_completions` 和 `responses`。火山方舟新版 Responses API 可配置为：

```bash
AI_PROVIDER=openai_compatible
ASR_PROVIDER=mock
AI_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
AI_API_STYLE=responses
AI_MODEL=已在方舟控制台开通的 endpoint id
```

Doubao-Seed-2.1-pro 等模型在方舟侧通常通过 endpoint id 调用，因此 `AI_MODEL` 填 `ep-...` 形式的 endpoint。AI 与语音可以分别启用；当前如果没有单独接入语音转写服务，建议先保持 `ASR_PROVIDER=mock`，小程序录音仍会生成可测试的转写文本。真实 AI 输出会经过严格结构校验并自动重试一次；仍失败时记录错误并进入“AI 待确认”，不会阻塞业务记录。管理端“集成设置”可检查就绪状态，接口不会返回任何密钥。

腾讯云一句话识别与“通用印刷体识别”可共用一组腾讯云 API 访问密钥：

```bash
ASR_PROVIDER=tencent_cloud
OCR_PROVIDER=tencent_cloud
TENCENT_SECRET_ID=your-secret-id
TENCENT_SECRET_KEY=your-secret-key
TENCENT_REGION=ap-guangzhou
TENCENT_APP_ID=your-asr-app-id
TENCENT_ASR_ENGINE=16k_zh
OCR_LANGUAGE_TYPE=zh
```

ASR 使用 `SentenceRecognition`，单段录音默认限制 3MB；OCR 使用资源包对应的 `GeneralBasicOCR`，原图默认限制 7MB，并将识别结果单独保存为附件的 `extracted_text`。SecretKey 只能写入服务器 `.env.production`，不能提交到代码或前端。

记录中心支持按权限软删除记录：创建人可删除自己的草稿，项目经理或超级管理员可删除其他记录。项目管理支持删除空项目；项目仍有有效记录时会阻止删除并提示先删除或迁移记录，避免误删关联业务数据。

正式微信登录关闭 `WECHAT_MOCK` 后，首次登录必须同时提交管理员预先登记的员工手机号；系统不会根据任意微信身份自动创建内部员工账号。

## 生产试点部署

复制 `.env.production.example` 为 `.env.production`，替换所有占位密码和密钥，然后运行：

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

生产模式会在 API 启动时检查弱密钥、Mock Provider 和微信配置，未达到要求时拒绝启动。详细步骤见 [`docs/deployment/production.md`](docs/deployment/production.md)。

## 核心接口

| 动作 | 接口 |
| --- | --- |
| 登录 / 微信 Mock | `POST /api/v1/auth/login`、`POST /api/v1/auth/wechat/login` |
| 当前用户 | `GET /api/v1/me` |
| 创建 / 查询 / 删除记录 | `POST /api/v1/records`、`GET /api/v1/records`、`DELETE /api/v1/records/{id}` |
| 提交 / AI确认 | `POST /records/{id}/submit`、`POST /records/{id}/ai/confirm` |
| 分派 / 处理 / 解决 / 关闭 | `POST /records/{id}/assign|process|resolve|close` |
| 审计流转 | `GET /records/{id}/events` |
| 项目管理 | `GET/POST /projects`、`PATCH /projects/{id}`、`DELETE /projects/{id}` |
| 评论 / 催办 / 转派 | `GET/POST /records/{id}/comments`、`POST /records/{id}/remind|reassign` |
| 通知中心 | `GET /notifications`、`PATCH /notifications/{id}/read`、`POST /notifications/read-all` |
| 报告中心 | `GET /reports/overview|exports`、`POST /reports/projects/{id}/export` |
| Excel 模板 | `GET/POST /export-templates`、`PATCH /export-templates/{id}` |
| 异步 Excel 导出 | `POST/GET /exports`、`GET /exports/{id}/download`、`POST /exports/{id}/retry` |
| 导出文件清理 | `POST /exports/maintenance/cleanup`（超级管理员） |
| 逾期扫描 | `POST /tasks/scan-overdue` |
| 上传 / ASR / OCR | `POST /uploads/presign|complete`、`POST /uploads/transcribe-direct|ocr-direct`、`POST /uploads/{media_id}/transcribe|ocr` |
| 文件安全下载 | `GET /uploads/{media_id}/download-url` |
| 集成与运行状态 | `GET /system/integrations`、`GET /system/runtime` |
| 工作台 / 风险 / 成员 | `GET /dashboard/overview`、`GET /projects/risks`、`GET /admin/users` |

所有 `/api/v1` 成功响应为 `{ success, data, message, request_id }`；错误响应带稳定错误码、可行动中文提示和 `request_id`。

## 安全说明

`.env.example` 只含开发默认值。部署前必须更换 `SECRET_KEY`、数据库与 MinIO 密码，使用 HTTPS，把对象存储置于私网，并配置正式微信 `code2session`。数据权限在后端执行，状态迁移与管理操作写入 `record_events`。

角色命名、PC Web 可见范围和成员管理边界见 [`docs/roles-and-permissions.md`](docs/roles-and-permissions.md)。

## 管理端“多项目经理”配置清单（本版本）

本版本已将权限收口为：
- 项目经理：仅可查看与处理**自己负责项目**；
- 部门负责人：可查看与处理本部门项目；
- 超级管理员：可查看全部，且可为任意项目配置负责人与成员。

建议按以下流程验收：

1. 登录管理员账号（`admin`）进入成员管理，确认存在以下角色用户：
   - `PROJECT_MANAGER`（每个项目经理一人）
   - `DEPARTMENT_HEAD`（按你的组织需要可选）
2. 在“成员与权限”里创建/更新成员时，给成员分配 `PROJECT_MANAGER`，并绑定所属 `department`（项目经理建议按部门归属管理）。
3. 在“项目管理”里为每个项目创建时：
   - `manager_id` 选择该项目经理；
   - `member_ids` 选择该项目相关成员；
   - `code/name` 按唯一项目标识命名；
   - 保存后再次调用 `GET /api/v1/projects` 验证只返回该经理可见项目。
4. 验证权限边界：
   - 以经理 A 账号登录 `/api/v1/projects`，应只看到自己负责项目；
   - 切到经理 B 账号登录，同样只看到自己负责项目；
   - 管理员登录应能看到全部项目；
   - 经理尝试处理非本项目记录，`/api/v1/records/{id}/ai/confirm`、`/assign` 等应返回 403（无权）。
5. 已提供自动化验收：
   - `tests/test_department_head_scope.py`、`tests/test_phase2.py`、`tests/test_phase3.py`、`tests/test_workflow.py`、`tests/test_exports.py`
   - 运行命令：`cd apps/api && pytest`

当前代码已验证通过（回归测试 green），可直接作为“小程序端按角色验收”的准备条件。

## 已知限制

- 短信发送暂未接入真实服务。`SMS_MOCK=true` 使用演示验证码；关闭后短信发送返回 503。生产环境请使用微信登录。
- 默认 AI、语音、OCR 为 Mock；不代表真实识别质量。外部调用费用由部署者承担。
- 仓库保留原项目的 Taro binding / doctor 替代包；原生脚手架创建和 doctor 检查不可用，不能把 doctor 的结果当作验证通过。
- 生产配置不自动创建演示用户；部署和初始化要求见 [生产部署说明](docs/deployment/production.md)。

## 许可证

本项目原创代码以 [MIT License](LICENSE) 发布，允许使用、修改及商用，须保留版权与许可声明。第三方依赖仍适用各自的许可证。
