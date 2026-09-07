function utcDate(value:string){const raw=value.trim().replace(" ","T");return new Date(/(?:Z|[+-]\d{2}:?\d{2})$/.test(raw)?raw:`${raw}Z`)}
export function formatChinaDate(value:string){return new Intl.DateTimeFormat("zh-CN",{timeZone:"Asia/Shanghai",year:"numeric",month:"2-digit",day:"2-digit"}).format(utcDate(value))}
export function formatChinaDateTime(value:string){return new Intl.DateTimeFormat("zh-CN",{timeZone:"Asia/Shanghai",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hourCycle:"h23"}).format(utcDate(value))}
