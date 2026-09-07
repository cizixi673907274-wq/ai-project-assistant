import {Button,Checkbox,Image,Input,Text,View} from "@tarojs/components";
import Taro,{useDidShow} from "@tarojs/taro";
import {useEffect,useState} from "react";
import homeHero from "../../assets/home-hero.jpg";
import {hasToken,loginWithMobile,loginWithWechat,request,sendSmsCode} from "../../services/api";
import "./index.scss";

export default function Login(){
 const statusBarHeight=Taro.getWindowInfo?.().statusBarHeight||20;
 const [mobile,setMobile]=useState("13800005678"),[code,setCode]=useState("123456"),[agreed,setAgreed]=useState(false);
 const [submitting,setSubmitting]=useState(false),[sendingCode,setSendingCode]=useState(false),[checking,setChecking]=useState(true),[countdown,setCountdown]=useState(0);

 useDidShow(()=>{
  if(!hasToken()){setChecking(false);return}
  request("/me").then(()=>Taro.switchTab({url:"/pages/record/index"})).catch(()=>setChecking(false));
 });
 useEffect(()=>{if(countdown<=0)return;const timer=setTimeout(()=>setCountdown(value=>value-1),1000);return()=>clearTimeout(timer)},[countdown]);

 function validMobile(){const value=mobile.trim();if(!/^1\d{10}$/.test(value)){Taro.showToast({title:"请输入正确的手机号",icon:"none"});return false}return true}
 function requireAgreement(){if(agreed)return true;Taro.showToast({title:"请先阅读并同意用户协议和隐私政策",icon:"none"});return false}
 async function getCode(){
  if(!validMobile()||countdown>0)return;setSendingCode(true);
  try{const result=await sendSmsCode(mobile.trim());setCountdown(60);if(result.dev_code)Taro.showModal({title:"测试验证码",content:`当前为开发测试环境，验证码为 ${result.dev_code}`,showCancel:false});else Taro.showToast({title:"验证码已发送",icon:"success"})}
  catch(reason:any){Taro.showToast({title:reason.message||"验证码发送失败",icon:"none"})}finally{setSendingCode(false)}
 }
 async function submitMobile(){
  if(!validMobile()||!requireAgreement())return;if(!/^\d{6}$/.test(code.trim()))return Taro.showToast({title:"请输入6位验证码",icon:"none"});
  setSubmitting(true);
  try{await loginWithMobile(mobile.trim(),code.trim());Taro.showToast({title:"登录成功",icon:"success"});await Taro.switchTab({url:"/pages/record/index"})}
  catch(reason:any){Taro.showModal({title:"登录未完成",content:reason.message||"手机号登录失败，请稍后重试",showCancel:false})}
  finally{setSubmitting(false)}
 }
 async function submitTestAccount(){
  setMobile("13800005678");setCode("123456");setAgreed(true);setSubmitting(true);
  try{await loginWithMobile("13800005678","123456");Taro.showToast({title:"测试账号已登录",icon:"success"});await Taro.switchTab({url:"/pages/record/index"})}
  catch(reason:any){Taro.showModal({title:"测试登录未完成",content:reason.message||"请确认 API 服务已启动，并已执行 pnpm miniapp:preview",showCancel:false})}
  finally{setSubmitting(false)}
 }
 async function submitWechat(){
  if(!requireAgreement())return;setSubmitting(true);
  try{await loginWithWechat(mobile.trim()||undefined);Taro.showToast({title:"登录成功",icon:"success"});await Taro.switchTab({url:"/pages/record/index"})}
  catch(reason:any){Taro.showModal({title:"微信登录未完成",content:reason.message||"微信登录失败，请稍后重试",showCancel:false})}finally{setSubmitting(false)}
 }
 function showPolicy(title:string){Taro.showModal({title,content:title==="用户协议"?"本应用仅用于企业内部研发项目记录、任务协作与产品问题闭环。请妥善保管账号并对提交内容负责。":"我们仅收集登录、研发记录及任务协作所必需的信息，内容仅对您和相关负责人可见。",showCancel:false})}

 return <View className="login-page">
  <View className="login-status" style={{height:`${statusBarHeight}px`}}/>
  <View className="login-hero"><Image className="login-hero-image" src={homeHero} mode="widthFix"/><View className="login-brand"><Text><Text className="login-ai">AI</Text> 项目助手</Text><Text>让项目记录更简单，让问题处理有闭环</Text></View></View>
  <View className="login-card">
   <Text className="login-title">欢迎登录</Text><Text className="login-subtitle">使用手机号登录，体验更多功能</Text><Text className="test-login-tip">内部测试账号和验证码已预填，勾选协议即可登录</Text>
   <Text className="field-label">手机号</Text><View className="login-field phone-field"><View className="country-code"><Text>+86</Text><Text className="country-arrow">⌄</Text></View><View className="field-divider"/><Input type="number" maxlength={11} value={mobile} onInput={event=>setMobile(event.detail.value)} placeholder="请输入手机号"/></View>
   <Text className="field-label code-label">验证码</Text><View className="login-field code-field"><Input type="number" maxlength={6} value={code} onInput={event=>setCode(event.detail.value)} placeholder="请输入验证码"/><View className="field-divider"/><Button disabled={sendingCode||countdown>0} onClick={getCode}>{countdown>0?`${countdown}s后重试`:sendingCode?"发送中":"获取验证码"}</Button></View>
   <View className="agreement" onClick={()=>setAgreed(value=>!value)}><Checkbox value="agreed" checked={agreed} color="#14a47b"/><Text>我已阅读并同意</Text><Text className="policy-link" onClick={event=>{event.stopPropagation();showPolicy("用户协议")}}>《用户协议》</Text><Text>和</Text><Text className="policy-link" onClick={event=>{event.stopPropagation();showPolicy("隐私政策")}}>《隐私政策》</Text></View>
   <Button className="mobile-login" loading={submitting||checking} disabled={submitting||checking} onClick={submitMobile}>登录</Button>
   <Button className="test-login" disabled={submitting||checking} onClick={submitTestAccount}>使用内部测试账号进入</Button>
   <View className="other-login"><View/><Text>其他登录方式</Text><View/></View>
   <Button className="wechat-login" disabled={submitting||checking} onClick={submitWechat}><View className="wechat-mark"><View/><View/></View></Button><Text className="wechat-caption">微信登录</Text>
   <Text className="login-policy">▣ 内容仅对您和相关负责人可见</Text>
  </View>
 </View>
}
