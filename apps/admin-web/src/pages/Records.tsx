import {BellOutlined,CommentOutlined,DeleteOutlined,DownloadOutlined,FileImageOutlined,FileOutlined,PlusOutlined,ReloadOutlined,SwapOutlined} from "@ant-design/icons";
import {App,Button,Checkbox,DatePicker,Form,Input,Modal,Select,Space} from "antd";
import {useEffect,useMemo,useRef,useState} from "react";
import {useSearchParams} from "react-router-dom";
import {api,downloadRecordDocument,downloadRecordsTable,fetchMediaBlob} from "../api";
import {PageTitle,Status} from "../components";
import {formatDateTime} from "../time";

type ActionKind="process"|"resolve"|"close";
const actionMeta:Record<ActionKind,{title:string;placeholder:string;endpoint:string}>={
 process:{title:"开始处理",placeholder:"填写处理计划或当前进展",endpoint:"process"},
 resolve:{title:"标记解决",placeholder:"填写处理结果和验证情况",endpoint:"resolve"},
 close:{title:"关闭记录",placeholder:"填写关闭说明（可选）",endpoint:"close"}
};
const statusOptions=["DRAFT","AI_REVIEW_REQUIRED","READY_TO_ASSIGN","ASSIGNED","IN_PROGRESS","RESOLVED","CLOSED"].map(value=>({value,label:{DRAFT:"草稿",AI_REVIEW_REQUIRED:"待确认",READY_TO_ASSIGN:"待分派",ASSIGNED:"已指派",IN_PROGRESS:"处理中",RESOLVED:"待确认解决",CLOSED:"已完成"}[value]}));

