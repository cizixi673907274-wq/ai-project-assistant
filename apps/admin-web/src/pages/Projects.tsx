import {DeleteOutlined,EditOutlined,PlusOutlined,ReloadOutlined} from "@ant-design/icons";
import {App,Button,Form,Input,Modal,Progress,Select,Space,Table,Tag} from "antd";
import {useEffect,useState} from "react";
import {api} from "../api";
import {PageTitle,Stat} from "../components";

export default function Projects(){
 const {message,modal}=App.useApp(); const [rows,setRows]=useState<any[]>([]),[users,setUsers]=useState<any[]>([]),[departments,setDepartments]=useState<any[]>([]),[editing,setEditing]=useState<any>(),[open,setOpen]=useState(false),[busy,setBusy]=useState(false); const [form]=Form.useForm();
 async function load(){try{const [projects,members,depts]=await Promise.all([api.request<any[]>("/projects"),api.request<any[]>("/users/assignable"),api.request<any[]>("/admin/departments")]);setRows(projects);setUsers(members);setDepartments(depts)}catch(e:any){message.error(e.message)}}
 useEffect(()=>{load()},[]);
 function create(){setEditing(undefined);form.resetFields();form.setFieldsValue({status:"ACTIVE",member_ids:[]});setOpen(true)}
 function edit(row:any){setEditing(row);form.setFieldsValue({name:row.name,code:row.code,manager_id:row.manager_id,department_id:row.department_id,status:row.status,member_ids:row.members.map((m:any)=>m.id)});setOpen(true)}
 async function save(){const values=await form.validateFields();setBusy(true);try{if(editing)await api.request(`/projects/${editing.id}`,{method:"PATCH",body:JSON.stringify(values)});else await api.request("/projects",{method:"POST",body:JSON.stringify(values)});message.success(editing?"项目已更新":"项目已创建");setOpen(false);await load()}catch(e:any){message.error(e.message)}finally{setBusy(false)}}
 function remove(row:any){modal.confirm({title:"删除研发项目",content:row.record_count?`“${row.name}”仍有 ${row.record_count} 条有效记录。请先删除或迁移这些记录，研发项目才可删除。`:`确定删除“${row.name}”吗？删除后项目将从项目管理和风险看板中隐藏。`,okText:"删除项目",okType:"danger",cancelText:"取消",okButtonProps:{disabled:row.record_count>0},onOk:async()=>{setBusy(true);try{await api.request(`/projects/${row.id}`,{method:"DELETE"});message.success("项目已删除");await load()}catch(e:any){message.error(e.message)}finally{setBusy(false)}}})}
 const totalOpen=rows.reduce((sum,r)=>sum+r.open_record_count,0),totalRecords=rows.reduce((sum,r)=>sum+r.record_count,0);
 return <><PageTitle title="项目管理" sub="统一维护研发项目、负责人、成员和产品问题闭环进度" extra={<Space><Button icon={<ReloadOutlined/>} onClick={load}>刷新</Button><Button type="primary" icon={<PlusOutlined/>} onClick={create}>新建项目</Button></Space>}/>
  <div className="stats four"><Stat label="研发项目总数" value={rows.length} icon="📁"/><Stat label="进行中研发项目" value={rows.filter(r=>r.status==="ACTIVE").length} icon="▶"/><Stat label="研发记录" value={totalRecords} icon="📝"/><Stat label="待闭环问题" value={totalOpen} icon="⚠"/></div>
  <section className="card table-card"><Table rowKey="id" dataSource={rows} pagination={{pageSize:8}} columns={[
  {title:"研发项目",render:(_:any,r:any)=><div><b>{r.name}</b><small className="block">{r.code}</small></div>},
   {title:"部门",dataIndex:"department_name",render:(v:string)=>v||"未设置"},
   {title:"负责人",dataIndex:"manager_name",render:(v:string)=>v||"未设置"},
   {title:"成员",render:(_:any,r:any)=><Space wrap>{r.members.slice(0,3).map((m:any)=><Tag key={m.id}>{m.name}</Tag>)}{r.members.length>3&&<Tag>+{r.members.length-3}</Tag>}</Space>},
   {title:"问题进度",width:220,render:(_:any,r:any)=><div><Progress size="small" percent={r.record_count?Math.round((r.record_count-r.open_record_count)/r.record_count*100):100}/><small>{r.open_record_count} 个待闭环 / {r.record_count} 条记录</small></div>},
   {title:"状态",dataIndex:"status",render:(v:string)=><Tag color={v==="ACTIVE"?"green":"default"}>{v==="ACTIVE"?"进行中":"已归档"}</Tag>},
   {title:"操作",render:(_:any,r:any)=><Space><Button icon={<EditOutlined/>} onClick={()=>edit(r)}>编辑</Button><Button danger icon={<DeleteOutlined/>} onClick={()=>remove(r)}>删除</Button></Space>}
  ]}/></section>
  <Modal title={editing?"编辑研发项目":"新建研发项目"} open={open} onCancel={()=>setOpen(false)} onOk={save} confirmLoading={busy} okText="保存" cancelText="取消"><Form form={form} layout="vertical">
    <Form.Item name="name" label="研发项目名称" rules={[{required:true,message:"请输入研发项目名称"}]}><Input/></Form.Item>
    <Form.Item name="code" label="项目编号" rules={[{required:true,message:"请输入项目编号"}]}><Input disabled={!!editing}/></Form.Item>
    <Form.Item name="department_id" label="所属部门"><Select allowClear options={departments.map((item:any)=>({value:item.id,label:item.name}))} placeholder="选择部门（默认与负责人部门保持一致）"/></Form.Item>
    <Form.Item name="manager_id" label="研发负责人"><Select allowClear options={users.map(u=>({value:u.id,label:`${u.name} · ${u.department||"未分部门"}`}))}/></Form.Item>
    <Form.Item name="member_ids" label="研发成员"><Select mode="multiple" options={users.map(u=>({value:u.id,label:u.name}))}/></Form.Item>
    {editing&&<Form.Item name="status" label="项目状态"><Select options={[{value:"ACTIVE",label:"进行中"},{value:"ARCHIVED",label:"已归档"}]}/></Form.Item>}
  </Form></Modal>
 </>
}
