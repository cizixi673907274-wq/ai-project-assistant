from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Table, Text, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.enums import MediaType, Priority, RecordStatus, RoleCode, TaskStatus, UserStatus
from app.db.base import Base, UUIDTimestampMixin

user_roles=Table("user_roles",Base.metadata,Column("user_id",ForeignKey("users.id",ondelete="CASCADE"),primary_key=True),Column("role_id",ForeignKey("roles.id",ondelete="CASCADE"),primary_key=True))
role_permissions=Table("role_permissions",Base.metadata,Column("role_id",ForeignKey("roles.id",ondelete="CASCADE"),primary_key=True),Column("permission_id",ForeignKey("permissions.id",ondelete="CASCADE"),primary_key=True))
project_members=Table("project_members",Base.metadata,Column("project_id",ForeignKey("projects.id",ondelete="CASCADE"),primary_key=True),Column("user_id",ForeignKey("users.id",ondelete="CASCADE"),primary_key=True),Column("member_role",String(50),default="MEMBER"))

class Department(UUIDTimestampMixin,Base):
    __tablename__="departments"; name:Mapped[str]=mapped_column(String(100),unique=True); parent_id:Mapped[str|None]=mapped_column(ForeignKey("departments.id"),nullable=True)
class Permission(UUIDTimestampMixin,Base):
    __tablename__="permissions"; code:Mapped[str]=mapped_column(String(100),unique=True); name:Mapped[str]=mapped_column(String(100))
class Role(UUIDTimestampMixin,Base):
    __tablename__="roles"; code:Mapped[RoleCode]=mapped_column(Enum(RoleCode),unique=True); name:Mapped[str]=mapped_column(String(100)); permissions:Mapped[list[Permission]]=relationship(secondary=role_permissions,lazy="selectin")
class User(UUIDTimestampMixin,Base):
    __tablename__="users"; username:Mapped[str]=mapped_column(String(80),unique=True,index=True); name:Mapped[str]=mapped_column(String(80)); mobile:Mapped[str|None]=mapped_column(String(30),nullable=True); password_hash:Mapped[str]=mapped_column(String(255)); wechat_openid:Mapped[str|None]=mapped_column(String(100),unique=True,nullable=True); department_id:Mapped[str|None]=mapped_column(ForeignKey("departments.id"),nullable=True); status:Mapped[UserStatus]=mapped_column(Enum(UserStatus),default=UserStatus.ACTIVE); avatar:Mapped[str|None]=mapped_column(String(500),nullable=True); roles:Mapped[list[Role]]=relationship(secondary=user_roles,lazy="selectin"); department:Mapped[Department|None]=relationship()
class Project(UUIDTimestampMixin,Base):
    __tablename__="projects"; name:Mapped[str]=mapped_column(String(150)); code:Mapped[str]=mapped_column(String(50),unique=True); manager_id:Mapped[str|None]=mapped_column(ForeignKey("users.id"),nullable=True); status:Mapped[str]=mapped_column(String(30),default="ACTIVE"); deleted_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True); members:Mapped[list[User]]=relationship(secondary=project_members,lazy="selectin")
    department_id:Mapped[str|None]=mapped_column(ForeignKey("departments.id"),nullable=True); department:Mapped[Department|None]=relationship()
class Record(UUIDTimestampMixin,Base):
    __tablename__="records"; creator_id:Mapped[str]=mapped_column(ForeignKey("users.id"),index=True); project_id:Mapped[str|None]=mapped_column(ForeignKey("projects.id"),nullable=True,index=True); title:Mapped[str]=mapped_column(String(200),default="待AI生成标题"); content:Mapped[str]=mapped_column(Text); summary:Mapped[str|None]=mapped_column(Text,nullable=True); status:Mapped[RecordStatus]=mapped_column(Enum(RecordStatus),default=RecordStatus.DRAFT,index=True); priority:Mapped[Priority]=mapped_column(Enum(Priority),default=Priority.MEDIUM); category_snapshot:Mapped[str|None]=mapped_column(String(100),nullable=True); stage_snapshot:Mapped[str|None]=mapped_column(String(100),nullable=True); product_snapshot:Mapped[str|None]=mapped_column(String(100),nullable=True); assigned_department_id:Mapped[str|None]=mapped_column(ForeignKey("departments.id"),nullable=True); deleted_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True); creator:Mapped[User]=relationship(foreign_keys=[creator_id]); project:Mapped[Project|None]=relationship(); media:Mapped[list["RecordMedia"]]=relationship(cascade="all, delete-orphan",lazy="selectin"); analyses:Mapped[list["AIAnalysis"]]=relationship(cascade="all, delete-orphan",lazy="selectin")
