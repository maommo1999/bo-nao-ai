import os
import json
import base64
import requests
import time
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 👇 ĐIỀN LẠI 2 MÃ API KEY CỦA BẠN VÀO ĐÂY 👇
GEMINI_API_KEY = "AIzaSyDux4LOm7o_HoaR_sSvaalt0h00VHCf6f0"
IMGBB_API_KEY = "f7a0aebb9ff6406830a228c03e7ebf9f"

client = genai.Client(api_key=GEMINI_API_KEY)
DB_FILE = "database.json"

# Cấu trúc DB mới: { "id_du_an": { "name": "Tên phim", "scenes": [...] } }
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
    return {}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)

class ProjectData(BaseModel): name: str
class ScriptData(BaseModel): text: str
class StatusData(BaseModel): id: int; status: str

# --- QUẢN LÝ DỰ ÁN ---
@app.get("/projects")
def get_projects():
    db = load_db()
    # Trả về danh sách các dự án (chỉ lấy id và tên)
    projects_list = [{"id": k, "name": v["name"]} for k, v in db.items()]
    return {"projects": projects_list}

@app.post("/create_project")
def create_project(data: ProjectData):
    db = load_db()
    project_id = str(int(time.time())) # Tạo ID ngẫu nhiên bằng thời gian
    db[project_id] = {"name": data.name, "scenes": []}
    save_db(db)
    return {"id": project_id, "name": data.name}

# --- QUẢN LÝ KỊCH BẢN THEO DỰ ÁN ---
@app.get("/scenes/{project_id}")
def get_scenes(project_id: str):
    db = load_db()
    if project_id in db:
        return {"scenes": db[project_id]["scenes"]}
    return {"scenes": []}

@app.post("/analyze/{project_id}")
def analyze_script(project_id: str, data: ScriptData):
    print(f"AI đang bóc tách kịch bản cho dự án {project_id}...")
    prompt_text = f"Đóng vai trợ lý đạo diễn. Bóc tách kịch bản thành shot list. Bắt đầu bằng 'Cảnh [Số]:'.\nKịch bản:\n{data.text}"
    response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt_text)
    
    lines = [line.strip() for line in response.text.split('\n') if line.strip() != ""]
    db = load_db()
    
    if project_id in db:
        start_id = len(db[project_id]["scenes"])
        for i, line in enumerate(lines):
            db[project_id]["scenes"].append({"id": start_id + i, "content": line, "status": "⏳ Chưa quay", "image": None})
        save_db(db)
        return {"status": "Thành công", "scenes": db[project_id]["scenes"]}
    return {"error": "Không tìm thấy dự án"}

@app.post("/upload_image/{project_id}/{scene_id}")
async def upload_image(project_id: str, scene_id: int, file: UploadFile = File(...)):
    contents = await file.read()
    encoded_image = base64.b64encode(contents).decode("utf-8")
    
    url = "https://api.imgbb.com/1/upload"
    res = requests.post(url, data={"key": IMGBB_API_KEY, "image": encoded_image})
    res_data = res.json()
    
    if res_data.get("success"):
        image_url = res_data["data"]["url"] 
        db = load_db()
        if project_id in db:
            for scene in db[project_id]["scenes"]:
                if scene["id"] == scene_id:
                    scene["image"] = image_url
            save_db(db)
        return {"image_url": image_url}
    return {"error": "Lỗi tải ảnh lên mạng"}

@app.post("/update_status/{project_id}")
def update_status(project_id: str, data: StatusData):
    db = load_db()
    if project_id in db:
        for scene in db[project_id]["scenes"]:
            if scene["id"] == data.id: 
                scene["status"] = data.status
        save_db(db)
    return {"status": "Thành công"}