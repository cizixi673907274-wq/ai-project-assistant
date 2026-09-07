from pydantic import BaseModel, field_validator
class LoginRequest(BaseModel): username:str; password:str
class WechatLoginRequest(BaseModel): code:str; employee_mobile:str|None=None
class SmsCodeRequest(BaseModel):
    mobile:str
    @field_validator("mobile")
    @classmethod
    def valid_mobile(cls,value:str):
        value=value.strip()
        if len(value)!=11 or not value.startswith("1") or not value.isdigit(): raise ValueError("手机号格式不正确")
        return value
class MobileLoginRequest(SmsCodeRequest): code:str
class RefreshTokenRequest(BaseModel): refresh_token:str
class TokenPair(BaseModel): access_token:str; refresh_token:str; token_type:str="bearer"
class UserOut(BaseModel):
    id:str; username:str; name:str; mobile:str|None; department_id:str|None; roles:list[str]; permissions:list[str]
