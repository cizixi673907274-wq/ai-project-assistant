import {Image,Text,View} from "@tarojs/components";
import Taro,{useDidShow} from "@tarojs/taro";
import {useState} from "react";
import logo from "../../assets/logo.png";
import menuAboutIcon from "../../assets/icons/menu-about.png";
import menuAiIcon from "../../assets/icons/menu-ai-preference.png";
import menuDraftIcon from "../../assets/icons/menu-draft.png";
import menuFavoriteIcon from "../../assets/icons/menu-favorite.png";
import menuHelpIcon from "../../assets/icons/menu-help.png";
import menuNotificationIcon from "../../assets/icons/menu-notification.png";
import menuRecentIcon from "../../assets/icons/menu-recent.png";
import {logout,request,requestNotificationSubscription} from "../../services/api";
import "./index.scss";

const roleNames:any={ENGINEER:"研发工程师",PROJECT_MANAGER:"项目经理",DEPARTMENT_HEAD:"部门负责人",SUPER_ADMIN:"超级管理员"};

export default function Me(){
 const statusBarHeight=Taro.getWindowInfo?.().statusBarHeight||20;
 const menuButton=Taro.getMenuButtonBoundingClientRect?.();
 const capsuleClearance=Taro.getEnv()===Taro.ENV_TYPE.WEAPP?Math.max(16,(menuButton?.bottom||statusBarHeight+36)-statusBarHeight+8):0;
 const [me,setMe]=useState<any>({name:"陈工",roles:["ENGINEER"]}),[rows,setRows]=useState<any[]>([]),[records,setRecords]=useState<any[]>([]),[unread,setUnread]=useState(0),[loading,setLoading]=useState(true),[error,setError]=useState("");
 const [customAvatar,setCustomAvatar]=useState<string>(()=>Taro.getStorageSync("custom_avatar")||"");
 async function load(){setLoading(true);setError("");try{const [user,tasks,recordRows,count]=await Promise.all([request<any>("/me"),request<any[]>("/tasks/my"),request<any[]>("/records"),request<any>("/notifications/unread-count")]);setMe(user);setRows(tasks);setRecords(recordRows);setUnread(count.count)}catch(reason:any){setError(reason.message||"个人数据加载失败")}finally{setLoading(false)}}
 useDidShow(()=>{load()});
 const done=rows.filter(row=>row.task_status==="DONE").length,pending=rows.filter(row=>!["DONE","CANCELLED"].includes(row.task_status)).length,created=records.filter(record=>record.creator_id===me.id).length;
 const role=me.roles?.map((code:string)=>roleNames[code]||code).join(" / ")||"项目成员";
 async function changeAvatar(event:any){
  event?.stopPropagation?.();
  try{
   const selected=await Taro.showActionSheet({itemList:["拍照","从相册选择"]});
   const result=await Taro.chooseMedia({count:1,mediaType:["image"],sourceType:[selected.tapIndex===0?"camera":"album"]});
   const tempFilePath=result.tempFiles[0]?.tempFilePath;
   if(!tempFilePath)return;
   let avatarPath=tempFilePath;
   if(Taro.getEnv()===Taro.ENV_TYPE.WEAPP){const saved:any=await Taro.saveFile({tempFilePath});avatarPath=saved.savedFilePath}
   Taro.setStorageSync("custom_avatar",avatarPath);setCustomAvatar(avatarPath);Taro.showToast({title:"头像已更新",icon:"success"});
  }catch(reason:any){if(!String(reason?.errMsg||reason||"").includes("cancel"))Taro.showToast({title:"头像更新失败",icon:"none"})}
 }
 function showProfile(){Taro.showModal({title:me.name,content:`角色：${role}\n部门：${me.department_name||"研发部"}\n账号：${me.username||"—"}`,showCancel:false})}
 function accountActions(){
  Taro.showActionSheet({itemList:["查看个人资料","退出登录"]}).then(async result=>{
   if(result.tapIndex===0){showProfile();return}
   const confirm=await Taro.showModal({title:"退出登录",content:"退出后需要重新使用微信登录，确定继续吗？",confirmText:"退出",confirmColor:"#D84F49"});
   if(confirm.confirm)logout();
  }).catch(()=>{});
 }
 function showDrafts(){const drafts=records.filter(record=>record.status==="DRAFT");Taro.showModal({title:`草稿箱（${drafts.length}）`,content:drafts.length?drafts.slice(0,5).map(record=>`• ${record.title}`).join("\n"):"当前没有未提交的草稿",showCancel:false})}
 function showRecent(){Taro.showModal({title:"最近查看",content:records.slice(0,5).map(record=>`• ${record.title}`).join("\n")||"暂无最近记录",showCancel:false})}
 function showFavorite(){Taro.showToast({title:"收藏功能将在二级页面阶段开放",icon:"none"})}
 function aiPreference(){const values=["简洁摘要","详细分析","风险优先"];Taro.showActionSheet({itemList:values}).then(result=>{Taro.setStorageSync("ai_preference",values[result.tapIndex]);Taro.showToast({title:`已选择${values[result.tapIndex]}`,icon:"success"})}).catch(()=>{})}
 function help(){Taro.showModal({title:"帮助与反馈",content:"记录页支持文字、语音、照片和文件。提交后 AI 会按结构、软件、模具、测试等方向整理分类，负责人可在待处理页面更新进展。\n\n反馈问题请联系研发项目管理员。",showCancel:false})}
 function about(){Taro.showModal({title:"关于 AI项目助手",content:"让研发项目记录更简单，让产品开发问题处理有闭环。\n\n当前版本：0.3.0 内部试用版",showCancel:false})}
 async function subscribe(){try{await requestNotificationSubscription();Taro.showToast({title:"通知订阅成功",icon:"success"})}catch(reason:any){Taro.showToast({title:reason.message||"订阅失败",icon:"none"})}}
 const menuOne=[{icon:"draft",image:menuDraftIcon,label:"草稿箱",value:String(records.filter(record=>record.status==="DRAFT").length),action:showDrafts},{icon:"star",image:menuFavoriteIcon,label:"收藏",value:"",action:showFavorite},{icon:"recent",image:menuRecentIcon,label:"最近查看",value:"",action:showRecent}];
 const menuTwo=[{icon:"ai",image:menuAiIcon,label:"AI 偏好设置",value:Taro.getStorageSync("ai_preference")||"",action:aiPreference},{icon:"bell",image:menuNotificationIcon,label:"消息通知",value:unread?`${unread} 条未读`:"",action:subscribe},{icon:"help",image:menuHelpIcon,label:"帮助与反馈",value:"",action:help},{icon:"about",image:menuAboutIcon,label:"关于我们",value:"",action:about}];
 return <View className="page me-page">
  <View className="status-spacer" style={{height:`${statusBarHeight}px`}}/>
  <View className="capsule-clearance" style={{height:`${capsuleClearance}px`}}/>
  {error&&<View className="me-error"><Text>{error}</Text><Text className="pressable" onClick={load}>重新加载</Text></View>}
  <View aria-label="账号与退出登录" className="profile pressable" onClick={accountActions}><View aria-label="修改头像" className="avatar-picker pressable" onClick={changeAvatar}><Image className="avatar" src={customAvatar||me.avatar||logo} mode="aspectFill"/><View className="avatar-camera"><View className="avatar-camera-lens"/></View></View><View><View><Text className="profile-name">{loading?"加载中…":me.name||"陈工"}</Text><Text className="role-badge">{role}</Text></View><Text className="department">{me.department_name||"研发部"}</Text></View><Text className="chevron">›</Text></View>
  <View className="stats-card"><View onClick={()=>Taro.switchTab({url:"/pages/record/index"})}><View className="stat-icon stat-record"/><Text className="stat-label">我的记录</Text><Text className="stat-value">{records.length}</Text><Text className="stat-unit">全部记录</Text></View><View onClick={showRecent}><View className="stat-icon stat-star">☆</View><Text className="stat-label">我创建的</Text><Text className="stat-value">{created}</Text><Text className="stat-unit">条记录</Text></View><View onClick={()=>Taro.switchTab({url:"/pages/todos/index"})}><View className="stat-icon stat-follow"/><Text className="stat-label">待我跟进</Text><Text className="stat-value">{pending}</Text><Text className="stat-unit">条任务</Text></View><View onClick={()=>Taro.switchTab({url:"/pages/todos/index"})}><View className="stat-icon stat-done"/><Text className="stat-label">已完成</Text><Text className="stat-value">{done}</Text><Text className="stat-unit">条任务</Text></View></View>
  <View className="menu-card">{menuOne.map(item=><View aria-label={item.label} className="menu-row pressable" key={item.label} onClick={item.action}><View><Image className="menu-icon-image" src={item.image} mode="aspectFit"/><Text>{item.label}</Text></View><View><Text>{item.value}</Text><Text className="chevron">›</Text></View></View>)}</View>
  <View className="menu-card">{menuTwo.map(item=><View aria-label={item.label} className="menu-row pressable" key={item.label} onClick={item.action}><View><Image className="menu-icon-image" src={item.image} mode="aspectFit"/><Text>{item.label}</Text></View><View><Text>{item.value}</Text>{item.icon==="bell"&&unread>0&&<View className="unread-dot"/>}<Text className="chevron">›</Text></View></View>)}</View>
  <View className="version"><Image src={logo} mode="aspectFill"/><Text>AI项目助手 · 内部试用版</Text></View><View className="safe-bottom"/>
 </View>
}
