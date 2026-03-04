import os
import json
import base64
import requests
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

# 👇 ĐIỀN 2 MÃ API KEY CỦA BẠN VÀO ĐÂY 👇
GEMINI_API_KEY = "AIzaSyDux4LOm7o_HoaR_sSvaalt0h00VHCf6f0"
IMGBB_API_KEY = "f7a0aebb9ff6406830a228c03e7ebf9f"

client = genai.Client(api_key=GEMINI_API_KEY)
DB_FILE = "database.json"

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
    return []

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)

class ScriptData(BaseModel): text: str
class StatusData(BaseModel): id: int; status: str

@app.get("/scenes")
def get_scenes():
    return {"scenes": load_db()}

@app.post("/analyze")
def analyze_script(data: ScriptData):
    print("AI đang bóc tách kịch bản...")
    prompt_text = f"Đóng vai trợ lý đạo diễn. Bóc tách kịch bản thành shot list. Bắt đầu bằng 'Cảnh [Số]:'.\nKịch bản:\n{data.text}"
    response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt_text)
    
    lines = [line.strip() for line in response.text.split('\n') if line.strip() != ""]
    scenes = load_db()
    start_id = len(scenes)
    
    for i, line in enumerate(lines):
        scenes.append({"id": start_id + i, "content": line, "status": "⏳ Chưa quay", "image": None})
        
    save_db(scenes)
    return {"status": "Thành công", "scenes": scenes}

# 🚀 ĐƯỜNG ỐNG ĐẨY ẢNH LÊN ĐÁM MÂY IMGBB
@app.post("/upload_image/{scene_id}")
async def upload_image(scene_id: int, file: UploadFile = File(...)):
    print(f"Đang đẩy ảnh lên Đám mây (ImgBB)...")
    
    # 1. Đọc ảnh và mã hóa
    contents = await file.read()
    encoded_image = base64.b64encode(contents).decode("utf-8")
    
    # 2. Gửi sang server của ImgBB
    url = "https://api.imgbb.com/1/upload"
    payload = {
        "key": IMGBB_API_KEY,
        "image": encoded_image,
    }
    res = requests.post(url, data=payload)
    res_data = res.json()
    
    # 3. Lấy link ảnh lưu vào hệ thống
    if res_data.get("success"):
        image_url = res_data["data"]["url"] 
        scenes = load_db()
        for scene in scenes:
            if scene["id"] == scene_id:
                scene["image"] = image_url
        save_db(scenes)
        return {"image_url": image_url}
    else:
        return {"error": "Lỗi tải ảnh lên mạng"}

@app.post("/update_status")
def update_status(data: StatusData):
    scenes = load_db()
    for scene in scenes:
        if scene["id"] == data.id: scene["status"] = data.status
    save_db(scenes)
    return {"status": "Thành công"}