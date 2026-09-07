# 架构摘要

小程序与 PC Web 共享 REST API、状态枚举和错误语义。FastAPI 负责认证、RBAC、数据范围、状态机与审计；PostgreSQL 持久化业务数据，Redis 为缓存/异步任务扩展点，MinIO 保存媒体文件。AI 与 ASR 通过 Provider 接口隔离，默认 Mock 可离线演示。
