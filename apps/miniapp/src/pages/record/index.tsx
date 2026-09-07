import {Button,Image,Text,Textarea,View} from "@tarojs/components";
import Taro,{useDidShow} from "@tarojs/taro";
import {useEffect,useState} from "react";
import {request,transcribeAudio,uploadRecordFile} from "../../services/api";
import homeHero from "../../assets/home-hero.jpg";
import cameraIcon from "../../assets/icons/camera.png";
import imageIcon from "../../assets/icons/image.png";
import micCircleIcon from "../../assets/icons/mic_circle.png";
import sendIcon from "../../assets/icons/send.png";
import uploadIcon from "../../assets/icons/upload.png";
import "./index.scss";

type Attachment={path:string;name:string;type:"IMAGE"|"AUDIO"|"FILE";size?:number;transcript?:string};
const recorder=Taro.getEnv()===Taro.ENV_TYPE.WEAPP?Taro.getRecorderManager():null;

export default function RecordPage(){
 const statusBarHeight=Taro.getWindowInfo?.().statusBarHeight||20;
 const [content,setContent]=useState("");
 const [textareaFocus,setTextareaFocus]=useState(false),[selection,setSelection]=useState({start:-1,end:-1});
 const [sending,setSending]=useState(false),[recording,setRecording]=useState(false),[transcribing,setTranscribing]=useState(false),[recordingSeconds,setRecordingSeconds]=useState(0),[loading,setLoading]=useState(true);
 const [projects,setProjects]=useState<any[]>([]),[projectIndex,setProjectIndex]=useState(0);
 const [attachments,setAttachments]=useState<Attachment[]>([]),[me,setMe]=useState<any>({name:"陈工"}),[loadError,setLoadError]=useState("");

 async function load(){
  setLoading(true);setLoadError("");
  try{const [projectRows,user]=await Promise.all([request<any[]>("/projects"),request<any>("/me")]);setProjects(projectRows);setMe(user)}
  catch(error:any){setLoadError(error.message||"页面加载失败")}
  finally{setLoading(false)}
 }
 useDidShow(()=>{load()});
 useEffect(()=>{
  if(!recorder)return;
  recorder.onStart(()=>{setRecording(true);Taro.showToast({title:"录音中，再点一次结束",icon:"none",duration:1800})});
  recorder.onStop(result=>{setRecording(false);void recognizeVoice(result.tempFilePath)});
  recorder.onError((reason:any)=>{setRecording(false);const denied=String(reason?.errMsg||"").toLowerCase().includes("auth");Taro.showToast({title:denied?"未获得麦克风权限":"录音失败，请稍后重试",icon:"none"})});
 },[]);
 useEffect(()=>{if(!recording){setRecordingSeconds(0);return}const timer=setInterval(()=>setRecordingSeconds(value=>value+1),1000);return()=>clearInterval(timer)},[recording]);
 async function recognizeVoice(filePath:string){
  if(!filePath)return;setTranscribing(true);
  try{const result=await transcribeAudio(filePath);const text=result.transcript.trim();if(!text)throw new Error("没有识别到清晰语音");setContent(value=>[value.trim(),text].filter(Boolean).join("\n"));Taro.showToast({title:"语音已转成文字",icon:"success"})}
  catch(reason:any){Taro.showModal({title:"语音识别失败",content:reason.message||"请重试或改用文字输入",showCancel:false})}
  finally{setTranscribing(false)}
 }
 async function ensureRecordPermission(){
  const settings:any=await Taro.getSetting();const current=settings.authSetting?.["scope.record"];
  if(current===true)return true;
  if(current===false){
   const result=await Taro.showModal({title:"需要麦克风权限",content:"请在小程序设置中允许使用麦克风，才能录制项目语音。",confirmText:"去设置"});
   if(!result.confirm)return false;const opened:any=await Taro.openSetting();return opened.authSetting?.["scope.record"]===true;
  }
  try{await Taro.authorize({scope:"scope.record" as any});return true}catch{return false}
 }
async function toggleRecording(){
 if(!recorder){Taro.showToast({title:"请在微信小程序中使用录音",icon:"none"});return}
 if(transcribing){Taro.showToast({title:"正在识别上一段语音",icon:"none"});return}
 if(recording){recorder.stop();return}
  try{if(!await ensureRecordPermission()){Taro.showToast({title:"请先允许麦克风权限",icon:"none"});return}recorder.start({duration:60000,format:"mp3",sampleRate:16000,numberOfChannels:1,encodeBitRate:48000})}
 catch{Taro.showToast({title:"无法开启录音，请检查系统权限",icon:"none"})}
}
 async function choosePhoto(){
  try{
   const picker=typeof Taro.chooseMedia==="function"?Taro.chooseMedia:Taro.chooseImage;
   const result:any=await picker({count:6,mediaType:["image"],sourceType:["camera","album"]});
   const files=result?.tempFiles||[];
   setAttachments(items=>[...items,...files.map((file:any,i:number)=>({path:file.tempFilePath||file.filePath,name:file.name||`项目照片-${Date.now()}-${i+1}.jpg`,type:"IMAGE" as const,size:file.size}))]);
  }catch(reason:any){if(!String(reason?.errMsg||"").includes("cancel")){Taro.showToast({title:"照片选择失败，请重试",icon:"none"})}}
 }
 async function chooseFile(){
  if(typeof Taro.chooseMessageFile!=="function"){Taro.showToast({title:"当前微信版本暂不支持文件选择",icon:"none"});return}
  try{
   const result=await Taro.chooseMessageFile({count:5,type:"file"});
   setAttachments(items=>[...items,...result.tempFiles.map(file=>({path:file.path,name:file.name,type:"FILE" as const,size:file.size}))]);
  }catch(reason:any){if(!String(reason?.errMsg||"").includes("cancel")){Taro.showToast({title:"文件选择失败，请重试",icon:"none"})}}
 }
 function removeAttachment(index:number){setAttachments(items=>items.filter((_,i)=>i!==index))}
 function previewContent(){if(!content.trim())return;Taro.showModal({title:"记录内容",content:content.trim(),showCancel:false,confirmText:"关闭"})}
 function selectAllContent(){
  if(!content)return;
  setTextareaFocus(true);
  setSelection({start:0,end:content.length});
  Taro.showToast({title:"已全选输入内容",icon:"none"});
 }
 function previewAttachment(item:Attachment){
  if(item.type==="IMAGE")return Taro.previewImage({current:item.path,urls:attachments.filter(file=>file.type==="IMAGE").map(file=>file.path)});
  if(item.type==="FILE")return Taro.openDocument({filePath:item.path,showMenu:true}).catch(()=>Taro.showModal({title:item.name,content:"当前文件暂不支持直接预览，可提交后在 PC Web 记录中心查看附件。",showCancel:false}));
  if(item.transcript)return Taro.showModal({title:item.name,content:item.transcript,showCancel:false});
  return Taro.showModal({title:item.name,content:"该附件暂无可预览内容。",showCancel:false});
 }
 function chooseProject(){if(!projects.length)return Taro.showToast({title:"暂无可选项目",icon:"none"});Taro.showActionSheet({itemList:projects.map(project=>project.name)}).then(result=>setProjectIndex(result.tapIndex)).catch(()=>{})}
 async function send(){
  if(!projects.length)return Taro.showToast({title:"暂无可选项目，请联系管理员",icon:"none"});
  if(recording||transcribing)return Taro.showToast({title:recording?"请先结束录音":"请等待语音识别完成",icon:"none"});
  if(!content.trim())return Taro.showToast({title:"请先描述情况或录制语音",icon:"none"});
  setSending(true);
  try{
   const record=await request<any>("/records","POST",{content:content.trim()||"语音项目记录，正在转写",project_id:projects[projectIndex]?.id});let transcript="";
   for(const attachment of attachments.filter(item=>item.type!=="AUDIO")){await uploadRecordFile(record.id,attachment.path,attachment.type)}
   if(transcript)await request(`/records/${record.id}`,"PATCH",{content:[content.trim(),transcript.trim()].filter(Boolean).join("\n")});
   await request(`/records/${record.id}/submit`,"POST");setContent("");setAttachments([]);Taro.showToast({title:"已提交，AI 正在整理",icon:"success"});
  }catch(error:any){Taro.showToast({title:error.message||"提交失败",icon:"none",duration:3000})}finally{setSending(false)}
 }
 return <View className="page record-page">
  <View className="status-spacer" style={{height:`${statusBarHeight}px`}}/>
  <View className="hero-banner">
   <View className="hero-copy"><View className="title"><Text>AI</Text>项目助手</View><View className="subtitle">随手记录，AI 自动整理并推送给相关负责人</View></View>
   <View className="hero-art-window"><Image className="hero-art" src={homeHero} mode="widthFix"/></View>
  </View>
  <View className="question">{me.name}，今天项目有什么情况？</View><View className="hint">您可以语音输入或输入文字，AI 帮您整理</View>
  {loadError&&<View className="load-error"><Text>{loadError}</Text><Text className="pressable" onClick={load}>重新加载</Text></View>}
  <View className={recording?"composer is-recording":"composer"}>
   <Textarea value={content} focus={textareaFocus} selectionStart={selection.start} selectionEnd={selection.end} onBlur={()=>setTextareaFocus(false)} onInput={event=>{setContent(event.detail.value);setSelection({start:-1,end:-1})}} maxlength={10000} placeholder="描述问题、进展、需求或异常..."/>
   {content.trim()&&<View className="content-preview-row"><Text>已输入 {content.trim().length} 字</Text><View><Text className="pressable" onClick={previewContent}>查看全文</Text><Text className="pressable select-all" onClick={selectAllContent}>全选</Text></View></View>}
   {(recording||transcribing)&&<View className={recording?"voice-capture recording":"voice-capture transcribing"} onClick={recording?toggleRecording:undefined}><View className="voice-bars">{[1,2,3,4,5,6,7].map(item=><View key={item}/>)}</View><Text className="voice-state">{recording?"正在聆听":"正在识别"}</Text><Text className="voice-time">{recording?`00:${String(recordingSeconds).padStart(2,"0")}`:"正在写入输入框…"}</Text><View className="voice-stop">{recording?"■":"AI"}</View><Text className="voice-help">{recording?"点击结束并转换成文字":"请稍候，不要关闭页面"}</Text></View>}
   <View className="composer-actions"><Button aria-label="录音" onClick={toggleRecording} className={recording?"circle recording":"circle"}><Image className="main-action-icon" src={micCircleIcon} mode="aspectFit"/></Button><View/><Button aria-label="添加图片" onClick={choosePhoto} className="circle"><Image className="main-action-icon" src={imageIcon} mode="aspectFit"/></Button><Button aria-label="提交记录" loading={sending} disabled={loading} onClick={send} className="send"><Image className="send-action-icon" src={sendIcon} mode="aspectFit"/></Button></View>
  </View>
  {attachments.some(item=>item.type!=="AUDIO")&&<View className="attachments">{attachments.map((item,index)=>item.type!=="AUDIO"&&<View className="attachment-row pressable" key={`${item.path}-${index}`} onClick={()=>previewAttachment(item)}><View className="attachment-name"><View className={`attachment-icon ${item.type.toLowerCase()}`}/><Text>{item.name}</Text><Text className="attachment-tip">{item.type==="IMAGE"?"点击查看":"点击打开"}</Text></View><Text className="delete-action" onClick={(event:any)=>{event.stopPropagation();removeAttachment(index)}}>删除</Text></View>)}</View>}
  <View className="quick"><Button className="pressable" onClick={choosePhoto}><Image className="quick-image-icon" src={cameraIcon} mode="aspectFit"/><Text>拍摄照片</Text></Button><Button className="pressable" onClick={chooseFile}><Image className="quick-image-icon" src={uploadIcon} mode="aspectFit"/><Text>上传文件</Text></Button></View>
  <View className="privacy"><View className="lock-icon"/>内容仅你和相关负责人可见</View><View className="safe-bottom"/>
 </View>
}
