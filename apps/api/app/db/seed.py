from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.core.enums import Priority, RecordStatus, RoleCode
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.entities import AIAnalysis, Department, ExportTemplate, Notification, Permission, Project, Record, RecordComment, RecordEvent, RecordTask, Role, User
from app.services.exports import DEFAULT_FIELDS
PERMISSIONS={
 RoleCode.ENGINEER:["record:create","record:view_related","record:process"],
 RoleCode.PROJECT_MANAGER:["record:view_project","ai:confirm","record:assign","record:close","risk:view"],
 RoleCode.DEPARTMENT_HEAD:["record:view_department","record:assign","risk:view"],
 RoleCode.SUPER_ADMIN:["*"]}
RESEARCH_PROJECTS=("研发中心-猫眼灯结构研发问题","研发中心-防爆标志灯研发问题","研发中心-吸顶灯软件联调问题","研发中心-应急照明控制模块研发","研发中心-通用灯具壳体模具研发")
RESEARCH_SAMPLES=[
 ("猫眼灯透镜卡扣装配干涉","试装时透镜卡扣与前壳加强筋干涉，扣合后右侧边缘翘起约0.4mm，需要结构确认是否调整筋位。",Priority.HIGH,RecordStatus.AI_REVIEW_REQUIRED,"结构设计问题","结构试装","猫眼灯"),
 ("防爆标志灯密封圈压缩量不足","防爆标志灯样机做淋雨前检查时，端盖密封圈压缩量不足，局部可见缝隙，需评估胶圈截面和端盖锁附力。",Priority.HIGH,RecordStatus.READY_TO_ASSIGN,"结构密封问题","样机验证","防爆标志灯"),
 ("吸顶灯驱动板上电偶发重启","吸顶灯驱动板在低温启动测试中偶发重启，复测发现电源纹波偏大，需软件与硬件一起确认启动策略。",Priority.URGENT,RecordStatus.IN_PROGRESS,"软件/硬件联调问题","可靠性测试","吸顶灯"),
 ("猫眼灯外壳缩水影响外观","猫眼灯后壳注塑后螺丝柱附近出现轻微缩水，喷涂后仍可见，需模具评估浇口和保压参数。",Priority.MEDIUM,RecordStatus.ASSIGNED,"模具工艺问题","模具试模","猫眼灯"),
 ("防爆标志灯蓝牙配置连接不稳定","工程样机用手机配置蓝牙参数时偶发断连，日志显示握手超时，需软件排查重连机制。",Priority.HIGH,RecordStatus.RESOLVED,"软件通信问题","功能联调","防爆标志灯"),
 ("吸顶灯安装底盘孔位偏差","吸顶灯安装底盘与老款支架通用验证时孔位偏差约1.2mm，需结构确认是否兼容旧支架。",Priority.MEDIUM,RecordStatus.AI_REVIEW_REQUIRED,"结构兼容问题","设计评审","吸顶灯"),
 ("猫眼灯导光柱亮斑不均","猫眼灯状态指示导光柱点亮后局部亮斑明显，需结构和光学一起调整导光柱纹理。",Priority.MEDIUM,RecordStatus.CLOSED,"光学结构问题","样机测试","猫眼灯"),
 ("防爆标志灯端子压接拉力不足","产前样件抽检发现防爆标志灯输入端子压接拉力不足，需确认端子规格和压接工装。",Priority.HIGH,RecordStatus.IN_PROGRESS,"工艺验证问题","小批试产","防爆标志灯"),
 ("吸顶灯 OTA 升级后参数丢失","吸顶灯控制板 OTA 升级后部分亮度参数恢复默认值，需软件确认配置迁移逻辑。",Priority.HIGH,RecordStatus.READY_TO_ASSIGN,"软件升级问题","软件测试","吸顶灯"),
 ("通用壳体模具顶出痕明显","通用灯具壳体第二次试模后顶出痕仍明显，影响外观件验收，需模具工程师调整顶针方案。",Priority.MEDIUM,RecordStatus.DRAFT,"模具外观问题","模具试模","通用灯具壳体")]