class RecordMedia(UUIDTimestampMixin,Base):
    __tablename__="record_media"; record_id:Mapped[str]=mapped_column(ForeignKey("records.id",ondelete="CASCADE"),index=True); type:Mapped[MediaType]=mapped_column(Enum(MediaType)); storage_key:Mapped[str]=mapped_column(String(500)); original_name:Mapped[str]=mapped_column(String(255)); mime:Mapped[str]=mapped_column(String(100)); size:Mapped[int]=mapped_column(Integer); duration:Mapped[float|None]=mapped_column(Float,nullable=True); width:Mapped[int|None]=mapped_column(Integer,nullable=True); height:Mapped[int|None]=mapped_column(Integer,nullable=True); sha256:Mapped[str|None]=mapped_column(String(64),nullable=True); transcript:Mapped[str|None]=mapped_column(Text,nullable=True); extracted_text:Mapped[str|None]=mapped_column(Text,nullable=True)
class AIAnalysis(UUIDTimestampMixin,Base):
    __tablename__="ai_analyses"; record_id:Mapped[str]=mapped_column(ForeignKey("records.id",ondelete="CASCADE"),index=True); result_json:Mapped[dict]=mapped_column(JSON); confidence:Mapped[float]=mapped_column(Float); provider:Mapped[str]=mapped_column(String(50)); model:Mapped[str]=mapped_column(String(100)); prompt_version:Mapped[str]=mapped_column(String(50)); reasoning_summary:Mapped[str|None]=mapped_column(Text,nullable=True); raw_response_hash:Mapped[str|None]=mapped_column(String(64),nullable=True); latency_ms:Mapped[int]=mapped_column(Integer,default=0); token_usage:Mapped[dict|None]=mapped_column(JSON,nullable=True); cost_estimate:Mapped[float]=mapped_column(Float,default=0); attempt_count:Mapped[int]=mapped_column(Integer,default=1); confirmed:Mapped[bool]=mapped_column(Boolean,default=False); error:Mapped[str|None]=mapped_column(Text,nullable=True)
class RecordTask(UUIDTimestampMixin,Base):
    __tablename__="tasks"; record_id:Mapped[str]=mapped_column(ForeignKey("records.id"),index=True); assignee_id:Mapped[str]=mapped_column(ForeignKey("users.id"),index=True); department_id:Mapped[str|None]=mapped_column(ForeignKey("departments.id"),nullable=True); due_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True); status:Mapped[TaskStatus]=mapped_column(Enum(TaskStatus),default=TaskStatus.PENDING); response:Mapped[str|None]=mapped_column(Text,nullable=True); reminder_count:Mapped[int]=mapped_column(Integer,default=0); last_reminded_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True); assignee:Mapped[User]=relationship()
class RecordEvent(UUIDTimestampMixin,Base):
    __tablename__="record_events"; record_id:Mapped[str]=mapped_column(ForeignKey("records.id"),index=True); actor_id:Mapped[str|None]=mapped_column(ForeignKey("users.id"),nullable=True); event_type:Mapped[str]=mapped_column(String(100)); before_json:Mapped[dict|None]=mapped_column(JSON,nullable=True); after_json:Mapped[dict|None]=mapped_column(JSON,nullable=True); request_id:Mapped[str|None]=mapped_column(String(36),nullable=True)

