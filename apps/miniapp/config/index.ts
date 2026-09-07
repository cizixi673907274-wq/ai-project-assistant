import {defineConfig} from "@tarojs/cli";

const isH5=process.env.TARO_ENV==="h5";

export default defineConfig({
 projectName:"ai-project-assistant-miniapp",
 date:"2026-07-18",
 designWidth:750,
 deviceRatio:{750:1},
 sourceRoot:"src",
 outputRoot:isH5?"dist-h5":"dist",
 framework:"react",
 compiler:"webpack5",
 cache:{enable:true},
 env:{
  TARO_APP_API_BASE_URL:JSON.stringify(process.env.TARO_APP_API_BASE_URL||"http://127.0.0.1:8000/api/v1"),
  TARO_APP_SUBSCRIBE_TEMPLATE_IDS:JSON.stringify(process.env.TARO_APP_SUBSCRIBE_TEMPLATE_IDS||"")
 },
 mini:{postcss:{pxtransform:{enable:true},cssModules:{enable:false}}},
 h5:{publicPath:"/",staticDirectory:"static"}
});
