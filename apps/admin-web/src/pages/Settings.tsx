import {CloudServerOutlined, DatabaseOutlined, DeleteOutlined, ReloadOutlined, RobotOutlined, SafetyCertificateOutlined, WechatOutlined} from "@ant-design/icons";
import {Alert, App, Button, Descriptions, Empty, Space, Spin, Statistic, Tag} from "antd";
import {useEffect, useState} from "react";

import {api} from "../api";
import {PageTitle} from "../components";

type Integration = {provider?: string; model?: string; configured: boolean; mock?: boolean};
type IntegrationStatus = {
  environment: string;
  ai: Integration;
  asr: Integration;
  wechat: Integration;
  storage: Integration;
  production_issues: string[];
};
type Runtime = {
  queue: {mode: string; redis: string; worker_online: boolean; depth: number};
  exports: {pending: number; processing: number; completed: number; failed: number; expired: number; retention_days: number; max_attempts: number};
};
type InvokeSummary = {
  total: number;
  success: number;
  failed: number;
  success_rate: number;
  avg_latency_ms: number;
  max_latency_ms: number;
  p95_latency_ms: number;
  total_cost: number;
  avg_cost: number;
  tokens: {prompt: number; completion: number; total: number};
  recent_errors: {error: string; count: number}[];
};
type ObservabilityResponse = {
  window: {days: number};
  invocations: {window: {days: number}; ai: InvokeSummary; asr: InvokeSummary};
  alert_summary: {recent_unread_count: number};
  recent_alerts: {id: string; title: string; content: string; related_record_id: string | null; is_read: boolean; created_at: string}[];
};

