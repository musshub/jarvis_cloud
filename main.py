from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid
from ai_brain import JarvisBrain
from memory_rules import ensure_user_memory, add_memory_rule
from location_tools import describe_location, nearest_petrol_pumps

app = FastAPI(title="Shub Jarvis Cloud Brain", version="1.0.0")
brain = None

def get_brain():
    global brain
    if brain is None:
        brain = JarvisBrain()
    return brain
WORKERS: Dict[str, Dict[str, Any]] = {}
TASKS: Dict[str, Dict[str, Any]] = {}
PROJECTS: Dict[str, Dict[str, Any]] = {}
MEMORY: Dict[str, Dict[str, Any]] = {}

def now_iso() -> str: return datetime.utcnow().isoformat() + "Z"

class WorkerRegisterRequest(BaseModel):
    user_id: str = "demo_user"; worker_id: Optional[str]=None; name: str="Shub Jarvis PC Worker"; device_name: str="Windows PC"; os: str="Windows"
class CommandRequest(BaseModel):
    user_id: str="demo_user"; command: str; worker_id: Optional[str]=None
class AICommandRequest(BaseModel):
    user_id: str="demo_user"; command: str; worker_id: Optional[str]=None; lat: Optional[float]=None; lon: Optional[float]=None; auto_execute: bool=True
class WorkerResultRequest(BaseModel):
    worker_id: str; task_id: str; ok: bool; result: Dict[str, Any]=Field(default_factory=dict); error: Optional[str]=None
class ProjectSaveRequest(BaseModel):
    user_id: str="demo_user"; project_id: str; name: str; root_path: str; project_type: str="flutter"
class CodeContextFile(BaseModel):
    path: str; score: int=0; content: str
class GenerateFileUpdatesRequest(BaseModel):
    user_id: str="demo_user"; command: str; project_hint: str="unknown"; project_path: str; files: List[CodeContextFile]; analyze_output: Dict[str, Any]=Field(default_factory=dict)
class GenerateRepairUpdatesRequest(BaseModel):
    user_id: str="demo_user"; command: str; project_hint: str="unknown"; project_path: str; files: List[CodeContextFile]; analyze_output: Dict[str, Any]=Field(default_factory=dict); previous_updates: List[Dict[str, Any]]=Field(default_factory=list); attempt: int=1
class ScreenshotVisionRequest(BaseModel):
    user_id: str="demo_user"; command: str; image_base64: str; image_mime: str="image/png"

def extract_project_hint(command: str) -> str:
    text=command.lower(); known=["nirmansutra","gallery_pro","gallerypro","gallery","agrisutra","cad","operator","shub ai"]
    for item in known:
        if item in text: return item.replace(" ","_").replace("gallerypro","gallery_pro").replace("gallery","gallery_pro")
    return "unknown"
def extract_password(command: str) -> Optional[str]:
    text=command.lower()
    if "password" not in text: return None
    return text.split("password",1)[1].strip().split(" ")[0].strip() or None

def choose_worker(user_id: str, requested_worker_id: Optional[str]) -> Optional[str]:
    if requested_worker_id and requested_worker_id in WORKERS: return requested_worker_id
    for wid,w in WORKERS.items():
        if w.get("user_id")==user_id: return wid
    return None

def create_worker_task_from_ai(req: AICommandRequest, ai: Dict[str, Any]) -> Dict[str, Any]:
    worker_id=choose_worker(req.user_id, req.worker_id)
    if not worker_id: raise HTTPException(status_code=404, detail="No PC worker found. Start Jarvis PC Worker first.")
    task_id=f"task_{uuid.uuid4().hex[:12]}"
    task={"task_id":task_id,"user_id":req.user_id,"worker_id":worker_id,"command":req.command,"project_hint":ai.get("project_hint") or extract_project_hint(req.command),"password":extract_password(req.command),"type":ai.get("mode","pc_task"),"action":ai.get("action") or "chat","ai_plan":ai,"status":"pending","created_at":now_iso(),"started_at":None,"completed_at":None,"result":None,"error":None}
    TASKS[task_id]=task; return task

@app.get("/")
def root(): return {"ok":True,"name":"Shub Jarvis Cloud Brain","time":now_iso()}
@app.get("/health")
def health(): return {"ok":True,"workers":len(WORKERS),"tasks":len(TASKS),"projects":len(PROJECTS),"time":now_iso()}
@app.post("/worker/register")
def register_worker(req: WorkerRegisterRequest):
    wid=req.worker_id or f"worker_{uuid.uuid4().hex[:12]}"
    WORKERS[wid]={"worker_id":wid,"user_id":req.user_id,"name":req.name,"device_name":req.device_name,"os":req.os,"status":"online","last_seen":now_iso()}
    return {"ok":True,"worker_id":wid,"worker":WORKERS[wid]}
@app.get("/workers/{user_id}")
def list_workers(user_id: str): return {"ok":True,"workers":[w for w in WORKERS.values() if w.get("user_id")==user_id]}
@app.get("/worker/poll/{worker_id}")
def worker_poll(worker_id: str):
    if worker_id not in WORKERS: raise HTTPException(status_code=404, detail="Worker not registered.")
    WORKERS[worker_id]["last_seen"]=now_iso(); WORKERS[worker_id]["status"]="online"
    for task in TASKS.values():
        if task["worker_id"]==worker_id and task["status"]=="pending":
            task["status"]="running"; task["started_at"]=now_iso(); return {"ok":True,"has_task":True,"task":task}
    return {"ok":True,"has_task":False,"task":None}
