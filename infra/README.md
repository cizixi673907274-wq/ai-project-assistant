# Infra

根目录 `docker-compose.yml` 定义 PostgreSQL、Redis、MinIO、API、Worker 与 PC Web 的完整开发栈；`docker-compose.prod.yml` 提供单机生产试点编排。

`infra/docker/admin-web.Dockerfile` 构建 React 管理端并由 Nginx 托管，`nginx.conf` 同时反向代理 `/api/` 和 `/health`。启动后可运行：

```bash
python scripts/verify_docker_stack.py
```

该脚本会验证数据库、Redis 队列、Worker 心跳、MinIO 文件上传以及异步 Excel 导出下载。
