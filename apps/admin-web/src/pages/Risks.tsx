import {Button,Modal,Select,Table,Tag} from "antd";
import {useEffect,useState} from "react";
import {api} from "../api";
import {PageTitle,Stat} from "../components";

export default function Risks(){
 const [rows,setRows]=useState<any[]>([]),[selected,setSelected]=useState<any>(),[level,setLevel]=useState("ALL");
 useEffect(()=>{api.request<any[]>("/projects/risks").then(setRows)},[]);
 const visible=level==="ALL"?rows:rows.filter(row=>row.risk_level===level);
 const columns=[{title:"研发项目",dataIndex:"name",render:(v:string)=><b>{v}</b>},{title:"问题总数",dataIndex:"total"},{title:"未处理",dataIndex:"unresolved"},{title:"高风险",dataIndex:"high"},{title:"风险等级",dataIndex:"risk_level",render:(v:string)=><RiskTag value={v}/>},{title:"风险标签",dataIndex:"tags",render:(v:string[])=>v.map(x=><Tag key={x}>{x}</Tag>)},{title:"操作",render:(_:any,row:any)=><Button type="link" onClick={()=>setSelected(row)}>查看详情</Button>}];
 return <>
  <PageTitle title="研发项目风险看板" sub="实时掌握产品开发问题、风险等级与闭环压力" extra={<Select value={level} onChange={setLevel} style={{width:140}} options={[{value:"ALL",label:"全部风险"},{value:"HIGH",label:"高风险"},{value:"MEDIUM",label:"中风险"},{value:"LOW",label:"低风险"}]}/>}/>
  <div className="stats four"><Stat label="研发项目总数" value={rows.length}/><Stat label="问题总数" value={rows.reduce((a,r)=>a+r.total,0)}/><Stat label="未处理问题" value={rows.reduce((a,r)=>a+r.unresolved,0)}/><Stat label="高风险研发项目" value={rows.filter(r=>r.risk_level==="HIGH").length}/></div>
  <Table className="card" rowKey="id" dataSource={visible} columns={columns}/>
  <Modal title="研发项目风险详情" open={!!selected} onCancel={()=>setSelected(undefined)} footer={<Button type="primary" onClick={()=>setSelected(undefined)}>关闭</Button>}>{selected&&<div className="risk-detail"><h2>{selected.name}</h2><p><b>风险等级：</b><RiskTag value={selected.risk_level}/></p><p><b>问题总数：</b>{selected.total}</p><p><b>未处理问题：</b>{selected.unresolved}</p><p><b>高风险问题：</b>{selected.high}</p><p><b>风险标签：</b>{selected.tags.map((x:string)=><Tag key={x}>{x}</Tag>)}</p><p className="muted">建议优先处理结构干涉、软件联调、模具试模等高风险问题，并由研发项目负责人跟踪处理进度。</p></div>}</Modal>
 </>
}
function RiskTag({value}:{value:string}){return <Tag color={value==="HIGH"?"red":value==="MEDIUM"?"orange":"green"}>{value==="HIGH"?"高风险":value==="MEDIUM"?"中风险":"低风险"}</Tag>}
