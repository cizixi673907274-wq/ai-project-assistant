import type {ReactNode} from "react"; import {Tag} from "antd";
export function PageTitle({title,sub,extra}:{title:string;sub:string;extra?:ReactNode}){return <div className="page-title"><div><h1>{title} <i>✦</i></h1><p>{sub}</p></div>{extra}</div>}
export function Stat({label,value,trend,icon}:{label:string;value:string|number;trend?:string;icon?:string}){return <div className="stat card"><span>{label}</span><b>{value}</b><small>{trend||"较上周 ↑ 8%"}</small>{icon&&<i>{icon}</i>}</div>}
export const statusMap:Record<string,[string,string]>={DRAFT:["草稿","default"],AI_PROCESSING:["AI分析中","processing"],AI_REVIEW_REQUIRED:["待确认","blue"],READY_TO_ASSIGN:["待分派","cyan"],ASSIGNED:["已指派","geekblue"],IN_PROGRESS:["处理中","orange"],RESOLVED:["待确认解决","purple"],CLOSED:["已完成","green"]};
export function Status({value}:{value:string}){const [text,color]=statusMap[value]||[value,"default"];return <Tag color={color}>{text}</Tag>}
