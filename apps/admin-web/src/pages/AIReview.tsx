import {EditOutlined,ReloadOutlined} from "@ant-design/icons";
import {App,Button,Form,Input,Modal,Progress,Select,Space,Table} from "antd";
import {useEffect,useMemo,useState} from "react";
import {api} from "../api";
import {PageTitle} from "../components";
import {formatDateTime} from "../time";

export default function AIReview(){
 const {message}=App.useApp(),[form]=Form.useForm();
 const [rows,setRows]=useState<any[]>([]),[editing,setEditing]=useState<any>(),[busy,setBusy]=useState(false),[category,setCategory]=useState("ALL"),[confidence,setConfidence]=useState("ALL");
 async function load(){setBusy(true);try{setRows(await api.request<any[]>("/records?status=AI_REVIEW_REQUIRED"))}catch(e:any){message.error(e.message)}finally{setBusy(false)}}
 useEffect(()=>{load()},[]);
 const categories=useMemo(()=>Array.from(new Set(rows.map(r=>r.category_snapshot).filter(Boolean))).map(value=>({value,label:value})),[rows]);
 const visible=rows.filter(r=>(category==="ALL"||r.category_snapshot===category)&&(confidence==="ALL"||(confidence==="HIGH"?(r.confidence||0)>=.85:(r.confidence||0)<.85)));
 async function confirm(row:any,values:Record<string,unknown>={}){setBusy(true);try{await api.request(`/records/${row.id}/ai/confirm`,{method:"POST",body:JSON.stringify(values)});message.success(values.category?"AI结果已修改并确认":"AI结果已确认");setEditing(undefined);form.resetFields();await load()}catch(e:any){message.error(e.message)}finally{setBusy(false)}}
 function openEdit(row:any){setEditing(row);form.setFieldsValue({category:row.category_snapshot,stage:row.stage_snapshot,product:row.product_snapshot,priority:row.priority})}
 const columns=[
  {title:"记录内容",dataIndex:"title",render:(v:string,r:any)=><><b>{v}</b><small className="block">{r.project_name}</small></>},
  {title:"AI识别结果",render:(_:any,r:any)=><><span>{r.category_snapshot}</span><small className="block">{r.stage_snapshot} · {r.product_snapshot}</small></>},
  {title:"置信度",dataIndex:"confidence",render:(v:number)=><Progress percent={Math.round((v||0)*100)} size="small" strokeColor={(v||0)>.85?"#169B7A":"#F29D38"}/>},
  {title:"提交人 / 时间",render:(_:any,r:any)=><>{r.creator_name}<small className="block">{formatDateTime(r.created_at)}</small></>},
  {title:"操作",render:(_:any,row:any)=><Space><Button type="primary" ghost loading={busy} onClick={()=>confirm(row)}>确认</Button><Button icon={<EditOutlined/>} onClick={()=>openEdit(row)}>修改</Button></Space>}
 ];
 return <>
  <PageTitle title="AI待确认" sub="以下是AI识别结果需人工确认的记录" extra={<Button icon={<ReloadOutlined/>} loading={busy} onClick={load}>刷新</Button>}/>
  <div className="filters"><Select value={category} onChange={setCategory} options={[{value:"ALL",label:"全部分类"},...categories]}/><Select value={confidence} onChange={setConfidence} options={[{value:"ALL",label:"全部置信度"},{value:"HIGH",label:"85%及以上"},{value:"LOW",label:"85%以下"}]}/><Button onClick={()=>{setCategory("ALL");setConfidence("ALL")}}>重置</Button></div>
  <Table className="card" rowKey="id" dataSource={visible} columns={columns} loading={busy} pagination={{pageSize:10}}/>
  <Modal title="修改 AI 识别结果" open={!!editing} onCancel={()=>{setEditing(undefined);form.resetFields()}} onOk={()=>form.submit()} confirmLoading={busy} okText="保存并确认" cancelText="取消">
   <Form form={form} layout="vertical" onFinish={values=>confirm(editing,values)}><Form.Item name="category" label="问题分类" rules={[{required:true,message:"请输入问题分类"}]}><Input/></Form.Item><Form.Item name="stage" label="发生环节"><Input/></Form.Item><Form.Item name="product" label="涉及产品"><Input/></Form.Item><Form.Item name="priority" label="优先级"><Select options={[{value:"LOW",label:"低"},{value:"MEDIUM",label:"中"},{value:"HIGH",label:"高"},{value:"URGENT",label:"紧急"}]}/></Form.Item></Form>
  </Modal>
 </>
}
