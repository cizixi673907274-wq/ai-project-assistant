import Taro from "@tarojs/taro";

const DEFAULT_API_BASE="http://localhost:8000/api/v1";
const API_BASE_STORAGE_KEY="miniapp_api_base_url";
const configuredBase=process.env.TARO_APP_API_BASE_URL;
let redirecting=false;

export function getApiBase(){const saved=Taro.getStorageSync(API_BASE_STORAGE_KEY);return configuredBase&&configuredBase.trim()?configuredBase.trim():typeof saved==="string"&&saved.trim()?saved.trim():DEFAULT_API_BASE}
export function setApiBase(base:string){if(!base||!String(base).trim())return;Taro.setStorageSync(API_BASE_STORAGE_KEY,String(base).trim())}
function unwrap<T>(body:any):T{if(!body?.success)throw new Error(body?.error?.message||body?.message||"请求失败");return body.data as T}
function messageOf(body:any,fallback:string){
 if(!body)return fallback;
 if(body.error?.message)return body.error.message;
 if(typeof body.detail==="string")return body.detail;
 if(body.detail?.message)return body.detail.message;
 if(body.message)return body.message;
 return fallback;
}
function networkMessage(action:string,reason?:any){
 const detail=reason?.errMsg||reason?.message||"";
 return `${action}失败：手机需要和电脑连接同一个 Wi-Fi，并确保电脑 API 服务可访问。当前预览使用 ${getApiBase()}。${detail?` 原因：${detail}`:""}`;
}

function goLogin(){
 if(redirecting)return;redirecting=true;
 Taro.reLaunch({url:"/pages/login/index"}).finally(()=>{redirecting=false});
}

export function hasToken(){return Boolean(Taro.getStorageSync("token"))}

export async function loginWithWechat(employeeMobile?:string){
 let code="dev-engineer";
 try{const login=await Taro.login();if(login.code)code=login.code}catch{}
 const response=await Taro.request({url:`${getApiBase()}/auth/wechat/login`,method:"POST",data:{code,employee_mobile:employeeMobile?.trim()||undefined}}).catch(reason=>{throw new Error(networkMessage("微信登录",reason))});
 if(response.statusCode>=400)throw new Error(messageOf(response.data,"微信登录失败"));
 const auth=unwrap<{access_token:string;refresh_token?:string}>(response.data);
 Taro.setStorageSync("token",auth.access_token);if(auth.refresh_token)Taro.setStorageSync("refresh_token",auth.refresh_token);
 return auth;
}

export async function sendSmsCode(mobile:string){
 const response=await Taro.request({url:`${getApiBase()}/auth/sms/send`,method:"POST",data:{mobile},header:{"Content-Type":"application/json"}}).catch(reason=>{throw new Error(networkMessage("验证码发送",reason))});
 if(response.statusCode>=400)throw new Error(messageOf(response.data,"验证码发送失败"));
 return unwrap<{expires_in:number;dev_code?:string}>(response.data);
}

export async function loginWithMobile(mobile:string,code:string){
 const response=await Taro.request({url:`${getApiBase()}/auth/mobile/login`,method:"POST",data:{mobile,code},header:{"Content-Type":"application/json"}}).catch(reason=>{throw new Error(networkMessage("手机号登录",reason))});
 if(response.statusCode>=400)throw new Error(messageOf(response.data,"手机号登录失败"));
 const auth=unwrap<{access_token:string;refresh_token?:string}>(response.data);
 Taro.setStorageSync("token",auth.access_token);if(auth.refresh_token)Taro.setStorageSync("refresh_token",auth.refresh_token);
 return auth;
}

export function logout(){
 Taro.removeStorageSync("token");Taro.removeStorageSync("refresh_token");Taro.removeStorageSync("custom_avatar");goLogin();
}

export async function token(){
 const value=Taro.getStorageSync("token");if(value)return value;goLogin();throw new Error("请先登录");
}

export async function request<T>(path:string,method:"GET"|"POST"|"PATCH"|"DELETE"="GET",data?:unknown){
 let auth=await token();let response=await Taro.request({url:`${getApiBase()}${path}`,method,data,header:{Authorization:`Bearer ${auth}`,"Content-Type":"application/json"}}).catch(reason=>{throw new Error(networkMessage("请求",reason))});
 if(response.statusCode===401){Taro.removeStorageSync("token");Taro.removeStorageSync("refresh_token");goLogin();throw new Error("登录已过期，请重新登录")}
 if(response.statusCode>=400)throw new Error(messageOf(response.data,"请求失败"));return unwrap<T>(response.data);
}

export async function uploadRecordFile(recordId:string,filePath:string,mediaType:"IMAGE"|"AUDIO"|"FILE"){
 const auth=await token();const response=await Taro.uploadFile({url:`${getApiBase()}/uploads/direct`,filePath,name:"file",formData:{record_id:recordId,media_type:mediaType},header:{Authorization:`Bearer ${auth}`}}).catch(reason=>{throw new Error(networkMessage("文件上传",reason))});
 const body=typeof response.data==="string"?JSON.parse(response.data):response.data;
 if(response.statusCode>=400)throw new Error(messageOf(body,"文件上传失败"));return unwrap<{id:string;original_name:string;type:string}>(body);
}

export async function transcribeAudio(filePath:string){
 const auth=await token();const response=await Taro.uploadFile({url:`${getApiBase()}/uploads/transcribe-direct`,filePath,name:"file",header:{Authorization:`Bearer ${auth}`}}).catch(reason=>{throw new Error(networkMessage("语音识别",reason))});
 const body=typeof response.data==="string"?JSON.parse(response.data):response.data;
 if(response.statusCode>=400)throw new Error(messageOf(body,"语音识别失败"));return unwrap<{transcript:string;provider:string}>(body);
}

export async function requestNotificationSubscription(){
 const ids=(process.env.TARO_APP_SUBSCRIBE_TEMPLATE_IDS||"").split(",").map(v=>v.trim()).filter(Boolean);
 if(!ids.length)throw new Error("尚未配置微信订阅消息模板");return (Taro.requestSubscribeMessage as any)({tmplIds:ids});
}