class RecordComment(UUIDTimestampMixin,Base):
    __tablename__="record_comments"
    record_id:Mapped[str]=mapped_column(ForeignKey("records.id",ondelete="CASCADE"),index=True)
    author_id:Mapped[str]=mapped_column(ForeignKey("users.id"),index=True)
    content:Mapped[str]=mapped_column(Text)
    kind:Mapped[str]=mapped_column(String(30),default="COMMENT")
    author:Mapped[User]=relationship()

class Notification(UUIDTimestampMixin,Base):
    __tablename__="notifications"
    user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    type:Mapped[str]=mapped_column(String(50),default="SYSTEM")
    title:Mapped[str]=mapped_column(String(200))
    content:Mapped[str]=mapped_column(Text)
    related_record_id:Mapped[str|None]=mapped_column(ForeignKey("records.id",ondelete="CASCADE"),nullable=True,index=True)
    is_read:Mapped[bool]=mapped_column(Boolean,default=False,index=True)
    read_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)

class ReportExport(UUIDTimestampMixin,Base):
    __tablename__="report_exports"
    user_id:Mapped[str]=mapped_column(ForeignKey("users.id"),index=True)
    project_id:Mapped[str]=mapped_column(ForeignKey("projects.id"),index=True)
    format:Mapped[str]=mapped_column(String(20),default="DOCX")
    status:Mapped[str]=mapped_column(String(20),default="COMPLETED",index=True)
    filename:Mapped[str]=mapped_column(String(255))
    record_count:Mapped[int]=mapped_column(Integer,default=0)
    filters_json:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    completed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    user:Mapped[User]=relationship()
    project:Mapped[Project]=relationship()

class ExportTemplate(UUIDTimestampMixin,Base):
    __tablename__="export_templates"
    name:Mapped[str]=mapped_column(String(120),unique=True)
    format:Mapped[str]=mapped_column(String(20),default="XLSX")
    fields_json:Mapped[list]=mapped_column(JSON)
    is_default:Mapped[bool]=mapped_column(Boolean,default=False,index=True)
    is_active:Mapped[bool]=mapped_column(Boolean,default=True,index=True)
    creator_id:Mapped[str|None]=mapped_column(ForeignKey("users.id"),nullable=True)
    creator:Mapped[User|None]=relationship()

class ExportJob(UUIDTimestampMixin,Base):
    __tablename__="export_jobs"
    creator_id:Mapped[str]=mapped_column(ForeignKey("users.id"),index=True)
    template_id:Mapped[str]=mapped_column(ForeignKey("export_templates.id"),index=True)
    format:Mapped[str]=mapped_column(String(20),default="XLSX")
    filters_json:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    status:Mapped[str]=mapped_column(String(20),default="PENDING",index=True)
    file_key:Mapped[str|None]=mapped_column(String(500),nullable=True)
    filename:Mapped[str|None]=mapped_column(String(255),nullable=True)
    record_count:Mapped[int]=mapped_column(Integer,default=0)
    error:Mapped[str|None]=mapped_column(Text,nullable=True)
    attempt_count:Mapped[int]=mapped_column(Integer,default=0)
    completed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    expires_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True,index=True)
    creator:Mapped[User]=relationship()
    template:Mapped[ExportTemplate]=relationship()

class AIInvocationLog(UUIDTimestampMixin,Base):
    __tablename__="ai_invocation_logs"
    service:Mapped[str]=mapped_column(String(20))
    provider:Mapped[str]=mapped_column(String(50))
    model:Mapped[str]=mapped_column(String(100))
    status:Mapped[str]=mapped_column(String(20))
    latency_ms:Mapped[int]=mapped_column(Integer,default=0)
    request_id:Mapped[str|None]=mapped_column(String(36),nullable=True)
    token_usage:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    cost_estimate:Mapped[float]=mapped_column(Float,default=0)
    attempt_count:Mapped[int]=mapped_column(Integer,default=1)
    error:Mapped[str|None]=mapped_column(Text,nullable=True)
    record_id:Mapped[str|None]=mapped_column(ForeignKey("records.id"),nullable=True,index=True)
    media_id:Mapped[str|None]=mapped_column(ForeignKey("record_media.id"),nullable=True,index=True)