def refresh_research_demo_data(db):
 users=list(db.scalars(select(User).order_by(User.created_at)).all())
 if not users: return
 projects=list(db.scalars(select(Project).where(Project.code.in_([f"P{i+1:03}" for i in range(len(RESEARCH_PROJECTS))])).order_by(Project.code)).all())
 for project,name in zip(projects,RESEARCH_PROJECTS):
  project.name=name
 old_titles=("3号楼集中电源通信异常","烟感安装位置确认","应急照明灯不亮","图纸与现场不一致","集中电源电池故障","消防主机报故障代码E23","灯具安装高度不符合要求","端子压接不良","驱动模块测试异常","采集网关离线")
 records=list(db.scalars(select(Record).where(Record.title.in_(old_titles)).order_by(Record.created_at)).all())
 for i,record in enumerate(records[:len(RESEARCH_SAMPLES)]):
  title,content,priority,status,category,stage,product=RESEARCH_SAMPLES[i]
  record.title=title; record.content=content; record.summary=content; record.priority=priority; record.status=status
  record.category_snapshot=category; record.stage_snapshot=stage; record.product_snapshot=product
  if i < len(projects): record.project_id=projects[i%len(projects)].id
  analysis=db.scalar(select(AIAnalysis).where(AIAnalysis.record_id==record.id).order_by(AIAnalysis.created_at.desc()).limit(1))
  if analysis:
   analysis.result_json={"title":title,"summary":content,"category":{"name":category},"stage":{"name":stage},"product":{"name":product},"priority":priority.value,"suggested_department":{"name":"研发部"},"confidence":0.9}
   analysis.confidence=.9; analysis.reasoning_summary="研发中心演示数据"
 for notice in db.scalars(select(Notification).where(Notification.type=="RISK")).all():
  notice.title="研发项目风险提醒"; notice.content="研发中心存在未闭环高优先级产品开发问题，建议优先跟进结构、软件与模具协同事项"
 for template in db.scalars(select(ExportTemplate)).all():
  if "项目记录" in template.name:
   template.name=template.name.replace("项目记录","研发记录")
 db.commit()

def ensure_phase2_seed(db):
 if db.scalar(select(Notification).limit(1)): return
 admin=db.scalar(select(User).where(User.username=="admin")); manager=db.scalar(select(User).where(User.username=="manager")); records=list(db.scalars(select(Record).order_by(Record.created_at).limit(3)).all())
 if not admin or not records: return
 db.add_all([Notification(user_id=admin.id,type="AI_REVIEW",title="AI 分析待确认",content=f"《{records[0].title}》需要人工确认",related_record_id=records[0].id),Notification(user_id=admin.id,type="RISK",title="研发项目风险提醒",content="研发中心存在未闭环高优先级产品开发问题",related_record_id=records[-1].id),Notification(user_id=admin.id,type="SYSTEM",title="第二阶段功能已启用",content="项目管理、通知中心和协作处理功能已上线")])
 if manager: db.add(RecordComment(record_id=records[-1].id,author_id=manager.id,content="请在今天下班前反馈检查结果。",kind="COMMENT"))
 db.commit()
def ensure_phase3_seed(db):
 if db.scalar(select(ExportTemplate).limit(1)): return
 admin=db.scalar(select(User).where(User.username=="admin"))
 db.add(ExportTemplate(name="标准研发记录模板",format="XLSX",fields_json=DEFAULT_FIELDS,is_default=True,is_active=True,creator_id=admin.id if admin else None)); db.commit()
