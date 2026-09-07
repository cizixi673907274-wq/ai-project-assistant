import {BarChartOutlined,BellOutlined,FileExcelOutlined,FileTextOutlined,FolderOpenOutlined,HomeOutlined,RobotOutlined,SearchOutlined,SettingOutlined,TeamOutlined,WarningOutlined} from "@ant-design/icons";
import {App as AntApp,Avatar,Badge,Button,Empty,Input,Layout,Menu,Popover,Result,Spin} from "antd";
import {useEffect,useMemo,useState} from "react";
import {Link,Navigate,Route,Routes,useLocation,useNavigate} from "react-router-dom";
import {api,currentAccount,logout,restoreSession} from "./api";
import AIReview from "./pages/AIReview";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";
import Members from "./pages/Members";
import Projects from "./pages/Projects";
import Records from "./pages/Records";
import Reports from "./pages/Reports";
import Risks from "./pages/Risks";
import Settings from "./pages/Settings";
import Templates from "./pages/Templates";
import "./settings.css";
import {formatDateTime} from "./time";

const allItems=[
 {key:"/dashboard",icon:<HomeOutlined/>,label:<Link to="/dashboard">工作台</Link>},
 {key:"/ai-review",icon:<RobotOutlined/>,label:<Link to="/ai-review">AI待确认</Link>},
 {key:"/records",icon:<FileTextOutlined/>,label:<Link to="/records">记录中心</Link>},
 {key:"/projects",icon:<FolderOpenOutlined/>,label:<Link to="/projects">项目管理</Link>},
 {key:"/members",icon:<TeamOutlined/>,label:<Link to="/members">成员与权限</Link>},
 {key:"/risks",icon:<WarningOutlined/>,label:<Link to="/risks">项目风险</Link>},
 {key:"/reports",icon:<BarChartOutlined/>,label:<Link to="/reports">报告中心</Link>},
 {key:"/templates",icon:<FileExcelOutlined/>,label:<Link to="/templates">模板中心</Link>},
 {key:"/settings",icon:<SettingOutlined/>,label:<Link to="/settings">集成设置</Link>}
];

const roleNames:Record<string,string>={SUPER_ADMIN:"管理员",PROJECT_MANAGER:"主管（项目经理）",DEPARTMENT_HEAD:"主管（项目经理）",ENGINEER:"工程师（员工）",VIEWER:"只读成员"};