export default function Records(){
 const {message,modal}=App.useApp();
 const [createForm]=Form.useForm();
 const [params]=useSearchParams();
 const [rows,setRows]=useState<any[]>([]),[current,setCurrent]=useState<any>(),[events,setEvents]=useState<any[]>([]),[comments,setComments]=useState<any[]>([]),[users,setUsers]=useState<any[]>([]),[managedProjects,setManagedProjects]=useState<any[]>([]);
 const [selectedIds,setSelectedIds]=useState<string[]>([]);
 const [keyword,setKeyword]=useState(params.get("keyword")||""),[project,setProject]=useState("ALL"),[status,setStatus]=useState("ALL");
 const [assignOpen,setAssignOpen]=useState(false),[reassignOpen,setReassignOpen]=useState(false),[createOpen,setCreateOpen]=useState(false),[assignee,setAssignee]=useState<string>(),[action,setAction]=useState<ActionKind>(),[note,setNote]=useState(""),[comment,setComment]=useState(""),[busy,setBusy]=useState(false),[mediaUrls,setMediaUrls]=useState<Record<string,string>>({}),[mediaPreview,setMediaPreview]=useState<{item:any;url:string}>();
 const mediaGeneration=useRef(0),objectUrls=useRef<string[]>([]);
 async function load(preferredId?:string){try{const data=await api.records() as any[];setRows(data);const selected=data.find(x=>x.id===(preferredId||current?.id))||data[0];setCurrent(selected);if(selected)await Promise.all([loadEvents(selected.id),loadMedia(selected.media||[])])}catch(e:any){message.error(e.message)}}
 async function loadEvents(id:string){const [eventRows,commentRows]=await Promise.all([api.request<any[]>(`/records/${id}/events`),api.request<any[]>(`/records/${id}/comments`)]);setEvents(eventRows);setComments(commentRows)}
 useEffect(()=>{load();Promise.all([api.request<any[]>("/users/assignable"),api.request<any[]>("/projects")]).then(([memberRows,projectRows])=>{setUsers(memberRows);setManagedProjects(projectRows)}).catch(e=>message.error(e.message))},[]);
 useEffect(()=>()=>{objectUrls.current.forEach(URL.revokeObjectURL)},[]);
 useEffect(()=>{setKeyword(params.get("keyword")||"")},[params]);
 const projects=useMemo(()=>Array.from(new Set(rows.map(r=>r.project_name).filter(Boolean))).map(value=>({value,label:value})),[rows]);
 const visible=useMemo(()=>rows.filter(r=>(!keyword||`${r.title} ${r.content} ${r.project_name}`.toLowerCase().includes(keyword.toLowerCase()))&&(project==="ALL"||r.project_name===project)&&(status==="ALL"||r.status===status)),[rows,keyword,project,status]);
 useEffect(()=>{if(visible.length&&!visible.some(r=>r.id===current?.id))choose(visible[0]);if(!visible.length&&current)setCurrent(undefined)},[keyword,project,status,rows,current?.id]);
 function choose(r:any){setCurrent(r);loadEvents(r.id);loadMedia(r.media||[])}
 async function loadMedia(items:any[]){
  const generation=++mediaGeneration.current;
  setMediaPreview(undefined);objectUrls.current.forEach(URL.revokeObjectURL);objectUrls.current=[];setMediaUrls({});
  const images=items.filter(item=>item.type==="IMAGE");if(!images.length)return;
  const pairs=await Promise.all(images.map(async item=>{try{const url=URL.createObjectURL(await fetchMediaBlob(item.id));return [item.id,url] as const}catch{return [item.id,""] as const}}));
  const urls=pairs.map(([,url])=>url).filter(Boolean);
  if(generation!==mediaGeneration.current){urls.forEach(URL.revokeObjectURL);return}
  objectUrls.current=urls;setMediaUrls(Object.fromEntries(pairs.filter(([,url])=>url)));
 }
 function canPreview(item:any){const mime=String(item.mime||"");return item.type==="IMAGE"||mime.startsWith("image/")||mime.startsWith("text/")||mime.startsWith("audio/")||mime.startsWith("video/")||mime==="application/pdf"}
 async function openMedia(item:any){
  setBusy(true);
  try{
   let url=mediaUrls[item.id];
   if(!url){url=URL.createObjectURL(await fetchMediaBlob(item.id));objectUrls.current.push(url)}
   if(canPreview(item)){
    setMediaPreview({item,url});
   }else{
    const anchor=document.createElement("a");anchor.href=url;anchor.download=item.original_name||"附件";document.body.appendChild(anchor);anchor.click();anchor.remove();URL.revokeObjectURL(url);
    objectUrls.current=objectUrls.current.filter(value=>value!==url);
   }
  }catch(e:any){message.error(e.message||"附件打开失败")}finally{setBusy(false)}
 }
 function renderMediaPreview(){if(!mediaPreview)return null;const mime=String(mediaPreview.item.mime||"");if(mediaPreview.item.type==="IMAGE"||mime.startsWith("image/"))return <img className="media-preview-image" src={mediaPreview.url} alt={mediaPreview.item.original_name}/>;if(mime.startsWith("video/"))return <video className="media-preview-player" src={mediaPreview.url} controls autoPlay/>;if(mime.startsWith("audio/"))return <audio className="media-preview-audio" src={mediaPreview.url} controls autoPlay/>;return <iframe className="media-preview-frame" src={mediaPreview.url} title={mediaPreview.item.original_name}/>}
 function mediaSize(bytes?:number){if(!bytes)return "未知大小";if(bytes<1024)return `${bytes} B`;if(bytes<1024*1024)return `${(bytes/1024).toFixed(1)} KB`;return `${(bytes/1024/1024).toFixed(1)} MB`}
 function mediaLabel(item:any){return item.type==="IMAGE"?"图片":item.type==="AUDIO"?"语音":item.type==="VIDEO"?"视频":"文件"}
 function renderMedia(){const items=current?.media||[];if(!items.length)return <div className="media-empty">暂无上传图片或附件</div>;return <div className="media-grid">{items.map((item:any)=><div className="media-card" key={item.id}><button className="media-thumb" onClick={()=>openMedia(item)}>{item.type==="IMAGE"&&mediaUrls[item.id]?<img src={mediaUrls[item.id]} alt={item.original_name}/>:item.type==="IMAGE"?<FileImageOutlined/>:<FileOutlined/>}</button><div className="media-meta"><b title={item.original_name}>{item.original_name}</b><small>{mediaLabel(item)} · {mediaSize(item.size)}</small>{item.transcript&&<p>{item.transcript}</p>}</div><Button size="small" block onClick={()=>openMedia(item)}>{canPreview(item)?"打开预览":"下载文件"}</Button></div>)}</div>}
 async function prepareAssign(){if(!current)return;setBusy(true);try{if(current.status==="AI_REVIEW_REQUIRED")await api.request(`/records/${current.id}/ai/confirm`,{method:"POST",body:"{}"});setAssignOpen(true);message.success("AI结果已确认，请选择责任人");await load(current.id)}catch(e:any){message.error(e.message)}finally{setBusy(false)}}
 async function assign(){if(!assignee)return message.warning("请选择责任人");setBusy(true);try{await api.request(`/records/${current.id}/assign`,{method:"POST",body:JSON.stringify({assignee_id:assignee})});message.success("已完成分派");setAssignOpen(false);setAssignee(undefined);await load(current.id)}catch(e:any){message.error(e.message)}finally{setBusy(false)}}
 async function submitAction(){if(!action||!current)return;const meta=actionMeta[action];if(action!=="close"&&!note.trim())return message.warning("请填写处理说明");setBusy(true);try{const body=action==="close"?{note}:{response:note};await api.request(`/records/${current.id}/${meta.endpoint}`,{method:"POST",body:JSON.stringify(body)});message.success(`${meta.title}成功`);setAction(undefined);setNote("");await load(current.id)}catch(e:any){message.error(e.message)}finally{setBusy(false)}}
 async function exportCurrent(){if(!current)return message.warning("请先选择一条记录");setBusy(true);try{await downloadRecordDocument(current.id,current.title);message.success("Word 文档已导出")}catch(e:any){message.error(e.message)}finally{setBusy(false)}}
 async function exportSelected(){if(!selectedIds.length)return message.warning("请先勾选需要导出的记录");setBusy(true);try{await downloadRecordsTable(selectedIds);message.success(`已导出 ${selectedIds.length} 条记录汇总表`)}catch(e:any){message.error(e.message)}finally{setBusy(false)}}
 async function addComment(){if(!current||!comment.trim())return message.warning("请输入协作评论");setBusy(true);try{await api.request(`/records/${current.id}/comments`,{method:"POST",body:JSON.stringify({content:comment})});setComment("");message.success("评论已发送");await loadEvents(current.id)}catch(e:any){message.error(e.message)}finally{setBusy(false)}}
 async function remind(){if(!current)return;setBusy(true);try{await api.request(`/records/${current.id}/remind`,{method:"POST",body:JSON.stringify({})});message.success("已向责任人发送催办通知");await loadEvents(current.id)}catch(e:any){message.error(e.message)}finally{setBusy(false)}}
 async function reassign(){if(!assignee)return message.warning("请选择新的责任人");setBusy(true);try{await api.request(`/records/${current.id}/reassign`,{method:"POST",body:JSON.stringify({assignee_id:assignee,note:note||undefined})});message.success("转派成功，已通知新责任人");setReassignOpen(false);setAssignee(undefined);setNote("");await load(current.id)}catch(e:any){message.error(e.message)}finally{setBusy(false)}}
 async function managerCreate(values:any){setBusy(true);try{const created=await api.request<any>("/records/manager-create",{method:"POST",body:JSON.stringify({...values,due_at:values.due_at?.toISOString()})});message.success("记录已创建并推送给工程师");setCreateOpen(false);createForm.resetFields();await load(created.id)}catch(e:any){message.error(e.message)}finally{setBusy(false)}}
 function removeCurrent(){if(!current)return;const target=current;modal.confirm({title:"删除记录",content:`确定删除“${target.title}”吗？删除后该记录不会出现在记录中心、待办、统计和导出中。`,okText:"删除记录",okType:"danger",cancelText:"取消",onOk:async()=>{setBusy(true);try{await api.request(`/records/${target.id}`,{method:"DELETE"});setSelectedIds(ids=>ids.filter(id=>id!==target.id));message.success("记录已删除");await load()}catch(e:any){message.error(e.message)}finally{setBusy(false)}}})}
 function toggleSelected(id:string,checked:boolean){setSelectedIds(current=>checked?[...new Set([...current,id])]:current.filter(value=>value!==id))}
 function toggleAll(checked:boolean){const ids=visible.map(r=>r.id);setSelectedIds(current=>checked?[...new Set([...current,...ids])]:current.filter(id=>!ids.includes(id)))}
 function actions(){if(!current)return null;if(["AI_REVIEW_REQUIRED","READY_TO_ASSIGN"].includes(current.status))return <Button type="primary" size="large" loading={busy} onClick={prepareAssign}>确认并分派</Button>;if(current.status==="ASSIGNED")return <Button type="primary" size="large" onClick={()=>setAction("process")}>开始处理</Button>;if(current.status==="IN_PROGRESS")return <Button type="primary" size="large" onClick={()=>setAction("resolve")}>标记解决</Button>;if(current.status==="RESOLVED")return <Button type="primary" size="large" onClick={()=>setAction("close")}>确认关闭</Button>;return <Button size="large" disabled>当前状态暂无操作</Button>}
 return <>
  <PageTitle title="记录中心" sub="创建项目任务，或查看、确认、分派工程师提交的研发问题记录" extra={<Space><Button type="primary" icon={<PlusOutlined/>} onClick={()=>{createForm.setFieldsValue({priority:"MEDIUM"});setCreateOpen(true)}}>创建记录</Button><Button icon={<ReloadOutlined/>} onClick={()=>load(current?.id)}>刷新</Button><Button icon={<DownloadOutlined/>} loading={busy} disabled={!selectedIds.length} onClick={exportSelected}>批量导出汇总表{selectedIds.length?`（${selectedIds.length}）`:""}</Button><Button icon={<DownloadOutlined/>} loading={busy} disabled={!current} onClick={exportCurrent}>导出当前记录</Button></Space>}/>
  <div className="filters"><Input allowClear value={keyword} onChange={e=>setKeyword(e.target.value)} placeholder="搜索关键词 / 项目 / 问题内容"/><Select value={project} onChange={setProject} options={[{value:"ALL",label:"全部项目"},...projects]}/><Select value={status} onChange={setStatus} options={[{value:"ALL",label:"全部状态"},...statusOptions]}/><Button onClick={()=>{setKeyword("");setProject("ALL");setStatus("ALL")}}>重置</Button></div>
  <div className="record-layout">
   <section className="record-list card"><div className="record-list-title"><h3>记录列表 <small>{visible.length}条</small></h3><Checkbox checked={!!visible.length&&visible.every(r=>selectedIds.includes(r.id))} indeterminate={visible.some(r=>selectedIds.includes(r.id))&&!visible.every(r=>selectedIds.includes(r.id))} onChange={e=>toggleAll(e.target.checked)}>全选</Checkbox></div>{visible.map(r=><div className="record-select-row" key={r.id}><Checkbox aria-label={`选择 ${r.title}`} checked={selectedIds.includes(r.id)} onChange={e=>toggleSelected(r.id,e.target.checked)}/><button className={current?.id===r.id?"record-item active":"record-item"} onClick={()=>choose(r)}><b>{r.title}</b><span>{r.project_name||"未关联项目"}　|　{r.creator_name}</span><Status value={r.status}/></button></div>)}{!visible.length&&<p className="empty">没有符合条件的记录</p>}</section>
   <section className="record-detail card">{current&&<><div className="detail-heading"><div><h2>{current.title}</h2><p className="muted">{current.project_name}　|　{current.creator_name}提交</p></div><Status value={current.status}/></div><hr/><h3>原始记录</h3><p>{current.content}</p><div className="ai-box"><b>✦ AI摘要</b><p>{current.summary||"AI正在整理…"}</p><span>问题类型：{current.category_snapshot||"待识别"}</span><span>优先级：{current.priority}</span><span>AI置信度：{Math.round((current.confidence||0)*100)}%</span></div><h3>研发附件</h3>{renderMedia()}<Space wrap>{actions()}{["ASSIGNED","IN_PROGRESS","RESOLVED"].includes(current.status)&&<><Button size="large" icon={<BellOutlined/>} onClick={remind}>催办</Button><Button size="large" icon={<SwapOutlined/>} onClick={()=>setReassignOpen(true)}>转派</Button></>}<Button size="large" icon={<DownloadOutlined/>} onClick={exportCurrent}>导出 Word</Button><Button size="large" onClick={()=>load(current.id)}>刷新</Button><Button danger size="large" icon={<DeleteOutlined/>} loading={busy} onClick={removeCurrent}>删除记录</Button></Space><div className="collaboration-box"><h3><CommentOutlined/> 协作记录</h3>{comments.map(c=><div className={c.kind==="REMINDER"?"comment reminder":"comment"} key={c.id}><b>{c.author_name}</b><span>{c.content}</span><small>{formatDateTime(c.created_at)}</small></div>)}{!comments.length&&<p className="muted">暂无协作评论</p>}<Space.Compact style={{width:"100%"}}><Input value={comment} onChange={e=>setComment(e.target.value)} onPressEnter={addComment} placeholder="输入处理意见、补充信息或验收反馈…"/><Button type="primary" loading={busy} onClick={addComment}>发送</Button></Space.Compact></div></>}</section>
   <aside className="flow card"><h3>处理流程</h3>{events.length?events.map((e,i)=><div className="flow-step done" key={e.id}><i>{i+1}</i><span><b>{eventName(e.event_type)}</b><small>{formatDateTime(e.created_at)}</small></span></div>):<p className="muted">暂无流转记录</p>}</aside>
  </div>
  <Modal title="确认并分派" open={assignOpen} onOk={assign} confirmLoading={busy} onCancel={()=>setAssignOpen(false)} okText="确认分派" cancelText="取消"><p>请选择负责处理该问题的成员：</p><Select showSearch optionFilterProp="label" style={{width:"100%"}} placeholder="选择责任人" value={assignee} onChange={setAssignee} options={users.map(u=>({value:u.id,label:`${u.name} · ${u.department||"未分部门"}`}))}/></Modal>
  <Modal title="创建并推送记录" open={createOpen} onOk={()=>createForm.submit()} confirmLoading={busy} onCancel={()=>{setCreateOpen(false);createForm.resetFields()}} okText="创建并推送" cancelText="取消">
   <p className="muted">主管创建的记录将直接指派给工程师，不经过 AI 分析与确认。</p>
   <Form form={createForm} layout="vertical" onFinish={managerCreate}>
    <Form.Item name="title" label="问题标题" rules={[{required:true,message:"请输入问题标题"}]}><Input maxLength={200}/></Form.Item>
    <Form.Item name="content" label="问题内容" rules={[{required:true,message:"请输入问题内容"}]}><Input.TextArea rows={5} maxLength={10000} showCount/></Form.Item>
    <Form.Item name="project_id" label="所属项目" rules={[{required:true,message:"请选择所属项目"}]}><Select showSearch optionFilterProp="label" options={managedProjects.map(item=>({value:item.id,label:`${item.name}（${item.code}）`}))}/></Form.Item>
    <Form.Item name="assignee_id" label="接收工程师" rules={[{required:true,message:"请选择工程师"}]}><Select showSearch optionFilterProp="label" options={users.map(item=>({value:item.id,label:`${item.name} · ${item.department||"未分团队"}`}))}/></Form.Item>
    <Form.Item name="priority" label="优先级"><Select options={[{value:"LOW",label:"低"},{value:"MEDIUM",label:"中"},{value:"HIGH",label:"高"},{value:"URGENT",label:"紧急"}]}/></Form.Item>
   <Form.Item name="due_at" label="截止时间（可选）"><DatePicker showTime style={{width:"100%"}}/></Form.Item>
   </Form>
  </Modal>
  <Modal title={mediaPreview?.item.original_name||"附件预览"} open={!!mediaPreview} footer={null} width="min(920px, 92vw)" onCancel={()=>setMediaPreview(undefined)} destroyOnHidden>{renderMediaPreview()}</Modal>
  <Modal title={action?actionMeta[action].title:"处理记录"} open={!!action} onOk={submitAction} confirmLoading={busy} onCancel={()=>{setAction(undefined);setNote("")}} okText="确认" cancelText="取消"><Input.TextArea rows={5} value={note} onChange={e=>setNote(e.target.value)} placeholder={action?actionMeta[action].placeholder:""}/></Modal>
  <Modal title="转派责任人" open={reassignOpen} onOk={reassign} confirmLoading={busy} onCancel={()=>{setReassignOpen(false);setNote("")}} okText="确认转派" cancelText="取消"><p>转派后原任务将取消，并通知新的责任人。</p><Select showSearch optionFilterProp="label" style={{width:"100%",marginBottom:14}} placeholder="选择新责任人" value={assignee} onChange={setAssignee} options={users.map(u=>({value:u.id,label:`${u.name} · ${u.department||"未分部门"}`}))}/><Input.TextArea rows={3} value={note} onChange={e=>setNote(e.target.value)} placeholder="转派说明（可选）"/></Modal>
 </>
}

function eventName(value:string){return ({SEEDED:"种子记录建立",RECORD_CREATED:"创建记录",RECORD_SUBMITTED:"工程师提交",AI_PROCESSING:"AI开始分析",AI_ANALYSIS_COMPLETED:"AI分析完成",AI_CONFIRMED:"管理员确认AI",AI_RESULT_EDITED:"修改AI结果",RECORD_ASSIGNED:"分派责任人",PROCESS_STARTED:"开始处理",PROCESS_COMMENTED:"提交处理进展",RECORD_RESOLVED:"标记解决",RECORD_CLOSED:"关闭记录",CLOSE_NOTE:"填写关闭说明",COMMENT_ADDED:"添加协作评论",RECORD_REMINDED:"发送催办",RECORD_REASSIGNED:"转派责任人"} as Record<string,string>)[value]||value}