def seed():
 Base.metadata.create_all(engine); db=SessionLocal()
 try:
  if db.scalar(select(User).limit(1)): ensure_phase2_seed(db); ensure_phase3_seed(db); refresh_research_demo_data(db); return
  perm_objs={c:Permission(code=c,name=c) for c in sorted({p for ps in PERMISSIONS.values() for p in ps})}; db.add_all(perm_objs.values()); db.flush()
  roles={code:Role(code=code,name={RoleCode.ENGINEER:"工程师（员工）",RoleCode.PROJECT_MANAGER:"主管（项目经理）",RoleCode.DEPARTMENT_HEAD:"主管（项目经理）",RoleCode.SUPER_ADMIN:"管理员"}[code],permissions=[perm_objs[p] for p in perms]) for code,perms in PERMISSIONS.items()}; db.add_all(roles.values())
  depts=[Department(name=n) for n in ("研发部","产品部","模具部")]; db.add_all(depts); db.flush()
  users=[User(username=u,name=n,mobile=m,password_hash=hash_password("Passw0rd!"),department_id=d.id,roles=[roles[r]]) for u,n,m,d,r in [("engineer","陈工","13800005678",depts[0],RoleCode.ENGINEER),("manager","李工","13900002345",depts[0],RoleCode.PROJECT_MANAGER),("head","王工","13700006789",depts[0],RoleCode.DEPARTMENT_HEAD),("admin","赵主管","13600008888",depts[0],RoleCode.SUPER_ADMIN)]]; db.add_all(users); db.flush()
  projects=[Project(name=n,code=f"P{i+1:03}",manager_id=users[1].id,department_id=depts[0].id,members=users[:3]) for i,n in enumerate(RESEARCH_PROJECTS)]
  db.add_all(projects); db.flush()
  samples=RESEARCH_SAMPLES
  now=datetime.now(timezone.utc)
  seeded_records=[]
  for i,(title,content,priority,status,category,stage,product) in enumerate(samples):
   r=Record(creator_id=users[i%2].id,project_id=projects[i%5].id,title=title,content=content,summary=content,status=status,priority=priority,category_snapshot=category,stage_snapshot=stage,product_snapshot=product); db.add(r); db.flush(); db.add(RecordEvent(record_id=r.id,actor_id=users[0].id,event_type="SEEDED",after_json={"status":status.value}))
   seeded_records.append(r)
   if status!=RecordStatus.DRAFT: db.add(AIAnalysis(record_id=r.id,result_json={"title":title,"summary":content,"category":{"name":category},"stage":{"name":stage},"product":{"name":product},"priority":priority.value,"suggested_department":{"name":"研发部"},"confidence":.9},confidence=.9,provider="mock",model="mock-structured-v1",prompt_version="v1",reasoning_summary="研发中心种子数据"))
   if status in {RecordStatus.ASSIGNED,RecordStatus.IN_PROGRESS,RecordStatus.RESOLVED}: db.add(RecordTask(record_id=r.id,assignee_id=users[0].id,department_id=depts[0].id,due_at=now+timedelta(days=3)))
  db.add(RecordComment(record_id=seeded_records[2].id,author_id=users[1].id,content="请在今天下班前反馈检查结果。",kind="COMMENT"))
  db.add_all([Notification(user_id=users[3].id,type="AI_REVIEW",title="AI 分析待确认",content=f"《{seeded_records[0].title}》需要人工确认",related_record_id=seeded_records[0].id),Notification(user_id=users[3].id,type="RISK",title="研发项目风险提醒",content="研发中心存在未闭环高优先级产品开发问题，建议优先跟进结构、软件与模具协同事项",related_record_id=seeded_records[2].id),Notification(user_id=users[3].id,type="SYSTEM",title="第二阶段功能已启用",content="项目管理、通知中心和协作处理功能已上线")])
  db.add(ExportTemplate(name="标准研发记录模板",format="XLSX",fields_json=DEFAULT_FIELDS,is_default=True,is_active=True,creator_id=users[3].id))
  db.commit(); print("Seed complete: admin/manager/engineer/head, password Passw0rd!")
 finally: db.close()
if __name__=="__main__": seed()
