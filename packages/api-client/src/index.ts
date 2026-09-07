import type { ApiResponse, RecordItem } from "@ai-field/shared-types";
export class ApiClient {
  constructor(private baseUrl:string, private getToken:()=>string|null=()=>null) {}
  async request<T>(path:string, init:RequestInit={}):Promise<T> {
    const token=this.getToken(); const headers=new Headers(init.headers);
    if (!(init.body instanceof FormData)) headers.set("Content-Type","application/json");
    if(token) headers.set("Authorization",`Bearer ${token}`);
    const res=await fetch(`${this.baseUrl}${path}`,{...init,headers});
    const body=await res.json() as ApiResponse<T> & {error?:{message:string}};
    if(!res.ok||!body.success) throw new Error(body.error?.message||body.message||"请求失败");
    return body.data;
  }
  login(username:string,password:string){ return this.request<{access_token:string;refresh_token:string}>("/auth/login",{method:"POST",body:JSON.stringify({username,password})}); }
  records(){ return this.request<RecordItem[]>("/records"); }
}
