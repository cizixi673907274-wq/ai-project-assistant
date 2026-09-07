export const RECORD_STATUSES = ["DRAFT","SUBMITTED","AI_PROCESSING","AI_REVIEW_REQUIRED","READY_TO_ASSIGN","ASSIGNED","IN_PROGRESS","WAITING_SUPPLEMENT","RESOLVED","CLOSED","REJECTED","CANCELLED"] as const;
export type RecordStatus = typeof RECORD_STATUSES[number];
export type Priority = "LOW" | "MEDIUM" | "HIGH" | "URGENT";
export interface ApiResponse<T> { success: boolean; data: T; message: string; request_id: string }
export interface RecordItem { id:string; title:string; content:string; summary?:string; status:RecordStatus; priority:Priority; project_name?:string; creator_name?:string; created_at:string }
