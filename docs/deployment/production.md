# 生产试点部署

本配置用于单机 Docker Compose 试点。正式公网部署时，应在 `admin-web` 前增加 HTTPS 反向代理或云负载均衡，并只开放 80/443；PostgreSQL、Redis、MinIO 和 API 均保持在内部网络。

> 短信发送尚未实现真实服务。生产配置使用 `SMS_MOCK=false`，手机号验证码入口不可用，请使用已配置的微信登录。示例中的腾讯云与 AI 凭据必须自行填写。

## 1. 创建生产环境变量

复制 `.env.production.example` 为 `.env.production`，至少修改：

- `APP_ENV=production`
- 32 位以上随机 `SECRET_KEY`
- `POSTGRES_PASSWORD`、`REDIS_PASSWORD`、`MINIO_ACCESS_KEY`、`MINIO_SECRET_KEY`
- `AI_PROVIDER=openai_compatible`、`AI_API_STYLE`、`AI_API_KEY` 与已开通的模型配置
- 腾讯云语音/OCR 启用时设置 `ASR_PROVIDER=tencent_cloud`、`OCR_PROVIDER=tencent_cloud`、`TENCENT_SECRET_ID`、`TENCENT_SECRET_KEY`、`TENCENT_REGION`
- `WECHAT_MOCK=false`、`WECHAT_APP_ID`、`WECHAT_APP_SECRET`
- `MINIO_PUBLIC_ENDPOINT` 设置为浏览器可访问的对象存储域名，HTTPS 时设置 `MINIO_PUBLIC_SECURE=true`
- `CORS_ORIGINS` 只保留正式管理端和小程序业务域名
- `TASK_QUEUE_MODE=redis`，并根据数据量设置 `EXPORT_RETENTION_DAYS` 与 `EXPORT_JOB_MAX_ATTEMPTS`

API 在生产模式启动时会拒绝弱密钥、Mock AI/ASR、Mock 微信或缺少微信凭据的配置。密钥不得写入前端、镜像或版本库。

## 2. 启动与检查

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.production -f docker-compose.prod.yml ps
curl --fail http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/api/v1/system/integrations -H "Authorization: Bearer <token>"
curl http://127.0.0.1:8080/api/v1/system/runtime -H "Authorization: Bearer <token>"
```

服务器本机验收入口为 `http://127.0.0.1:8080`，该端口只绑定回环地址。公网管理端应由 HTTPS 网关转发到该端口，不要直接暴露 8080、数据库、Redis 或 MinIO 管理端口。

新建的生产数据库默认不创建演示账号。内部试点环境如需测试数据，可明确执行一次：

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec api python -m app.db.seed
python scripts/verify_docker_stack.py --origin http://127.0.0.1:8080
python scripts/verify_workflow.py --base http://127.0.0.1:8080/api/v1
```

正式上线前应删除或禁用演示账号，并改用管理员预先登记的员工账号。`verify_docker_stack.py` 会真实验证 MinIO 上传、Redis Worker、异步 Excel 生成和下载；执行后会保留一条标记清晰的联调记录用于审计。

## 3. 上线前检查

- 完成数据库备份与恢复演练，并为数据卷配置每日快照。
- 在微信后台配置 request 合法域名、uploadFile 合法域名和 downloadFile 合法域名。
- 使用普通工程师账号执行越权测试，确认无法读取无关记录和附件。
- 验证对象存储签名地址 15 分钟后失效。
- 检查 `/health`、结构化请求日志和 `X-Request-ID`，确认可定位单次请求。
- 检查“集成设置”中的 Worker 状态为正常，并实际创建、下载和重试一项 Excel 导出任务。
- 用真实但脱敏的试点数据验证 AI 输出；失败记录应进入“AI 待确认”。