@app.post("/worker/result")
def worker_result(req: WorkerResultRequest):
    task=TASKS.get(req.task_id)
    if not task: raise HTTPException(status_code=404, detail="Task not found.")
    task["status"]="completed" if req.ok else "failed"; task["completed_at"]=now_iso(); task["result"]=req.result; task["error"]=req.error
    if req.ok and task.get("action")=="search_project" and req.result.get("found_path"):
        mem=ensure_user_memory(MEMORY, task["user_id"]); ph=task.get("project_hint") or "unknown"
        if ph != "unknown": mem["projects"][ph]={"project_id":ph,"name":ph,"root_path":req.result["found_path"],"project_type":req.result.get("project_type","flutter"),"saved_at":now_iso()}
    return {"ok":True,"task":task}
@app.get("/tasks/{user_id}")
def list_tasks(user_id: str):
    items=[t for t in TASKS.values() if t.get("user_id")==user_id]; items.sort(key=lambda x:x.get("created_at",""), reverse=True); return {"ok":True,"tasks":items}
@app.get("/task/{task_id}")
def get_task(task_id: str):
    if task_id not in TASKS: raise HTTPException(status_code=404, detail="Task not found.")
    return {"ok":True,"task":TASKS[task_id]}
@app.get("/memory/{user_id}")
def get_memory(user_id: str): return {"ok":True,"memory":ensure_user_memory(MEMORY,user_id)}
@app.post("/projects")
def save_project(req: ProjectSaveRequest):
    mem=ensure_user_memory(MEMORY, req.user_id); PROJECTS[req.project_id]=req.model_dump(); mem["projects"][req.project_id]=PROJECTS[req.project_id]; return {"ok":True,"project":PROJECTS[req.project_id]}
@app.get("/projects/{user_id}")
def list_projects(user_id: str): return {"ok":True,"projects":ensure_user_memory(MEMORY,user_id).get("projects",{})}

@app.post("/ai/command")
def ai_command(req: AICommandRequest):
    memory=ensure_user_memory(MEMORY, req.user_id)
    loc={"lat":req.lat,"lon":req.lon} if req.lat is not None and req.lon is not None else None
    ai=get_brain().answer_or_plan(user_id=req.user_id, command=req.command, memory=memory, location=loc)
    mode=ai.get("mode"); action=ai.get("action")
    if mode=="memory_update":
        saved=add_memory_rule(MEMORY, req.user_id, ai.get("task_payload",{}).get("summary") or ai.get("answer") or req.command)
        return {"ok":True,"mode":"memory_update","answer":ai.get("answer") or "Memory updated.","memory_update":saved,"ai":ai}
    if mode=="location_task":
        if req.lat is None or req.lon is None: return {"ok":False,"mode":"location_task","answer":"Location permission chahiye. Mobile app se GPS allow karo.","ai":ai}
        if action=="nearest_petrol_pump":
            result=nearest_petrol_pumps(req.lat, req.lon); places=result.get("places",[])
            answer=f"Sabse najdeek petrol pump: {places[0].get('name')} lagbhag {places[0].get('distance_km')} km door hai." if places else "Nearby petrol pump nahi mila."
            return {"ok":result.get("ok",False),"mode":"location_task","answer":answer,"result":result,"ai":ai}
        result=describe_location(req.lat, req.lon); return {"ok":result.get("ok",False),"mode":"location_task","answer":f"Aap approx yahan ho: {result.get('display_name')}" if result.get("display_name") else "Location mil gayi, address resolve nahi hua.","result":result,"ai":ai}
    if mode=="answer": return {"ok":True,"mode":"answer","answer":ai.get("answer") or "Samjha, Shubham.","ai":ai}
    if mode in {"pc_task","phone_task"}:
        if ai.get("requires_confirmation") and action not in {"phone_whatsapp_draft"}:
            return {"ok":True,"mode":mode,"answer":ai.get("answer") or "This task needs confirmation.","requires_confirmation":True,"ai":ai}
        if not req.auto_execute: return {"ok":True,"mode":mode,"answer":ai.get("answer") or "Task planned.","requires_confirmation":False,"ai":ai}
        task=create_worker_task_from_ai(req, ai); return {"ok":True,"mode":"pc_task","answer":ai.get("answer") or "Task sent to PC worker.","task":task,"ai":ai}
    return {"ok":True,"mode":mode,"answer":ai.get("answer") or "Command understood.","ai":ai}

@app.post("/ai/generate-file-updates")
def generate_file_updates(req: GenerateFileUpdatesRequest):
    return get_brain().generate_file_updates(user_id=req.user_id, command=req.command, memory=ensure_user_memory(MEMORY, req.user_id), project_hint=req.project_hint, project_path=req.project_path, files=[f.model_dump() for f in req.files], analyze_output=req.analyze_output)
@app.post("/ai/generate-repair-updates")
def generate_repair_updates(req: GenerateRepairUpdatesRequest):
    return get_brain().generate_repair_updates(user_id=req.user_id, command=req.command, memory=ensure_user_memory(MEMORY, req.user_id), project_hint=req.project_hint, project_path=req.project_path, files=[f.model_dump() for f in req.files], analyze_output=req.analyze_output, previous_updates=req.previous_updates, attempt=req.attempt)
@app.post("/ai/analyze-screenshot")
def analyze_screenshot_with_ai(req: ScreenshotVisionRequest): return get_brain().analyze_phone_screenshot(command=req.command, image_base64=req.image_base64, image_mime=req.image_mime)
@app.get("/ping")
def ping():
    return {"ok": True, "message": "pong"}