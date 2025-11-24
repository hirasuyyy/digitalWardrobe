from fastapi.responses import HTMLResponse
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1"

import uuid
import sqlite3
import random
import json
import requests
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps
from io import BytesIO
import google.generativeai as genai
import cloudinary
import cloudinary.uploader
import cloudinary.api

# --- CLOUDINARY AYARLARI (Burayı Doldur) ---
cloudinary.config( 
  cloud_name = "dv5fndevj", 
  api_key = "412538943184697", 
  api_secret = "**********" 
)
# --- API KEYS ---
GEMINI_API_KEY = "AIzaSyBKWsm-9gyNslpXWKdgFAZs7I9zxX4asLI" 
REMOVE_BG_API_KEY = "FvDk6BLEEFbJVpJLtvWj9gjk" 

GEMINI_ACTIVE = False
try:
    if "SENIN" not in GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        GEMINI_ACTIVE = True
        print("✅ Gemini Active")
except: pass

REMBG_AVAILABLE = False
try:
    from rembg import remove, new_session
    session = new_session("u2net_human_seg") 
    REMBG_AVAILABLE = True
    print("✅ Rembg Active")
except: pass

UPLOAD_DIR = "uploads"
DB_NAME = "closet_master.db"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- AFFILIATE DB ---
AFFILIATE_DB = {
    "female": [
        {"id": "ad_f1", "category": "top", "tags": "dress red elegant gala", "img": "https://images.pexels.com/photos/985635/pexels-photo-985635.jpeg?auto=compress&cs=tinysrgb&w=600", "link": "#", "is_ad": True, "price": "45000", "tier": "high"},
        {"id": "ad_f2", "category": "shoes", "tags": "heels luxury", "img": "https://images.pexels.com/photos/33853/shoes-heels-black-women.jpg?auto=compress&cs=tinysrgb&w=600", "link": "#", "is_ad": True, "price": "12000", "tier": "high"},
        {"id": "ad_f3", "category": "top", "tags": "puffer ski winter white", "img": "https://images.pexels.com/photos/7200795/pexels-photo-7200795.jpeg?auto=compress&cs=tinysrgb&w=600", "link": "#", "is_ad": True, "price": "8000", "tier": "mid"},
        {"id": "ad_f4", "category": "top", "tags": "basic white tee", "img": "https://images.pexels.com/photos/4066290/pexels-photo-4066290.jpeg?auto=compress&cs=tinysrgb&w=600", "link": "#", "is_ad": True, "price": "400", "tier": "low"},
    ],
    "male": [
        {"id": "ad_m1", "category": "top", "tags": "suit tuxedo black gala", "img": "https://images.pexels.com/photos/1043474/pexels-photo-1043474.jpeg?auto=compress&cs=tinysrgb&w=600", "link": "#", "is_ad": True, "price": "35000", "tier": "high"},
        {"id": "ad_m2", "category": "top", "tags": "hoodie streetwear", "img": "https://images.pexels.com/photos/6311392/pexels-photo-6311392.jpeg?auto=compress&cs=tinysrgb&w=600", "link": "#", "is_ad": True, "price": "1200", "tier": "mid"},
    ]
}

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS items (id TEXT PRIMARY KEY, filename TEXT, category TEXT, tags TEXT, gender TEXT, price REAL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()
init_db()

app = FastAPI()
@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("index.html", "r") as f:
        return f.read()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# --- FULL SCENARIO LOGIC ---
STYLE_LOGIC = {
    # NIGHT
    "night_cocktail": ["black", "midi", "silk", "heels", "elegant", "clutch", "suit"],
    "night_party": ["sparkle", "sequin", "mini", "silver", "gold", "leather", "boots", "cool"],
    "night_dinner": ["red", "black", "velvet", "romantic", "lace", "dress", "shirt"],
    "night_lounge": ["satin", "slip", "minimal", "mule", "chic", "trousers", "polo"],
    "night_concert": ["leather", "boots", "corset", "denim", "band", "cool", "sneaker"],
    "gala_wedding": ["gown", "elegant", "luxury", "crystal", "long", "tuxedo", "bow tie"],

    # SPORT
    "sport_tennis": ["white", "skirt", "polo", "cap", "sneaker", "preppy", "shorts"],
    "sport_yoga": ["leggings", "bra", "tight", "comfy", "pastel", "mat"],
    "sport_gym": ["black", "shorts", "hoodie", "runner", "tech", "gym"],
    "sport_run": ["tracksuit", "sneaker", "windbreaker", "leggings", "cap", "running"],
    "sport_hike": ["boots", "cargo", "fleece", "backpack", "outdoor"],
    "ski": ["puffer", "jacket", "boots", "winter", "scarf", "beanie", "gloves"],

    # SOCIAL
    "social_coffee": ["denim", "basic", "trench", "loafers", "casual", "beige", "jeans"],
    "social_brunch": ["floral", "colorful", "dress", "sandal", "cute", "pink", "linen"],
    "social_art": ["minimal", "black", "white", "architectural", "trousers", "blazer", "turtleneck"],
    "social_library": ["knit", "cardigan", "glasses", "loafer", "skirt", "preppy", "sweater"],
    "school_casual": ["backpack", "hoodie", "jeans", "sneaker", "casual", "comfy", "denim"],
    "social_office": ["blazer", "shirt", "trousers", "smart", "watch", "loafers", "black"],

    # TRAVEL
    "travel_city": ["comfortable", "layer", "jeans", "boots", "coat", "bag", "walking"],
    "travel_beach": ["linen", "white", "sandal", "shorts", "hat", "swim", "sunglasses"],
    "travel_summer": ["bikini", "swim", "resort", "colorful", "shorts", "hat"],
    "travel_culture": ["walking", "backpack", "comfortable", "modest", "cotton"],
    
    # VIBES
    "dark_feminine": ["black", "lace", "leather", "corset", "dark"],
    "old_money": ["navy", "cream", "tweed", "pearl", "polo", "cashmere"],
    "clean_girl": ["white", "beige", "slick", "gold", "basic"],
    "streetwear": ["baggy", "hoodie", "sneaker", "cargo", "oversize"],
    "coquette": ["pink", "bow", "ribbon", "lace"],
    "office_siren": ["grey", "glasses", "tight", "skirt", "office"]
}

@app.post("/analyze")
async def analyze_image(file: UploadFile = File(...)):
    if not GEMINI_ACTIVE: return {"error": "No API Key"}
    try:
        contents = await file.read()
        image = Image.open(BytesIO(contents))
        prompt = """Analyze this fashion item. Return JSON with:
        1. 'category': [top, bottom, shoes, bag, jewelry, hat, gloves, socks, coat]
        2. 'tags': comma separated keywords (e.g. "black, leather, sexy, winter")
        Only return JSON."""
        response = model.generate_content([prompt, image])
        text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except: return {"category": "top", "tags": "basic"}

@app.post("/upload")
async def upload_item(file: UploadFile = File(...), category: str = Form(...), tags: str = Form(...), gender: str = Form(...), price: float = Form(...)):
    try:
        contents = await file.read()
        try: import pillow_heif; pillow_heif.register_heif_opener(); 
        except: pass
        input_image = Image.open(BytesIO(contents)).convert("RGBA")
        input_image = ImageOps.exif_transpose(input_image)
        
        bg_removed = False
        if "SENIN" not in REMOVE_BG_API_KEY:
            try:
                file.file.seek(0)
                res = requests.post('https://api.remove.bg/v1.0/removebg', files={'image_file': file.file}, data={'size':'auto'}, headers={'X-Api-Key': REMOVE_BG_API_KEY})
                if res.status_code == 200:
                    input_image = Image.open(BytesIO(res.content)).convert("RGBA")
                    bg_removed = True
            except: pass

        if not bg_removed and REMBG_AVAILABLE:
            try: input_image = remove(input_image, session=session, alpha_matting=True)
            except: pass

        unique_name = f"{uuid.uuid4()}.png"
        file_path = os.path.join(UPLOAD_DIR, unique_name)
        input_image.save(file_path, format="PNG")
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        item_id = str(uuid.uuid4())
        c.execute("INSERT INTO items (id, filename, category, tags, gender, price) VALUES (?, ?, ?, ?, ?, ?)", 
                  (item_id, unique_name, category, tags, gender, price))
        conn.commit()
        conn.close()
        return {"status": "saved"}
    except Exception as e: print(e); raise e

@app.post("/update/{item_id}")
async def update_item(item_id: str, category: str = Form(...), tags: str = Form(...), price: float = Form(...)):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE items SET category=?, tags=?, price=? WHERE id=?", (category, tags, price, item_id))
    conn.commit()
    conn.close()
    return {"status": "updated"}

@app.delete("/items/{item_id}")
def delete_item(item_id: str):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted"}

@app.get("/wardrobe")
def get_all_items(gender: str = "female"):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM items WHERE gender = ? ORDER BY created_at DESC", (gender,))
    items = [dict(row) for row in c.fetchall()]
    conn.close()
    for item in items:
        item['url'] = f"http://127.0.0.1:8000/uploads/{item['filename']}"
        item['is_ad'] = False
    return items

@app.get("/generate-outfit/{style}")
def generate_outfit(style: str, gender: str = "female", budget: str = "mid", season: str = "summer", weather: str = "sunny"):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM items WHERE gender = ?", (gender,))
    user_items = [dict(row) for row in c.fetchall()]
    conn.close()
    
    for item in user_items:
        item['url'] = f"http://127.0.0.1:8000/uploads/{item['filename']}"
        item['is_ad'] = False

    target_tags = STYLE_LOGIC.get(style, [])
    suggestions = []
    cats = ["top", "bottom", "shoes", "bag", "jewelry", "hat", "gloves", "socks", "coat"]
    unique_hashes = set()
    
    for _ in range(15): 
        outfit = {}
        has_main = False
        for cat in cats:
            candidates = []
            # 1. Dolap + HAVA DURUMU
            for item in user_items:
                if item["category"] == cat:
                    score = 0
                    tags = item["tags"].lower()
                    for t in target_tags: 
                        if t in tags: score += 50
                    
                    if season == "winter":
                        if "coat" in tags or "jacket" in tags or "boots" in tags: score += 100
                        if "sandal" in tags or "linen" in tags: score -= 500
                    if weather == "rainy":
                        if "suede" in tags: score -= 500
                    
                    score += random.randint(0, 40)
                    if score > 0: candidates.append({"data": item, "score": score})
            
            # 2. Reklam
            if (not candidates or random.random() < 0.3) and gender in AFFILIATE_DB:
                for ad in AFFILIATE_DB[gender]:
                    if ad["category"] == cat:
                        if budget == "low" and ad["tier"] == "high": continue
                        if budget == "high" and ad["tier"] == "low": continue
                        candidates.append({"data": ad, "score": 70})

            if candidates:
                candidates.sort(key=lambda x: x["score"], reverse=True)
                chosen = random.choice(candidates[:min(3, len(candidates))])["data"]
                outfit[cat] = {
                    "img": chosen.get('url', chosen.get('img')),
                    "id": chosen.get('id', 'ad'),
                    "is_ad": chosen.get('is_ad', False),
                    "price": chosen.get('price', ''),
                    "link": chosen.get('link', '')
                }
                if cat in ["top", "bottom", "shoes"]: has_main = True
        
        if has_main:
            outfit_hash = str(outfit.get('top',{}).get('id')) + str(outfit.get('bottom',{}).get('id'))
            if outfit_hash not in unique_hashes:
                suggestions.append(outfit)
                unique_hashes.add(outfit_hash)
                
        if len(suggestions) >= 10: break

    return {"title": style.replace("_", " ").upper(), "outfits": suggestions}