export default function App(){
 const {message}=AntApp.useApp();
 const [checking,setChecking]=useState(true),[authenticated,setAuthenticated]=useState(false);
 const [account,setAccount]=useState<any>();
 const [notifications,setNotifications]=useState<any[]>([]);
 const loc=useLocation();
 const navigate=useNavigate();
 async function refreshAccount(){const data=await currentAccount();setAccount(data);return data}
 useEffect(()=>{restoreSession().then(async ok=>{setAuthenticated(ok);if(ok)await refreshAccount().catch(()=>{});setChecking(false)})},[]);
 useEffect(()=>{if(authenticated)api.request<any[]>("/notifications").then(setNotifications).catch(()=>{})},[authenticated,loc.pathname]);
 const isSuperAdmin=account?.roles?.includes("SUPER_ADMIN");
 const isSupervisor=account?.roles?.some((role:string)=>["PROJECT_MANAGER","DEPARTMENT_HEAD"].includes(role));
 const allowedPaths=useMemo(()=>{
  if(isSuperAdmin)return new Set(["/dashboard","/members","/settings"]);
  if(isSupervisor)return new Set(allItems.filter(item=>item.key!=="/settings").map(item=>item.key));
  return new Set(["/dashboard"]);
 },[isSuperAdmin,isSupervisor]);
 useEffect(()=>{if(account&&!allowedPaths.has(loc.pathname))navigate("/dashboard",{replace:true})},[account,allowedPaths,loc.pathname,navigate]);
 const items=useMemo(()=>allItems.filter(item=>allowedPaths.has(item.key)).map(item=>item.key==="/members"?{...item,label:<Link to="/members">{isSuperAdmin?"成员与权限":"团队管理"}</Link>}:item),[allowedPaths,isSuperAdmin]);
 const displayRole=account?.roles?.map((role:string)=>roleNames[role]||role).join(" / ")||"未识别角色";
 const displayName=account?.name||"当前用户";
 if(checking)return <div className="center"><Spin size="large"/></div>;
 if(!authenticated)return <Login onSuccess={async()=>{setAuthenticated(true);await refreshAccount().catch(()=>{})}}/>;
 function signOut(){logout();setAuthenticated(false);setAccount(undefined)}
 return <Layout className="shell">
  <Layout.Header className="header">
   <button className="brand brand-button" onClick={()=>navigate("/dashboard")}><img className="brand-logo" src="/logo.png" alt="AI项目助手 Logo"/><span><b>AI项目助手</b><small>工程师问题&工作记录</small></span></button>
   <Input.Search className="global-search" prefix={<SearchOutlined/>} enterButton="搜索" placeholder={isSuperAdmin?"搜索团队、主管姓名或账号…":"搜索问题、项目、人员、标签…"} onSearch={value=>navigate(`${isSuperAdmin?"/members":"/records"}${value?`?keyword=${encodeURIComponent(value)}`:""}`)}/>
   <div className="user"><Popover trigger="click" title={<div className="notification-title"><span>消息通知</span><Button size="small" type="link" onClick={async()=>{await api.request("/notifications/read-all",{method:"POST"});setNotifications(items=>items.map(n=>({...n,is_read:true})));message.success("已全部标记为已读")}}>全部已读</Button></div>} content={<div className="notifications">{notifications.length?notifications.slice(0,6).map(n=><button className={n.is_read?"notification-item":"notification-item unread"} key={n.id} onClick={async()=>{if(!n.is_read)await api.request(`/notifications/${n.id}/read`,{method:"PATCH"});setNotifications(items=>items.map(item=>item.id===n.id?{...item,is_read:true}:item));if(n.related_record_id)navigate("/records")}}><b>{n.title}</b><span>{n.content}</span><small>{formatDateTime(n.created_at)}</small></button>):<Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无通知"/>}</div>}><Badge count={notifications.filter(n=>!n.is_read).length} size="small"><Button aria-label="消息通知" type="text" icon={<BellOutlined/>}/></Badge></Popover><Avatar>{displayName.slice(0,1)}</Avatar><span>{displayName}</span><Button type="text" onClick={signOut}>退出</Button></div>
  </Layout.Header>
  <Layout>
   <Layout.Sider width={210} theme="light" className="sider"><Menu selectedKeys={[loc.pathname]} mode="inline" items={items}/><div className="role-card"><b>🛡 管理后台</b><span>{displayName}</span><small>当前角色：{displayRole}</small></div></Layout.Sider>
   <Layout.Content className="content"><Routes><Route path="/dashboard" element={(isSuperAdmin||isSupervisor)?<Dashboard adminMode={isSuperAdmin}/>:<Result status="403" title="工程师请使用微信小程序" subTitle="PC Web 仅供管理员和主管（项目经理）使用。"/>}/><Route path="/records" element={isSupervisor?<Records/>:<Navigate to="/dashboard" replace/>}/><Route path="/projects" element={isSupervisor?<Projects/>:<Navigate to="/dashboard" replace/>}/><Route path="/ai-review" element={isSupervisor?<AIReview/>:<Navigate to="/dashboard" replace/>}/><Route path="/risks" element={isSupervisor?<Risks/>:<Navigate to="/dashboard" replace/>}/><Route path="/reports" element={isSupervisor?<Reports/>:<Navigate to="/dashboard" replace/>}/><Route path="/templates" element={isSupervisor?<Templates/>:<Navigate to="/dashboard" replace/>}/><Route path="/members" element={(isSuperAdmin||isSupervisor)?<Members/>:<Navigate to="/dashboard" replace/>}/><Route path="/settings" element={isSuperAdmin?<Settings/>:<Navigate to="/dashboard" replace/>}/><Route path="*" element={<Navigate to="/dashboard"/>}/></Routes></Layout.Content>
  </Layout>
 </Layout>
}
