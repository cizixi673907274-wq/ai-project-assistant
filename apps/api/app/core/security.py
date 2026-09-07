from datetime import datetime, timedelta, timezone
import jwt
from pwdlib import PasswordHash
from app.core.config import settings
password_hash=PasswordHash.recommended()
def hash_password(value:str)->str: return password_hash.hash(value)
def verify_password(value:str, hashed:str)->bool: return password_hash.verify(value,hashed)
def create_token(subject:str, token_type:str="access"):
    delta=timedelta(minutes=settings.access_token_expire_minutes) if token_type=="access" else timedelta(days=settings.refresh_token_expire_days)
    return jwt.encode({"sub":subject,"type":token_type,"exp":datetime.now(timezone.utc)+delta},settings.secret_key,algorithm="HS256")
def decode_token(token:str): return jwt.decode(token,settings.secret_key,algorithms=["HS256"])
