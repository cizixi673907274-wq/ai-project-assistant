import {ApiClient} from "@ai-field/api-client";
const base=import.meta.env.VITE_API_BASE_URL||"/api/v1";
export const api=new ApiClient(base,()=>localStorage.getItem("token"));
export async function login(username:string,password:string){const t=await api.login(username,password);localStorage.setItem("token",t.access_token);localStorage.setItem("refresh_token",t.refresh_token);return t}
export function logout(){localStorage.removeItem("token");localStorage.removeItem("refresh_token")}
export async function restoreSession(){if(!localStorage.getItem("token"))return false;try{await api.request("/me");return true}catch{logout();return false}}
export async function currentAccount(){return api.request<{id:string;username:string;name:string;mobile?:string;department_id?:string;roles:string[];permissions:string[]}>("/me")}
export async function downloadRecordDocument(id:string,title:string){
 const headers=new Headers(),token=localStorage.getItem("token");if(token)headers.set("Authorization",`Bearer ${token}`);
 const response=await fetch(`${base}/records/${id}/export`,{headers});
 if(!response.ok)throw new Error("文档导出失败");
 const url=URL.createObjectURL(await response.blob()),anchor=document.createElement("a");
 anchor.href=url;anchor.download=`研发记录-${title.replace(/[\\/:*?"<>|]/g,"-").slice(0,40)}.docx`;document.body.appendChild(anchor);anchor.click();anchor.remove();URL.revokeObjectURL(url);
}
export async function downloadRecordsTable(recordIds:string[]){
 const headers=new Headers({"Content-Type":"application/json"}),token=localStorage.getItem("token");if(token)headers.set("Authorization",`Bearer ${token}`);
 const response=await fetch(`${base}/records/batch-export`,{method:"POST",headers,body:JSON.stringify({record_ids:recordIds})});
 if(!response.ok)throw new Error("批量文档导出失败");
 const url=URL.createObjectURL(await response.blob()),anchor=document.createElement("a");
 anchor.href=url;anchor.download=`研发记录批量汇总-${new Date().toISOString().slice(0,10)}.docx`;document.body.appendChild(anchor);anchor.click();anchor.remove();URL.revokeObjectURL(url);
}
export async function downloadProjectReport(projectId:string,projectName:string){
 const headers=new Headers(),token=localStorage.getItem("token");if(token)headers.set("Authorization",`Bearer ${token}`);
 const response=await fetch(`${base}/reports/projects/${projectId}/export`,{method:"POST",headers});
 if(!response.ok)throw new Error("项目报告导出失败");
 const disposition=response.headers.get("Content-Disposition")||"",match=disposition.match(/filename\*=UTF-8''([^;]+)/);
 const filename=match?decodeURIComponent(match[1]):`${projectName.replace(/[\\/:*?"<>|]/g,"-")}-研发问题闭环报告.docx`;
 const url=URL.createObjectURL(await response.blob()),anchor=document.createElement("a");
 anchor.href=url;anchor.download=filename;document.body.appendChild(anchor);anchor.click();anchor.remove();URL.revokeObjectURL(url);
}
export async function downloadExportJob(jobId:string,filename:string){
 const headers=new Headers(),token=localStorage.getItem("token");if(token)headers.set("Authorization",`Bearer ${token}`);
 const response=await fetch(`${base}/exports/${jobId}/download`,{headers});
 if(!response.ok)throw new Error("Excel 文件下载失败");
 const url=URL.createObjectURL(await response.blob()),anchor=document.createElement("a");
 anchor.href=url;anchor.download=filename||"研发记录汇总.xlsx";document.body.appendChild(anchor);anchor.click();anchor.remove();URL.revokeObjectURL(url);
}
export async function fetchMediaBlob(id:string){
 const headers=new Headers(),token=localStorage.getItem("token");if(token)headers.set("Authorization",`Bearer ${token}`);
 const response=await fetch(`${base}/uploads/${id}/content`,{headers});
 if(!response.ok){
  let detail="附件读取失败";
  try{const body=await response.json();detail=body?.error?.message||body?.detail?.message||detail}catch{}
  throw new Error(detail);
 }
 return response.blob();
}
