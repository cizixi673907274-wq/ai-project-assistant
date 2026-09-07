# 微信小程序

Taro + React + TypeScript，包含记录、待处理、我的三个 Tab，并调用真实 API。支持微信登录、项目选择、文字/录音/照片/文件提交、语音转写、个人任务、逾期提示和订阅通知。

```bash
pnpm dev:weapp
pnpm typecheck
pnpm build
pnpm build:h5
```

在微信开发者工具导入本目录并选择 `dist`。H5 预览产物单独输出到 `dist-h5`，避免覆盖微信构建；可在该目录启动静态服务器进行浏览器验收。用 `TARO_APP_API_BASE_URL` 指定 API 根地址。

手机真机预览前，建议在项目根目录执行：

```bash
pnpm miniapp:preview
```

该命令会自动检测当前电脑局域网 IP，验证测试账号 `13800005678 / 123456` 能登录，并把微信开发者工具实际加载的 `dist` 产物同步到当前 API 地址。若换了 Wi-Fi 或重启网络后无法登录，重新执行一次即可。

开发环境保持 `WECHAT_MOCK=true`，可使用 `touristappid`。正式联调步骤：

1. 把 `project.config.json` 中的 `appid` 替换为正式小程序 AppID。
2. 后端设置 `WECHAT_MOCK=false`、`WECHAT_APP_ID` 和 `WECHAT_APP_SECRET`。
3. 在微信公众平台配置 API 与 MinIO 对应的 HTTPS 合法域名。
4. 将订阅消息模板 ID 以逗号分隔写入 `TARO_APP_SUBSCRIBE_TEMPLATE_IDS`。
5. 保证 MinIO 可访问，单个上传文件限制为 20MB。
