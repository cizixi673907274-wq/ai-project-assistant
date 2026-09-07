from fastapi import HTTPException
from app.core.enums import RecordStatus
TRANSITIONS={
 RecordStatus.DRAFT:{RecordStatus.SUBMITTED,RecordStatus.CANCELLED},RecordStatus.SUBMITTED:{RecordStatus.AI_PROCESSING},RecordStatus.AI_PROCESSING:{RecordStatus.AI_REVIEW_REQUIRED,RecordStatus.READY_TO_ASSIGN},RecordStatus.AI_REVIEW_REQUIRED:{RecordStatus.READY_TO_ASSIGN,RecordStatus.WAITING_SUPPLEMENT,RecordStatus.REJECTED},RecordStatus.READY_TO_ASSIGN:{RecordStatus.ASSIGNED},RecordStatus.ASSIGNED:{RecordStatus.IN_PROGRESS,RecordStatus.WAITING_SUPPLEMENT},RecordStatus.IN_PROGRESS:{RecordStatus.RESOLVED,RecordStatus.WAITING_SUPPLEMENT},RecordStatus.WAITING_SUPPLEMENT:{RecordStatus.AI_PROCESSING,RecordStatus.IN_PROGRESS},RecordStatus.RESOLVED:{RecordStatus.CLOSED,RecordStatus.IN_PROGRESS},RecordStatus.CLOSED:set(),RecordStatus.REJECTED:set(),RecordStatus.CANCELLED:set()}
def ensure_transition(current:RecordStatus,target:RecordStatus):
    if target not in TRANSITIONS[current]: raise HTTPException(status_code=409,detail={"code":"RECORD_STATUS_INVALID","message":f"记录处于{current.value}，不能变更为{target.value}"})
