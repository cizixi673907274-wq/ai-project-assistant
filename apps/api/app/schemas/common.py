from typing import Any, Generic, TypeVar
from pydantic import BaseModel
T=TypeVar("T")
class ApiResponse(BaseModel,Generic[T]): success:bool=True; data:T; message:str="ok"; request_id:str
class ErrorBody(BaseModel): code:str; message:str; details:dict[str,Any]={}
class ErrorResponse(BaseModel): success:bool=False; error:ErrorBody; request_id:str
