import {BellOutlined,DownloadOutlined,FileWordOutlined,ReloadOutlined} from "@ant-design/icons";
import {App,Button,Progress,Select,Space,Table,Tag} from "antd";
import {useEffect,useState} from "react";
import {api,downloadProjectReport} from "../api";
import {PageTitle,Stat} from "../components";
import {formatDateTime} from "../time";

const statusNames:Record<string,string>={DRAFT:"草稿",SUBMITTED:"已提交",AI_PROCESSING:"AI分析中",AI_REVIEW_REQUIRED:"AI待确认",READY_TO_ASSIGN:"待分派",ASSIGNED:"已分派",IN_PROGRESS:"处理中",RESOLVED:"待确认解决",CLOSED:"已关闭",CANCELLED:"已取消"};
const priorityNames:Record<string,string>={LOW:"低",MEDIUM:"中",HIGH:"高",URGENT:"紧急"};

export default function Reports(){
 const {message}=App.useApp(); const [overview,setOverview]=useState<any>(),[history,setHistory]=useState<any[]>([]),[projectId,setProjectId]=useState<string>(),[busy,setBusy]=useState(false),[scanning,setScanning]=useState(false);
 async function load(id=projectId){try{const query=id?`?project_id=${id}`:"";const [summary,exports]=await Promise.all([api.request<any>(`/reports/overview${query}`),api.request<any[]>(`/reports/exports${query}`)]);setOverview(summary);setHistory(exports)}catch(e:any){message.error(e.message)}}
 useEffect(()=>{load()},[projectId]);
 async function exportReport(){if(!projectId)return message.warning("请先选择研发项目");const project=overview?.projects.find((p:any)=>p.id===projectId);setBusy(true);try{await downloadProjectReport(projectId,project?.name||"研发项目");message.success("研发问题闭环报告已生成并开始下载");await load(projectId)}catch(e:any){message.error(e.message)}finally{setBusy(false)}}
 async function scan(){setScanning(true);try{const result=await api.request<any>("/tasks/scan-overdue",{method:"POST"});message.success(`扫描完成：新增 ${result.notifications_created} 条逾期通知`)}catch(e:any){message.error(e.message)}finally{setScanning(false)}}
 return <><PageTitle title="报告中心" sub="按研发项目生成闭环报告，追踪导出记录与逾期事项" extra={<Space><Button icon={<BellOutlined/>} loading={scanning} onClick={scan}>扫描逾期任务</Button><Button icon={<ReloadOutlined/>} onClick={()=>load()}>刷新</Button><Button type="primary" icon={<DownloadOutlined/>} loading={busy} disabled={!projectId} onClick={exportReport}>导出 Word 报告</Button></Space>}/>
  <section className="report-toolbar card"><div><b>报告范围</b><span>选择研发项目后，统计卡片、问题清单和导出历史会同步筛选。</span></div><Select allowClear showSearch optionFilterProp="label" value={projectId} placeholder="全部研发项目（请选择一个项目导出）" onChange={setProjectId} options={(overview?.projects||[]).map((p:any)=>({value:p.id,label:`${p.name} · ${p.code}`}))}/></section>
  <div className="stats four"><Stat label="记录总数" value={overview?.record_count||0} icon="📝"/><Stat label="待闭环" value={overview?.open_count||0} icon="⏳"/><Stat label="高风险事项" value={overview?.high_risk_count||0} icon="⚠"/><section className="card stat report-rate"><span>闭环率</span><b>{overview?.completion_rate??0}%</b><Progress percent={overview?.completion_rate||0} showInfo={false}/></section></div>
  <div className="grid-2 report-grid"><section className="card table-card"><h3>研发问题快照</h3><Table rowKey="id" size="small" pagination={false} dataSource={overview?.recent_records||[]} columns={[
   {title:"记录",dataIndex:"title",ellipsis:true},{title:"研发项目",dataIndex:"project_name",ellipsis:true},{title:"优先级",dataIndex:"priority",width:82,render:(v:string)=><Tag color={v==="HIGH"||v==="URGENT"?"red":v==="MEDIUM"?"orange":"green"}>{priorityNames[v]||v}</Tag>},{title:"状态",dataIndex:"status",width:100,render:(v:string)=><Tag>{statusNames[v]||v}</Tag>}
  ]}/></section><section className="card report-guide"><FileWordOutlined/><div><h3>研发问题闭环 Word 报告</h3><p>自动整理管理摘要、闭环指标、问题清单、高风险事项和报告说明。适合研发周会、阶段评审与问题复盘。</p><ol><li>选择一个研发项目</li><li>确认闭环率与高风险事项</li><li>导出后在历史中留痕</li></ol></div></section></div>
  <section className="card table-card"><h3>导出历史</h3><Table rowKey="id" dataSource={history} pagination={{pageSize:8}} locale={{emptyText:"暂无导出记录，选择项目后生成第一份闭环报告"}} columns={[
   {title:"文件名",dataIndex:"filename",render:(v:string)=><Space><FileWordOutlined className="word-icon"/><b>{v}</b></Space>},{title:"项目",dataIndex:"project_name"},{title:"记录数",dataIndex:"record_count",render:(v:number)=>`${v} 条`},{title:"生成者",dataIndex:"generated_by"},{title:"状态",dataIndex:"status",render:()=><Tag color="green">已完成</Tag>},{title:"生成时间",dataIndex:"completed_at",render:(v:string)=>formatDateTime(v)}
  ]}/></section>
 </>;
}
