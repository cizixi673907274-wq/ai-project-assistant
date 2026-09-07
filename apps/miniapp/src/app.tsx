import type {PropsWithChildren} from "react";
import "./app.scss";
if(process.env.TARO_ENV==="h5")require("./app.h5.scss");
export default function App(props:PropsWithChildren){return props.children}
