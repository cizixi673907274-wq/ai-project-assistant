import {Image,Input,Text,View} from "@tarojs/components";
import Taro,{useDidShow} from "@tarojs/taro";
import {useMemo,useState} from "react";
import {request} from "../../services/api";
import {formatChinaDate,formatChinaDateTime} from "../../services/time";
import todoIcon0 from "../../assets/icons/todo-0.png";
import todoIcon1 from "../../assets/icons/todo-1.png";
import todoIcon2 from "../../assets/icons/todo-2.png";
import todoIcon3 from "../../assets/icons/todo-3.png";
import todoIcon4 from "../../assets/icons/todo-4.png";
import "./index.scss";

const priorities:any={URGENT:["高","high"],HIGH:["高","high"],MEDIUM:["中","medium"],LOW:["低","low"]};
const tabs=[{key:"TODO",label:"需我处理"},{key:"ALL",label:"全部"},{key:"CREATED",label:"我创建的"},{key:"DONE",label:"已完成"}];
const todoIcons=[todoIcon0,todoIcon1,todoIcon2,todoIcon3,todoIcon4];

export default function Todos(){
 const statusBarHeight=Taro.getWindowInfo?.().statusBarHeight||20;
 const [rows,setRows]=useState<any[]>([]),[me,setMe]=useState<any>({name:""}),[active,setActive]=useState("TODO"),[query,setQuery]=useState(""),[filterMode,setFilterMode]=useState("ALL"),[loading,setLoading]=useState(true),[error,setError]=useState("");
 async function load(){setLoading(true);setError("");try{const [tasks,user]=await Promise.all([request<any[]>("/tasks/my"),request<any>("/me")]);setRows(tasks);setMe(user)}catch(reason:any){setError(reason.message||"任务加载失败")}finally{setLoading(false)}}
 useDidShow(()=>{load()});
 const filtered=useMemo(()=>rows.filter(row=>active==="ALL"||(active==="TODO"&&!["DONE","CANCELLED"].includes(row.task_status))||(active==="CREATED"&&(row.creator_id?row.creator_id===me.id:row.creator_name===me.name))||(active==="DONE"&&row.task_status==="DONE")),[rows,active,me.id,me.name]);
 const visible=useMemo(()=>{const byMode=filtered.filter(row=>filterMode==="ALL"||(filterMode==="OVERDUE"&&row.overdue)||(filterMode==="HIGH"&&["HIGH","URGENT"].includes(row.priority)));const keyword=query.trim().toLowerCase();return keyword?byMode.filter(row=>[row.title,row.summary,row.project_name,row.creator_name].some(value=>String(value||"").toLowerCase().includes(keyword))):byMode},[filtered,query,filterMode]);
 const count=(key:string)=>key==="ALL"?rows.length:key==="TODO"?rows.filter(row=>!["DONE","CANCELLED"].includes(row.task_status)).length:key==="CREATED"?rows.filter(row=>row.creator_id?row.creator_id===me.id:row.creator_name===me.name).length:rows.filter(row=>row.task_status==="DONE").length;
 function filter(){Taro.showActionSheet({itemList:["全部任务","仅看逾期","仅看高优先级"]}).then(result=>{setFilterMode(["ALL","OVERDUE","HIGH"][result.tapIndex]||"ALL")}).catch(()=>{})}
 async function submitAction(row:any,action:"process"|"resolve"){
  const result=await Taro.showModal({title:action==="process"?"开始处理":"标记完成",content:"请输入处理说明",editable:true,placeholderText:"填写处理进展、结果或补充信息"} as any);
  if(!result.confirm)return;const response=(result as any).content?.trim();if(!response)return Taro.showToast({title:"请填写处理说明",icon:"none"});
  try{await request(`/records/${row.record_id}/${action}`,"POST",{response});Taro.showToast({title:action==="process"?"已开始处理":"已标记完成",icon:"success"});await load()}catch(reason:any){Taro.showToast({title:reason.message||"操作失败",icon:"none"})}
 }
 function openTask(row:any){
  const items=["查看任务详情"];if(!["DONE","CANCELLED"].includes(row.task_status))items.push(row.task_status==="IN_PROGRESS"?"标记处理完成":"开始处理");
  Taro.showActionSheet({itemList:items}).then(result=>{if(result.tapIndex===0)Taro.showModal({title:row.title,content:`${row.project_name||"未关联项目"}\n\n${row.summary||"暂无摘要"}\n\n${row.due_at?`截止：${formatChinaDateTime(row.due_at)}`:"未设置截止时间"}`,showCancel:false});if(result.tapIndex===1)submitAction(row,row.task_status==="IN_PROGRESS"?"resolve":"process")}).catch(()=>{})
 }
 return <View className="page todo-page">
  <View className="todo-header">
   <View className="status-spacer" style={{height:`${statusBarHeight}px`}}/>
   <View className="todo-nav"><View/><Text className="nav-title">待处理</Text><View/></View>
   <View className="search-box"><View className="small-search"/><Input value={query} onInput={event=>setQuery(event.detail.value)} placeholder="搜索任务、项目或创建人"/>{query&&<Text className="search-clear pressable" onClick={()=>setQuery("")}>清空</Text>}<View aria-label="筛选任务" className="search-filter pressable" onClick={filter}><Text>筛选</Text><Text>▽</Text></View></View>
   <View className="tabs">{tabs.map(tab=><View aria-label={`查看${tab.label}任务`} key={tab.key} className={active===tab.key?"active":""} onClick={()=>setActive(tab.key)}><Text>{tab.label}</Text><Text className="tab-count">{count(tab.key)}</Text></View>)}</View>
   {filterMode!=="ALL"&&<View className="active-filter"><Text>{filterMode==="OVERDUE"?"仅显示逾期任务":"仅显示高优先级任务"}</Text><Text className="pressable" onClick={()=>setFilterMode("ALL")}>清除筛选</Text></View>}
  </View>
  {error&&<View className="todo-feedback"><Text>{error}</Text><Text className="pressable" onClick={load}>重新加载</Text></View>}
  {loading&&!rows.length?<View className="skeleton-list">{[1,2,3].map(item=><View className="todo-skeleton" key={item}><View className="skeleton-icon"/><View><View className="skeleton-line"/><View className="skeleton-line"/><View className="skeleton-line"/></View></View>)}</View>:visible.map((row,index)=>{const priority=priorities[row.priority]||priorities.MEDIUM;return <View aria-label={`打开任务：${row.title}`} className={row.overdue?"todo-card overdue-card pressable":"todo-card pressable"} key={row.id} onClick={()=>openTask(row)}>
   <View className="record-icon"><Image className="todo-card-icon" src={todoIcons[index%todoIcons.length]} mode="aspectFit"/></View><View className="todo-main"><View className="todo-title"><Text className="task-name">{row.title}</Text>{row.created_at&&<Text className="created-date">{formatChinaDate(row.created_at)}</Text>}</View><View className="meta">{row.project_name||"未关联项目"}<Text className="meta-divider">|</Text>{row.creator_name}创建</View>
   <View className="tags"><Text className={priority[1]}>{priority[0]}</Text>{row.overdue&&<Text className="overdue">已逾期</Text>}<Text>{row.task_status==="DONE"?"已完成":row.task_status==="IN_PROGRESS"?"处理中":"待处理"}</Text></View><View className="summary">{row.summary||"暂无任务摘要"}</View>
   <View className="counts"><Text>催办 {row.reminder_count||0} 次</Text></View></View></View>})}
  {!loading&&!error&&!visible.length&&<View className="todo-empty"><View className="empty-icon"><View/><View/><View/></View><Text className="empty-title">{query?"没有匹配的任务":"当前分类暂无任务"}</Text><Text>{query?"换个关键词或清空筛选条件试试":"新的任务分派后会显示在这里"}</Text>{query&&<Text className="empty-action pressable" onClick={()=>setQuery("")}>清空搜索</Text>}</View>}
  <View className="safe-bottom"/>
 </View>
}
