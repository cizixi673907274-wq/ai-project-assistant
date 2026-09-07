from datetime import datetime
from pydantic import BaseModel, Field
from app.core.enums import Priority, RecordStatus
class RecordCreate(BaseModel): content:str=Field(min_length=1,max_length=10000); title:str|None=None; project_id:str|None=None; priority:Priority=Priority.MEDIUM; media_ids:list[str]=[]
class RecordUpdate(BaseModel): content:str|None=None; title:str|None=None; project_id:str|None=None; priority:Priority|None=None
class RecordOut(BaseModel):
    model_config={"from_attributes":True}
    id:str; title:str; content:str; summary:str|None; status:RecordStatus; priority:Priority; project_id:str|None; creator_id:str; category_snapshot:str|None; stage_snapshot:str|None; product_snapshot:str|None; created_at:datetime; updated_at:datetime
    project_name:str|None=None; creator_name:str|None=None; confidence:float|None=None
class AIConfirm(BaseModel): title:str|None=None; summary:str|None=None; category:str|None=None; stage:str|None=None; product:str|None=None; priority:Priority|None=None; department_id:str|None=None
class AssignRequest(BaseModel): assignee_id:str; department_id:str|None=None; due_at:datetime|None=None
class ProcessRequest(BaseModel): response:str=Field(min_length=1,max_length=5000)
class CloseRequest(BaseModel): note:str|None=None
