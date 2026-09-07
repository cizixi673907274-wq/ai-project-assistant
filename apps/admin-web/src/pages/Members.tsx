import {DownOutlined,PlusOutlined} from "@ant-design/icons";
import {App,Avatar,Button,Dropdown,Form,Input,Modal,Select,Space,Table,Tabs,Tag} from "antd";
import {useEffect,useMemo,useState} from "react";
import {useSearchParams} from "react-router-dom";
import {api,currentAccount} from "../api";
import {PageTitle} from "../components";
import {formatDateTime} from "../time";

const roleNames:Record<string,string>={SUPER_ADMIN:"管理员",PROJECT_MANAGER:"主管（项目经理）",DEPARTMENT_HEAD:"主管（项目经理）",ENGINEER:"工程师（员工）",VIEWER:"只读成员"};
const supervisorRoleCodes=["PROJECT_MANAGER","DEPARTMENT_HEAD"];
export default function Members(){
 const {message}=App.useApp(),[form]=Form.useForm(),[teamForm]=Form.useForm();
 const [params]=useSearchParams();
 const [rows,setRows]=useState<any[]>([]),[roles,setRoles]=useState<any[]>([]),[editing,setEditing]=useState<any|null|undefined>(undefined),[editingTeam,setEditingTeam]=useState<any|null|undefined>(undefined),[busy,setBusy]=useState(false),[keyword,setKeyword]=useState(params.get("keyword")||""),[department,setDepartment]=useState("ALL"),[status,setStatus]=useState("ALL");
 const [departments,setDepartments]=useState<any[]>([]),[account,setAccount]=useState<any>();
  async function load(){setBusy(true);try{const [usersData,rolesData,departmentData,accountData]=await Promise.all([api.request<any[]>("/admin/users"),api.request<any[]>("/admin/roles"),api.request<any[]>("/admin/departments"),currentAccount()]);setRows(usersData);setRoles(rolesData);setDepartments(departmentData);setAccount(accountData)}catch(e:any){message.error(e.message)}finally{setBusy(false)}}
 useEffect(()=>{load()},[]);
 useEffect(()=>{setKeyword(params.get("keyword")||"")},[params]);
 const isSuperAdmin=account?.roles?.includes("SUPER_ADMIN");
 const departmentOptions=useMemo(()=>Array.from(new Map([...rows.filter(r=>r.department_id).map(r=>[r.department_id,{value:r.department_id,label:r.department}]),...departments.map(d=>[d.id,{value:d.id,label:d.name}])].map(([k,v])=>[k,v])).values()),[rows,departments]);
 const visible=rows.filter(r=>(!keyword||`${r.name} ${r.username} ${r.mobile||""}`.toLowerCase().includes(keyword.toLowerCase()))&&(department==="ALL"||r.department_id===department)&&(status==="ALL"||r.status===status));
 const backendRoles=roles.filter(role=>isSuperAdmin?supervisorRoleCodes.includes(role.code):role.code==="ENGINEER");
 function openCreate(){setEditing(null);form.setFieldsValue({role:isSuperAdmin?"PROJECT_MANAGER":"ENGINEER",department_id:isSuperAdmin?undefined:account?.department_id,status:"ACTIVE"})}
function roleToSupervisorCode(roleCode:string){return roleCode}
 function openEdit(row:any){setEditing(row);form.setFieldsValue({name:row.name,department_id:row.department_id,role:roleToSupervisorCode(row.roles[0]),status:row.status})}
 async function save(values:any){setBusy(true);try{if(editing)await api.request(`/admin/users/${editing.id}`,{method:"PATCH",body:JSON.stringify(values)});else await api.request("/admin/users",{method:"POST",body:JSON.stringify(values)});message.success(editing?"成员设置已保存":"成员已创建");setEditing(undefined);form.resetFields();await load()}catch(e:any){message.error(e.message)}finally{setBusy(false)}}
 async function toggle(row:any){setBusy(true);try{const next=row.status==="ACTIVE"?"DISABLED":"ACTIVE";await api.request(`/admin/users/${row.id}`,{method:"PATCH",body:JSON.stringify({status:next})});message.success(next==="ACTIVE"?"成员已启用":"成员已停用");await load()}catch(e:any){message.error(e.message)}finally{setBusy(false)}}
 function openTeam(team?:any){setEditingTeam(team||null);teamForm.setFieldsValue({name:team?.name||""})}
 async function saveTeam(values:{name:string}){setBusy(true);try{if(editingTeam)await api.request(`/admin/departments/${editingTeam.id}`,{method:"PATCH",body:JSON.stringify(values)});else await api.request("/admin/departments",{method:"POST",body:JSON.stringify(values)});message.success(editingTeam?"团队名称已更新":"团队已创建");setEditingTeam(undefined);teamForm.resetFields();await load()}catch(e:any){message.error(e.message)}finally{setBusy(false)}}
 const columns=[
  {title:isSuperAdmin?"主管信息":"工程师信息",render:(_:any,r:any)=><div className="member"><Avatar>{r.name[0]}</Avatar><span><b>{r.name}</b><small>{r.username} · {r.mobile||"未填写手机号"}</small></span></div>},
  {title:"所属团队",dataIndex:"department",render:(v:string)=>v||"未分团队"},
  {title:"角色",dataIndex:"roles",render:(v:string[])=><Tag color="green">{roleNames[v[0]]||v[0]}</Tag>},
  {title:"状态",dataIndex:"status",render:(v:string)=><Tag color={v==="ACTIVE"?"green":"default"}>{v==="ACTIVE"?"启用":"停用"}</Tag>},
  {title:"最后活跃",dataIndex:"last_active",render:(v:string)=>formatDateTime(v)},
  {title:"操作",render:(_:any,row:any)=><Space><Button type="link" onClick={()=>openEdit(row)}>编辑</Button><Dropdown menu={{items:[{key:"toggle",label:row.status==="ACTIVE"?"停用成员":"启用成员",onClick:()=>toggle(row)}]}}><Button type="link">更多<DownOutlined/></Button></Dropdown></Space>}
 ];
 const roleColumns=[{title:"角色名称",dataIndex:"name",render:(_:string,r:any)=><><b>{roleNames[r.code]||r.name}</b><small className="block">{r.code}</small></>},{title:"权限数量",dataIndex:"permissions",render:(v:string[])=>v.length},{title:"权限明细",dataIndex:"permissions",render:(v:string[])=>v.slice(0,4).map(x=><Tag key={x}>{x}</Tag>)}];
 const teamColumns=[
  {title:"团队名称",dataIndex:"name",render:(value:string)=><b>{value}</b>},
  {title:"主管数量",render:(_:any,team:any)=>rows.filter(row=>row.department_id===team.id).length},
  {title:"操作",render:(_:any,team:any)=><Button type="link" onClick={()=>openTeam(team)}>修改名称</Button>}
 ];
 return <>
  <PageTitle title={isSuperAdmin?"成员与权限":"团队管理"} sub={isSuperAdmin?"自定义团队名称，并创建、维护各团队主管（项目经理）账号":"创建并维护本团队工程师账号"} extra={<Button type="primary" icon={<PlusOutlined/>} onClick={openCreate}>{isSuperAdmin?"新增主管账号":"新增工程师账号"}</Button>}/>
  <Tabs items={[{key:"members",label:isSuperAdmin?"主管账号":"团队工程师",children:<><div className="filters"><Input allowClear value={keyword} onChange={e=>setKeyword(e.target.value)} placeholder={isSuperAdmin?"搜索主管姓名 / 账号 / 手机号":"搜索工程师姓名 / 账号 / 手机号"}/>{isSuperAdmin&&<Select value={department} onChange={setDepartment} options={[{value:"ALL",label:"全部团队"},...departmentOptions]}/>}<Select value={status} onChange={setStatus} options={[{value:"ALL",label:"全部状态"},{value:"ACTIVE",label:"启用"},{value:"DISABLED",label:"停用"}]}/><Button onClick={()=>{setKeyword("");setDepartment("ALL");setStatus("ALL")}}>重置</Button></div><Table className="card" rowKey="id" dataSource={visible} columns={columns} loading={busy}/></>},...(isSuperAdmin?[{key:"teams",label:"团队设置",children:<><div className="team-toolbar"><div><b>团队名称</b><span>团队名称可按公司实际部门或项目组自定义</span></div><Button type="primary" icon={<PlusOutlined/>} onClick={()=>openTeam()}>新增团队</Button></div><Table className="card" rowKey="id" dataSource={departments} columns={teamColumns} loading={busy}/></>}]:[]),{key:"roles",label:"角色说明",children:<Table className="card" rowKey="id" dataSource={backendRoles} columns={roleColumns} loading={busy}/>}]} />
  <Modal title={editing?"编辑成员":"新增成员"} open={editing!==undefined} onCancel={()=>{setEditing(undefined);form.resetFields()}} onOk={()=>form.submit()} confirmLoading={busy} okText="保存" cancelText="取消">
   <Form form={form} layout="vertical" onFinish={save}>
    {!editing&&<><Form.Item name="username" label="登录账号" rules={[{required:true,message:"请输入登录账号"}]}><Input/></Form.Item><Form.Item name="password" label="初始密码" rules={[{required:true,message:"请输入初始密码"}]}><Input.Password/></Form.Item></>}
    <Form.Item name="name" label="姓名" rules={[{required:true,message:"请输入姓名"}]}><Input/></Form.Item>
    {!editing&&<Form.Item name="mobile" label="手机号"><Input/></Form.Item>}
    <Form.Item name="department_id" label="所属团队" rules={[{required:true,message:"请选择所属团队"}]}><Select disabled={!isSuperAdmin} options={departmentOptions} placeholder="选择团队"/></Form.Item>
    <Form.Item name="role" label="角色" rules={[{required:true,message:"请选择角色"}]}><Select disabled={!isSuperAdmin} options={backendRoles.map(r=>({value:r.code,label:roleNames[r.code]||r.name}))}/></Form.Item>
    {editing&&<Form.Item name="status" label="状态"><Select options={[{value:"ACTIVE",label:"启用"},{value:"DISABLED",label:"停用"}]}/></Form.Item>}
   </Form>
  </Modal>
  <Modal title={editingTeam?"修改团队名称":"新增团队"} open={editingTeam!==undefined} onCancel={()=>{setEditingTeam(undefined);teamForm.resetFields()}} onOk={()=>teamForm.submit()} confirmLoading={busy} okText="保存" cancelText="取消">
   <Form form={teamForm} layout="vertical" onFinish={saveTeam}>
    <Form.Item name="name" label="团队名称" rules={[{required:true,message:"请输入团队名称"},{max:100,message:"团队名称不能超过100个字符"}]}><Input placeholder="例如：结构研发一部、软件平台组"/></Form.Item>
   </Form>
  </Modal>
 </>
}