export default function Settings() {
  const {message} = App.useApp();
  const [data, setData] = useState<IntegrationStatus | undefined>();
  const [runtime, setRuntime] = useState<Runtime | undefined>();
  const [observability, setObservability] = useState<ObservabilityResponse | undefined>();
  const [loading, setLoading] = useState(true);
  const [cleaning, setCleaning] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [integrations, operation, observe] = await Promise.all([
        api.request<IntegrationStatus>("/system/integrations"),
        api.request<Runtime>("/system/runtime"),
        api.request<ObservabilityResponse>("/system/observability"),
      ]);
      setData(integrations);
      setRuntime(operation);
      setObservability(observe);
    } catch (e: any) {
      setData(undefined);
      setRuntime(undefined);
      setObservability(undefined);
      setError(e.message || "无法连接 API");
      message.error(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function cleanup() {
    setCleaning(true);
    try {
      const result = await api.request<{cleaned: number; retention_days: number}>(
        "/exports/maintenance/cleanup",
        {method: "POST"},
      );
      message.success(result.cleaned ? `已清理 ${result.cleaned} 个过期文件` : "当前没有需要清理的过期文件");
      await load();
    } catch (e: any) {
      message.error(e.message);
    } finally {
      setCleaning(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  if (loading && !data) return <div className="center"><Spin size="large" /></div>;

  const services = [
    {key: "ai", name: "AI 结构化分析", icon: <RobotOutlined />, item: data?.ai, help: "支持 OpenAI 兼容接口；未配置 Key 时开发环境继续使用 Mock。"},
    {key: "asr", name: "语音转写", icon: <CloudServerOutlined />, item: data?.asr, help: "与 AI 服务共享兼容接口配置，可单独选择 Mock 或真实 ASR。"},
    {key: "wechat", name: "微信登录", icon: <WechatOutlined />, item: data?.wechat, help: "正式模式使用 code2session，首次登录必须绑定已登记员工手机号。"},
    {key: "storage", name: "文件存储", icon: <SafetyCertificateOutlined />, item: data?.storage, help: "文件通过 MinIO 私有桶保存，下载地址有效期为 15 分钟。"},
  ];

  return (
    <>
      <PageTitle
        title="集成设置"
        sub="检查 AI、微信与文件服务是否具备联调条件；此页面不会显示任何密钥"
        extra={<Button icon={<ReloadOutlined />} onClick={load}>重新检查</Button>}
      />

      {error
        ? <Alert className="integration-alert" type="error" showIcon message="无法读取集成状态" description={`${error}。请确认 API 已启动后重新检查。`} />
        : data?.production_issues?.length
          ? <Alert className="integration-alert" type="warning" showIcon message="生产环境配置尚未通过" description={data.production_issues.join("；")} />
          : <Alert className="integration-alert" type="success" showIcon message={data?.environment === "production" ? "生产环境配置检查通过" : "当前为开发环境，可在无外部 Key 时使用 Mock 完整演示"} />
      }

      {!error && (
        <>
          <div className="integration-grid">
            {services.map((service) => (
              <section className="card integration-card" key={service.key}>
                <div className="integration-icon">{service.icon}</div>
                <div>
                  <div className="integration-heading">
                    <h3>{service.name}</h3>
                    <Tag color={service.item?.configured ? "green" : "red"}>{service.item?.configured ? "已就绪" : "未配置"}</Tag>
                    {service.item?.mock && <Tag color="blue">Mock</Tag>}
                  </div>
                  <p>{service.help}</p>
                  <Descriptions
                    size="small"
                    column={1}
                    items={[
                      {key: "provider", label: "服务类型", children: service.item?.provider || "—"},
                      {key: "model", label: "模型", children: service.item?.model || "—"},
                    ]}
                  />
                </div>
              </section>
            ))}
          </div>

          {observability && (
            <section className="card observability-card">
              <div className="runtime-title">
                <div>
                  <div className="runtime-title">
                    <span><h3>AI/ASR 可观测指标（最近 {observability.window.days} 天）</h3></span>
                    <Tag color={observability.alert_summary.recent_unread_count ? "red" : "green"}>
                      未读告警 {observability.alert_summary.recent_unread_count}
                    </Tag>
                  </div>
                  <p>成功率、耗时、成本与错误按服务维度统计，可用于联调验收。</p>
                </div>
                <Space />
              </div>

              <div className="obs-stats">
                <Statistic title="AI 总调用" value={observability.invocations.ai.total} />
                <Statistic title="AI 成功率" value={`${observability.invocations.ai.success_rate}%`} />
                <Statistic title="AI 失败次数" value={observability.invocations.ai.failed} />
                <Statistic title="AI P95 耗时" value={`${observability.invocations.ai.p95_latency_ms} ms`} />
                <Statistic title="ASR 总调用" value={observability.invocations.asr.total} />
                <Statistic title="ASR 成功率" value={`${observability.invocations.asr.success_rate}%`} />
              </div>
            </section>
          )}

          {runtime && (
            <section className="card runtime-card">
              <div className="runtime-title">
                <div>
                  <DatabaseOutlined />
                  <span>
                    <h3>后台任务与导出文件</h3>
                    <p>开发环境使用内联任务；生产环境由 Redis 持久队列和独立 Worker 执行。</p>
                  </span>
                </div>
                <Space>
                  <Tag color={runtime.queue.worker_online ? "green" : "red"}>
                    {runtime.queue.worker_online ? "Worker 正常" : "Worker 离线"}
                  </Tag>
                  <Button icon={<DeleteOutlined />} loading={cleaning} onClick={cleanup}>
                    清理过期文件
                  </Button>
                </Space>
              </div>
              <div className="runtime-stats">
                <Statistic title="队列模式" value={runtime.queue.mode === "redis" ? "Redis" : "内联"} />
                <Statistic title="等待任务" value={runtime.exports.pending + runtime.queue.depth} />
                <Statistic title="处理中" value={runtime.exports.processing} />
                <Statistic title="失败" value={runtime.exports.failed} valueStyle={{color: runtime.exports.failed ? "#cf4a4a" : undefined}} />
                <Statistic title="已完成" value={runtime.exports.completed} />
                <Statistic title="保留天数" value={runtime.exports.retention_days} suffix="天" />
              </div>
              <div className="runtime-note">失败任务最多自动尝试 {runtime.exports.max_attempts} 次；超过 {runtime.exports.retention_days} 天的导出文件会自动删除，任务记录保留并可重新生成。</div>
            </section>
          )}

          {observability && observability.recent_alerts.length > 0 && (
            <section className="card runtime-card">
              <h3>最近 AI 告警</h3>
              <div className="alert-list">
                {observability.recent_alerts.map((item) => (
                  <div key={item.id} className="alert-row">
                    <div>
                      <b>{item.title}</b>
                      <small>{item.content}</small>
                    </div>
                    <Tag color={item.is_read ? "default" : "warning"}>
                      {item.is_read ? "已读" : "未读"}
                    </Tag>
                  </div>
                ))}
                {observability.recent_alerts.length === 0 && <Empty description="暂无告警记录" />}
              </div>
            </section>
          )}
        </>
      )}

      <section className="card security-note">
        <SafetyCertificateOutlined />
        <div>
          <h3>密钥安全说明</h3>
          <p>请只在服务器或本机根目录的 <code>.env</code> 中配置密钥，不要写入前端代码、提交到版本库或粘贴到聊天记录。修改后重启 API，再点击“重新检查”。</p>
        </div>
      </section>
    </>
  );
}
