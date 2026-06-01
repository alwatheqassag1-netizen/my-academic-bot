# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys
import io
import re
import json
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests
import telebot
from telebot.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson.objectid import ObjectId
from bson import json_util
from flask import Flask, request, redirect

# ==========================================
# 1. الإعدادات، التوكنات، والسجلات (مدمجة مباشرة)
# ==========================================

if sys.version_info >= (3, 0):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# 🔑 التوكنات الخاصة بك مدمجة كقيم افتراضية قوية
API_TOKEN = os.getenv("API_TOKEN", "7524289470:AAGkeX96s1s6saxGP3uy14MN9it19nKn10A").strip()
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://Alwatheq:alwatheq73@cluster0.ft0mdkt.mongodb.net/?appName=Cluster0").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSy").strip()
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "6842543527"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://academic-bot-iyuy.onrender.com").strip()
PORT = int(os.getenv("PORT", "5000"))

START_TIME = datetime.utcnow()

# ==========================================
# 2. النصوص الافتراضية الرسمية
# ==========================================

DEFAULT_START_TEXT = (
    "🌟 أهلاً وسهلاً بك يا {first_name} في المنصة الأكاديمية الرسمية لقسم الذكاء الاصطناعي وعلوم البيانات (AI & DS) 🎓\n\n"
    "مرحباً بك في بوابتك التعليمية الرقمية الموحدة. يمكنك من خلالها الوصول إلى المحاضرات، الملخصات، النماذج، والمراجع المعتمدة بشكل منظم وآمن.\n\n"
    "👇 الرجاء اختيار القسم أو الخدمة المطلوبة من القائمة أدناه:"
)
DEFAULT_INFO_TEXT = (
    "🤖 المنصة الأكاديمية الذكية - قسم الذكاء الاصطناعي وعلوم البيانات\n\n"
    "نظام متكامل يهدف إلى أتمتة الوصول للموارد التعليمية، وتسهيل رحلة الطالب الأكاديمية عبر أدوات برمجية حديثة ومنظمة."
)
DEFAULT_DEV_TEXT = (
    "✉️ التواصل مع إدارة المنصة\n\n"
    "نرحب باستفساراتكم، ملاحظاتكم، وبلاغاتكم حول المقررات أو الملفات.\n"
    "الأزرار بالأسفل تفتح جهة التواصل الرسمية مباشرة."
)
DEFAULT_GUIDE_TEXT = (
    "📖 دليل القسم\n\n"
    "هذه المنصة وُضعت لتجميع المواد الأكاديمية بشكل منظم، مع تسهيل الوصول إلى المستويات، المقررات، الملفات، والمحتوى المساند."
)
DEFAULT_SCI_TEXT = (
    "بسم الله الرحمن الرحيم\n\n"
    "تتقدم إدارة الدفعة بخالص الشكر والتقدير لأعضاء اللجنة العلمية على جهودهم الكبيرة المبذولة في ترتيب وتنسيق المصادر الدراسية.\n\n"
    "🎓 إدارة الدفعة:\n"
    "• مندوب الدفعة: الواثق بالله عساج\n"
    "• مندوبة الدفعة: شهد المشهور\n"
    "• نائب الدفعة: ليث آل مرزوق\n"
    "• نائبة الدفعة: آية أمين\n\n"
    "🧠 رئيس اللجنة العلمية: عبد القوي أحمد\n\n"
    "📚 أعضاء اللجنة العلمية حسب المقررات:\n"
    "🔸 التكامل: أبرار عدنان، مجد محمود، البراء خسن\n"
    "🔸 الإسلامية: أحلام طلال\n"
    "🔸 البرمجة: جلال عبد الناصر، نهى رفيق، مرام نبيل\n"
    "🔸 الإنجليزي: عمرو خالد، مرام رأفت\n"
    "🔸 مقدمة علوم البيانات: مودة أسامة، محمد جميل\n"
    "🔸 رياضيات متقطعة: عمر عبد الحبيب، حنان عبده\n\n"
    "✨ ختاماً، شكراً لكل من ساهم بوقته وجهده في خدمة دفعتهم."
)
DEFAULT_EMERGENCY_FLAGS = {"ai": False, "upload": False, "search": False, "ads": False, "all": False}

# ==========================================
# 3. الاتصال بقاعدة البيانات MongoDB
# ==========================================

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=7000)
db = client["academic_bot_db"]

files_col = db["uploaded_files"]
folders_col = db["dynamic_folders"]
users_col = db["bot_users"]
admins_col = db["admins_list"]
settings_col = db["bot_settings"]
hashtags_col = db["dynamic_hashtags"]
auth_groups_col = db["auth_groups"]
alerts_col = db["course_alerts"]
kb_col = db["knowledge_base"]
ai_usage_col = db["ai_usage"]
reminders_col = db["personal_reminders"]
action_logs_col = db["action_logs"]
ratings_col = db["file_ratings"]

try:
    files_col.create_index([("menu_path", ASCENDING), ("sort_order", ASCENDING), ("name", ASCENDING)])
    files_col.create_index([("file_id", ASCENDING)])
    files_col.create_index([("name", ASCENDING)])
    folders_col.create_index([("parent_path", ASCENDING), ("sort_order", ASCENDING), ("folder_name", ASCENDING)])
    users_col.create_index([("chat_id", ASCENDING)], unique=True)
    admins_col.create_index([("id", ASCENDING)], unique=True)
    settings_col.create_index([("_id", ASCENDING)], unique=True)
    ratings_col.create_index([("file_id", ASCENDING), ("user_id", ASCENDING)], unique=True)
    kb_col.create_index([("question", ASCENDING)])
    logging.info("Database Connected Flawlessly!")
except Exception as e:
    logging.warning(f"Index setup warning: {e}")

BOT_GENERAL_SETTINGS_ID = "bot_general_settings"
ACADEMIC_STRUCTURE_ID = "academic_structure"
ACADEMIC_STRUCTURE_DEFAULT = {
    "🌱 مستوى أول": {
        "📅 ترم أول": {},
        "📅 ترم ثاني": {
            "🕌 ثقافة اسلامية 🕌": {"📁 محاضرات وملخصات": {}, "📝 نماذج اختبارات": {}},
            "🟢 لغة عربية 102 🟢": {"📁 محاضرات وملخصات": {}, "📝 نماذج اختبارات": {}},
            "🔠 English language 102 🔠": {"📁 محاضرات وملخصات": {}, "📝 نماذج اختبارات": {}},
            "📐 تفاضل وتكامل 102 📐": {"📂 محاضرات نظري": {}, "📐 محاضرات تمارين": {}, "📝 نماذج اختبارات نظري": {}, "✍️ نماذج تمارين": {}, "📚 مراجع خارجية": {}},
            "📊 مقدمة في علوم البيانات 📊": {"👨‍🏫 محاضرات المهندس": {}, "📜 ملخص محاضرات": {}, "⚙️ محاضرات العملي": {}, "📝 نماذج اختبارات نظري": {}},
            "💻 برمجة حاسوب": {"📂 محاضرات نظري": {}, "🖥️ محاضرات العملي": {}, "📝 نماذج اختبارات": {}, "🚀 التمارين والمشاريع العملية": {}},
            "🗂️ رياضيات متقطعة": {"📂 محاضرات نظري": {}, "✏️ محاضرات تمارين": {}, "📝 نماذج اختبارات": {}, "📚 مراجع خارجية": {}},
            "اللجنة العلمية": {}
        }
    },
    "🌿 مستوى ثاني": {"📅 ترم أول": {}, "📅 ترم ثاني": {}},
    "☘️ مستوى ثالث": {"📅 ترم أول": {}, "📅 ترم ثاني": {}},
    "🌳 مستوى رابع": {"📅 ترم أول": {}, "📅 ترم ثاني": {}},
    "📖 دليل القسم": {},
}

def _ensure_bootstrap():
    if SUPER_ADMIN_ID:
        admins_col.update_one({"id": SUPER_ADMIN_ID}, {"$setOnInsert": {"id": SUPER_ADMIN_ID, "type": "super", "allowed_paths": [], "permissions": ["all"], "active": True}}, upsert=True)
    settings_col.update_one({"_id": BOT_GENERAL_SETTINGS_ID}, {"$setOnInsert": {"_id": BOT_GENERAL_SETTINGS_ID, "status": "active", "emergency_flags": DEFAULT_EMERGENCY_FLAGS, "start_text": DEFAULT_START_TEXT, "info_text": DEFAULT_INFO_TEXT, "dev_text": DEFAULT_DEV_TEXT, "guide_text": DEFAULT_GUIDE_TEXT, "sci_text": DEFAULT_SCI_TEXT, "last_announcement": "", "target_group_id": None}}, upsert=True)
    settings_col.update_one({"_id": ACADEMIC_STRUCTURE_ID}, {"$setOnInsert": {"_id": ACADEMIC_STRUCTURE_ID, "data": ACADEMIC_STRUCTURE_DEFAULT}}, upsert=True)

_ensure_bootstrap()

# ==========================================
# 4. تهيئة البوت والمصفوفات
# ==========================================

bot = telebot.TeleBot(API_TOKEN, parse_mode=None)
app = Flask(__name__)
BOT_USERNAME = bot.get_me().username or "bot"

user_path: Dict[int, List[str]] = {}
upload_mode: Dict[int, bool] = {}
add_folder_mode: Dict[int, bool] = {}
admin_action_mode: Dict[int, Optional[str]] = {}
testing_mode: Dict[int, bool] = {}
action_payload: Dict[int, Any] = {}
RATE_LIMIT_DICT: Dict[int, float] = {}
ai_memory: Dict[int, List[Dict[str, str]]] = {}
broadcast_mode: Dict[int, bool] = {}
upload_batches: Dict[str, List[Any]] = {}
upload_batch_watchers: Dict[str, threading.Timer] = {}
system_stats = {"requests_24h": 0, "ai_queries_today": 0, "cache_hits_today": 0}

def now_utc() -> datetime:
    return datetime.utcnow()

def get_settings() -> Dict[str, Any]:
    return settings_col.find_one({"_id": BOT_GENERAL_SETTINGS_ID}) or {}

def save_settings(fields: Dict[str, Any]) -> None:
    settings_col.update_one({"_id": BOT_GENERAL_SETTINGS_ID}, {"$set": fields}, upsert=True)

def get_structure() -> Dict[str, Any]:
    doc = settings_col.find_one({"_id": ACADEMIC_STRUCTURE_ID}) or {}
    data = doc.get("data")
    if not isinstance(data, dict):
        data = ACADEMIC_STRUCTURE_DEFAULT
        settings_col.update_one({"_id": ACADEMIC_STRUCTURE_ID}, {"$set": {"data": data}}, upsert=True)
    return data

global_academic_structure = get_structure()

# ==========================================
# 5. دوال مساعدة وإدارة الصلاحيات
# ==========================================

def log_action(admin_id: int, action_type: str, details: str) -> None:
    try:
        user = users_col.find_one({"chat_id": admin_id}) or {}
        action_logs_col.insert_one({"admin_id": admin_id, "admin_name": user.get("first_name", "Admin"), "action": action_type, "details": details, "timestamp": now_utc()})
    except Exception:
        pass

def is_owner(chat_id: int) -> bool:
    return chat_id == SUPER_ADMIN_ID

def is_admin(chat_id: int) -> bool:
    if is_owner(chat_id): return True
    adm = admins_col.find_one({"id": chat_id, "active": True})
    return bool(adm and adm.get("type") in ["global", "super"])

def is_any_admin(chat_id: int) -> bool:
    if is_owner(chat_id): return True
    return admins_col.find_one({"id": chat_id, "active": True}) is not None

def get_admin_permissions(chat_id: int) -> List[str]:
    if is_owner(chat_id): return ["all"]
    adm = admins_col.find_one({"id": chat_id, "active": True})
    return adm.get("permissions", []) if adm else []

def has_permission(chat_id: int, current_path_str: str) -> bool:
    if testing_mode.get(chat_id, False): return False
    if is_owner(chat_id): return True
    adm = admins_col.find_one({"id": chat_id, "active": True})
    if not adm: return False
    if adm.get("type") in ["global", "super"]: return True
    for allowed_p in adm.get("allowed_paths", []):
        if current_path_str.startswith(allowed_p) or current_path_str == allowed_p:
            return True
    return False

def get_menu_by_path(path: List[str]) -> Optional[Dict[str, Any]]:
    menu = global_academic_structure
    for segment in path:
        if isinstance(menu, dict) and segment in menu:
            menu = menu[segment]
        else: return None
    return menu

def get_path_string(chat_id: int) -> str:
    return " > ".join(user_path.get(chat_id, []))

def reset_modes(chat_id: int, clear_upload: bool = True) -> None:
    if clear_upload: upload_mode[chat_id] = False
    add_folder_mode[chat_id] = False
    admin_action_mode[chat_id] = None
    action_payload.pop(chat_id, None)
    broadcast_mode[chat_id] = False

def check_rate_limit(chat_id: int) -> bool:
    now = time.time()
    if chat_id in RATE_LIMIT_DICT and now - RATE_LIMIT_DICT[chat_id] < 0.6: return False
    RATE_LIMIT_DICT[chat_id] = now
    return True

def sanitize_name(text: str) -> str:
    return text.replace("📄", "").replace("📌", "").replace("🖼️", "").replace("📁", "").strip()

def get_next_sort_order(menu_path: str, kind: str = "file") -> int:
    col = files_col if kind == "file" else folders_col
    key = "menu_path" if kind == "file" else "parent_path"
    top = list(col.find({key: menu_path}).sort("sort_order", DESCENDING).limit(1))
    return int(top[0].get("sort_order", 0)) + 10 if top else 10

def build_file_doc(message, path_str: str) -> Dict[str, Any]:
    if message.content_type == "document":
        name = message.document.file_name or "مستند"
        f_id = message.document.file_id
    elif message.content_type == "photo":
        name = "صورة توضيحية"
        f_id = message.photo[-1].file_id
    elif message.content_type == "video":
        name = "مقطع مرئي"
        f_id = message.video.file_id
    elif message.content_type == "audio":
        name = "ملف صوتي"
        f_id = message.audio.file_id
    else:
        name, f_id = "ملحق أكاديمي", None
    caption_text = message.caption or name
    clean_name = sanitize_name(caption_text)[:120]
    return {"menu_path": path_str, "name": clean_name or name, "type": message.content_type, "caption": message.caption, "file_id": f_id, "downloads": 0, "sort_order": get_next_sort_order(path_str, "file"), "upload_date": now_utc(), "uploader_id": message.chat.id, "uploader_name": (message.from_user.first_name if message.from_user else "") or "المنصة"}

def build_folder_doc(folder_name: str, parent_path: str) -> Dict[str, Any]:
    return {"parent_path": parent_path, "folder_name": folder_name, "created_at": now_utc(), "sort_order": get_next_sort_order(parent_path, "folder")}

def split_display_text(text: str) -> str:
    return text.split(" ", 1)[1].strip() if " " in text else text.strip()

def search_file_fallback(query_text: str, current_path: str = "") -> List[Dict[str, Any]]:
    if current_path:
        q1 = {"menu_path": {"$regex": f"^{re.escape(current_path)}"}, "$or": [{"name": {"$regex": re.escape(query_text), "$options": "i"}}, {"caption": {"$regex": re.escape(query_text), "$options": "i"}}]}
        res = list(files_col.find(q1).sort([("sort_order", ASCENDING), ("_id", ASCENDING)]).limit(10))
        if res: return res
    q2 = {"$or": [{"name": {"$regex": re.escape(query_text), "$options": "i"}}, {"caption": {"$regex": re.escape(query_text), "$options": "i"}}, {"menu_path": {"$regex": re.escape(query_text), "$options": "i"}}]}
    return list(files_col.find(q2).sort([("sort_order", ASCENDING), ("_id", ASCENDING)]).limit(15))

def rename_folder_recursive(old_full: str, new_full: str) -> None:
    for f in files_col.find({"menu_path": {"$regex": f"^{re.escape(old_full)}"}}):
        files_col.update_one({"_id": f["_id"]}, {"$set": {"menu_path": f["menu_path"].replace(old_full, new_full, 1)}})
    for d in folders_col.find({"parent_path": {"$regex": f"^{re.escape(old_full)}"}}):
        folders_col.update_one({"_id": d["_id"]}, {"$set": {"parent_path": d["parent_path"].replace(old_full, new_full, 1)}})

def get_target_group_id() -> Optional[int]:
    tg = get_settings().get("target_group_id")
    if tg is None or tg == "": return None
    try: return int(tg)
    except Exception: return None

def get_file_ratings(file_id: str) -> Tuple[float, int]:
    docs = list(ratings_col.find({"file_id": file_id}, {"score": 1}))
    if not docs: return 0.0, 0
    total = sum(int(d.get("score", 0)) for d in docs)
    return total / len(docs), len(docs)

def ensure_user(chat_id: int, first_name: str, username: Optional[str]) -> None:
    users_col.update_one({"chat_id": chat_id}, {"$set": {"first_name": first_name, "username": username and f"@{username}", "last_interaction": now_utc()}, "$setOnInsert": {"smart_notifications": True, "favorites": []}}, upsert=True)

# ==========================================
# 6. الذكاء الاصطناعي وإرسال الملفات المباشر
# ==========================================

def get_ai_response(prompt: str, chat_id: int) -> str:
    cached = kb_col.find_one({"question": prompt})
    if cached:
        system_stats["cache_hits_today"] += 1
        kb_col.update_one({"_id": cached["_id"]}, {"$inc": {"hits": 1}, "$set": {"last_used": now_utc()}})
        return cached.get("answer", "")
    
    history = ai_memory.get(chat_id, [])[-3:]
    clean_prompt = "أنت مساعد أكاديمي مختصر ودقيق. أجب بالعربية وبأسلوب واضح:\n\n"
    for item in history: clean_prompt += f"س: {item['q']}\nج: {item['a']}\n"
    clean_prompt += f"س: {prompt}\nج:"
    
    if GEMINI_API_KEY and not GEMINI_API_KEY.startswith("AIzaSy"):
        for model_name in ["gemini-2.0-flash-lite-preview-02-05", "gemini-2.0-flash", "gemini-1.5-flash"]:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
                payload = {"contents": [{"parts": [{"text": clean_prompt}]}], "generationConfig": {"temperature": 0.35, "maxOutputTokens": 700}}
                res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
                if res.status_code == 200:
                    ans = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                    if ans:
                        kb_col.insert_one({"question": prompt, "answer": ans, "hits": 1, "last_used": now_utc()})
                        system_stats["ai_queries_today"] += 1
                        return ans
            except Exception: continue
            
    for backup_model in ["openai", "llama", "mistral"]:
        try:
            url = f"https://text.pollinations.ai/{requests.utils.quote(clean_prompt)}?model={backup_model}&seed=42"
            res = requests.get(url, timeout=12)
            if res.status_code == 200 and res.text.strip():
                ans = res.text.strip()
                kb_col.insert_one({"question": prompt, "answer": ans, "hits": 1, "last_used": now_utc()})
                system_stats["ai_queries_today"] += 1
                return ans
        except Exception: continue
    return "🤖 نعتذر، هناك ضغط حالياً. يرجى إعادة إرسال استفسارك."

def schedule_batch_finalize(chat_id: int, media_group_id: str, path_str: str) -> None:
    def finalize():
        try:
            batch = upload_batches.pop(media_group_id, [])
            if not batch: return
            batch.sort(key=lambda m: m.message_id)
            base_sort = get_next_sort_order(path_str, "file")
            added = 0
            for i, msg in enumerate(batch):
                doc = build_file_doc(msg, path_str)
                doc["sort_order"] = base_sort + (i * 10)
                if doc["file_id"] and not files_col.find_one({"menu_path": path_str, "file_id": doc["file_id"]}):
                    files_col.insert_one(doc)
                    added += 1
            if added:
                bot.send_message(chat_id, f"✅ تم إدراج الدفعة بالترتيب الصحيح.\n📦 الملفات المضافة: {added}\n📁 المسار: `{path_str}`", parse_mode="Markdown")
                log_action(chat_id, "BATCH_UPLOAD", f"{added} files in {path_str}")
        except Exception as e:
            logging.error(f"Batch finalize error: {e}")
            
    old_timer = upload_batch_watchers.get(media_group_id)
    if old_timer:
        try: old_timer.cancel()
        except: pass
    t = threading.Timer(3.5, finalize)
    upload_batch_watchers[media_group_id] = t
    t.daemon = True
    t.start()

def send_file_to_user(chat_id: int, res: Dict[str, Any], has_perm: bool) -> None:
    try:
        if not res:
            bot.send_message(chat_id, "❌ الملف غير موجود.")
            return
        markup = InlineKeyboardMarkup(row_width=2)
        file_id_str = str(res["_id"])
        share_url = f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}?start={file_id_str}"
        deep_folder_url = f"https://t.me/{BOT_USERNAME}?start=folder_{file_id_str}"
        
        # أزرار المشرفين المخفية عن الجروبات والطلاب
        if has_perm and not testing_mode.get(chat_id, False):
            markup.add(InlineKeyboardButton("✏️ تسمية", callback_data=f"rn_{file_id_str}"), InlineKeyboardButton("🔄 استبدال", callback_data=f"rp_{file_id_str}"))
            markup.add(InlineKeyboardButton("🗑️ حذف", callback_data=f"dl_{file_id_str}"), InlineKeyboardButton("📦 نقل", callback_data=f"mv_{file_id_str}"))
            markup.add(InlineKeyboardButton("🔼 للأعلى", callback_data=f"up_{file_id_str}"), InlineKeyboardButton("🔽 للأسفل", callback_data=f"dn_{file_id_str}"))
            markup.add(InlineKeyboardButton("📌 تثبيت", callback_data=f"pn_{file_id_str}"))
            # زر النشر المباشر السحري
            markup.add(InlineKeyboardButton("📢 نشر في الجروب", callback_data=f"sh_{file_id_str}"))
            
        markup.add(InlineKeyboardButton("🔗 مشاركة", url=share_url), InlineKeyboardButton("📂 عرض المقرر", url=deep_folder_url))
        markup.add(InlineKeyboardButton("⭐ تقييم", callback_data=f"rt_{file_id_str}"), InlineKeyboardButton("❤️ مفضلة", callback_data=f"fv_{file_id_str}"))
        markup.add(InlineKeyboardButton("💡 ملفات من نفس المقرر", callback_data=f"rl_{file_id_str}"))
        
        file_type = res.get("type", "document")
        file_id = res.get("file_id")
        file_name = res.get("name", "وثيقة أكاديمية")
        caption = res.get("caption") or file_name
        up_date = res.get("upload_date", now_utc())
        if not isinstance(up_date, datetime): up_date = now_utc()
        
        avg_rt, rt_cnt = get_file_ratings(file_id_str)
        caption = f"{caption}\n\n📅 التاريخ: {up_date.strftime('%Y-%m-%d')}\n👤 بواسطة: {res.get('uploader_name', 'المنصة')}\n🔻 الاستدعاء: {res.get('downloads', 0)}\n⭐ التقييم: {avg_rt:.1f}/10 ({rt_cnt})\n\n📥 /start folder_{file_id_str}"
        
        if file_type == "text": bot.send_message(chat_id, res.get("content", file_name), reply_markup=markup)
        elif file_type == "photo" and file_id: bot.send_photo(chat_id, file_id, caption=caption, reply_markup=markup)
        elif file_id: bot.send_document(chat_id, file_id, caption=caption, reply_markup=markup)
        else: bot.send_message(chat_id, "❌ تنبيه: الملف غير متواجد بخوادم تيليجرام.", reply_markup=markup)
    except Exception as e:
        logging.error(f"Send File Error: {e}")

# ==========================================
# 7. التوجيه الديناميكي وعرض القوائم
# ==========================================

def render_path_header(path_str: str) -> str:
    return f"📂 المسار الحالي:\n`{path_str or 'الرئيسية'}`"

def show_menu(chat_id: int) -> None:
    path = user_path.get(chat_id, [])
    path_str = get_path_string(chat_id)
    current_menu = get_menu_by_path(path)
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mode = admin_action_mode.get(chat_id)
    
    if mode == "move_file_dest":
        markup.add(KeyboardButton("📦 أنقل إلى هذا القسم"), KeyboardButton("🛑 إلغاء الأمر"))
        bot.send_message(chat_id, f"📦 تصفح الأقسام للوصول للموقع الجديد ثم اضغط تأكيد.\n📌 {path_str or 'الرئيسية'}", reply_markup=markup)
        return
    if mode == "navigate_to_assign":
        markup.add(KeyboardButton("✅ تعيين مشرف لهذا القسم"), KeyboardButton("🛑 إلغاء الأمر"))
        
    if not path:
        for level_name in [k for k in global_academic_structure.keys() if "مستوى" in k]:
            markup.add(KeyboardButton(level_name))
        markup.add(KeyboardButton("🌟 ميزات الطالب"), KeyboardButton("📖 دليل القسم"))
        markup.add(KeyboardButton("📞 التواصل مع المشرف العام"), KeyboardButton("⭐ ملفاتي المفضلة"))
        if is_owner(chat_id) and not testing_mode.get(chat_id, False):
            markup.add(KeyboardButton("👑 لوحة المشرف الرئيسي"))
        elif is_admin(chat_id) and not testing_mode.get(chat_id, False):
            markup.add(KeyboardButton("🛡️ لوحة المشرف العام"))
        if is_any_admin(chat_id):
            markup.add(KeyboardButton("👤 عرض كمستخدم" if not testing_mode.get(chat_id, False) else "🛑 إنهاء العرض كمستخدم"))
        bot.send_message(chat_id, "⚙️ القائمة الرئيسية:", reply_markup=markup)
        return
        
    if path_str == "STUDENT_FEATURES":
        markup.add(KeyboardButton("🤖 المساعد الذكي (AI)"), KeyboardButton("🔍 بحث عن ملف"))
        markup.add(KeyboardButton("🔥 الملفات الأكثر شعبية"), KeyboardButton("🆕 تحديثات اليوم"))
        markup.add(KeyboardButton("📢 إعلانات الدفعة"), KeyboardButton("🔙 الرجوع للقائمة الرئيسية"))
        bot.send_message(chat_id, "🌟 *ميزات الطالب:*", reply_markup=markup, parse_mode="Markdown")
        return
        
    if path_str == "FAVORITES":
        u_data = users_col.find_one({"chat_id": chat_id}) or {}
        favs = u_data.get("favorites", [])
        markup.add(KeyboardButton("🔙 الرجوع للقائمة الرئيسية"))
        bot.send_message(chat_id, "⭐ *المفضلة:*", reply_markup=markup, parse_mode="Markdown")
        for fav in favs:
            if isinstance(fav, str) and not fav.startswith("path:"):
                try:
                    f_doc = files_col.find_one({"_id": ObjectId(fav)})
                    if f_doc: send_file_to_user(chat_id, f_doc, False)
                except Exception: continue
        if not favs: bot.send_message(chat_id, "لا توجد عناصر مفضلة بعد.")
        return
        
    if path_str == "SUPER_ADMIN_PANEL":
        markup.add("👥 إدارة المشرفين", "🔑 صلاحيات المشرفين")
        markup.add("📈 إحصائيات النظام", "📊 حالة النظام")
        markup.add("🚨 وضع الطوارئ", "📝 سجل العمليات")
        markup.add("📊 نشاط المشرفين", "🔍 كشف الملفات المكررة")
        markup.add("💾 النسخ الاحتياطي اليدوي", "✏️ تعديل نصوص البوت")
        markup.add("📢 إدارة الإعلانات", "🏷️ إدارة الأرشفة")
        markup.add("⭐️ التقييمات", "📊 إحصائيات المقررات")
        markup.add("🛠️ إدارة المشرف المخصص", "⚙️ إعدادات جروب الدفعة")
        markup.add("🔙 الرجوع للقائمة الرئيسية")
        bot.send_message(chat_id, "👑 *لوحة المشرف الرئيسي:*", reply_markup=markup, parse_mode="Markdown")
        return
        
    if path_str == "GLOBAL_ADMIN_PANEL":
        perms = get_admin_permissions(chat_id)
        if "all" in perms or "stats" in perms: markup.add("📊 حالة النظام", "📈 إحصائيات النظام")
        if "all" in perms or "broadcast" in perms: markup.add("📢 إدارة الإعلانات")
        if "all" in perms or "archives" in perms: markup.add("🏷️ إدارة الأرشفة")
        if "all" in perms or "courses_stats" in perms: markup.add("📊 إحصائيات المقررات")
        if "all" in perms or "texts" in perms: markup.add("✏️ تعديل نصوص البوت")
        if "all" in perms or "logs" in perms: markup.add("📝 سجل العمليات")
        markup.add("👤 عرض كمستخدم" if not testing_mode.get(chat_id, False) else "🛑 إنهاء العرض كمستخدم")
        markup.add("🔙 الرجوع للقائمة الرئيسية")
        bot.send_message(chat_id, "🛡️ *لوحة المشرف العام:*", reply_markup=markup, parse_mode="Markdown")
        return
        
    if path_str == "MANAGE_ADMINS":
        markup.add("➕ إضافة مشرف عام", "➕ إضافة مشرف مخصص لمسار")
        markup.add("✅ تفعيل مشرف", "🚫 تعطيل مشرف")
        markup.add("➖ حذف مشرف", "🟢 منح صلاحية محددة")
        markup.add("🔴 سحب صلاحية محددة", "📋 عرض صلاحيات المشرف")
        markup.add("📊 لوحة نشاط المشرفين", "📝 سجل العمليات")
        markup.add("🔍 البحث عن مشرف", "🛠️ إدارة المشرف المخصص")
        markup.add("🔙 الرجوع للقائمة السابقة")
        bot.send_message(chat_id, "👥 *إدارة المشرفين:*", reply_markup=markup, parse_mode="Markdown")
        return
        
    if path_str == "ADMIN_PERMISSIONS":
        markup.add("🟢 منح صلاحية محددة", "🔴 سحب صلاحية محددة")
        markup.add("📋 عرض صلاحيات المشرف", "🔙 الرجوع للقائمة الرئيسية")
        bot.send_message(chat_id, "🔑 *صلاحيات المشرفين:*", reply_markup=markup, parse_mode="Markdown")
        return
        
    if path_str == "TEXTS_PANEL":
        markup.add("✏️ تعديل Start", "✏️ تعديل Info")
        markup.add("✏️ تعديل المطور", "✏️ تعديل اللجنة العلمية")
        markup.add("✏️ تعديل دليل القسم", "🔙 الرجوع للقائمة الرئيسية")
        bot.send_message(chat_id, "✏️ *تعديل نصوص البوت:*", reply_markup=markup, parse_mode="Markdown")
        return
        
    if path_str == "EMERGENCY_PANEL":
        flags = get_settings().get("emergency_flags", DEFAULT_EMERGENCY_FLAGS)
        markup.add(KeyboardButton(f"{'🟢' if not flags.get('ai') else '🔴'} الذكاء الاصطناعي"), KeyboardButton(f"{'🟢' if not flags.get('upload') else '🔴'} الرفع"))
        markup.add(KeyboardButton(f"{'🟢' if not flags.get('search') else '🔴'} البحث"), KeyboardButton(f"{'🟢' if not flags.get('ads') else '🔴'} الإعلانات"))
        markup.add(KeyboardButton(f"{'🟢' if not flags.get('all') else '🔴'} الخدمة الكلية"), KeyboardButton("🔙 الرجوع للقائمة الرئيسية"))
        bot.send_message(chat_id, "🚨 *وضع الطوارئ:*", reply_markup=markup, parse_mode="Markdown")
        return
        
    if path_str == "LOGS_PANEL":
        markup.add("📝 سجل العمليات", "📊 نشاط المشرفين")
        markup.add("🔍 كشف الملفات المكررة", "🔙 الرجوع للقائمة الرئيسية")
        bot.send_message(chat_id, "📝 *لوحة السجلات:*", reply_markup=markup, parse_mode="Markdown")
        return
        
    if path_str == "STATS_PANEL":
        markup.add("📈 إحصائيات النظام", "📊 إحصائيات المقررات")
        markup.add("⭐️ التقييمات", "🔙 الرجوع للقائمة الرئيسية")
        bot.send_message(chat_id, "📊 *لوحة الإحصائيات:*", reply_markup=markup, parse_mode="Markdown")
        return
        
    if path_str == "GUIDE_PANEL":
        markup.add("✏️ تعديل دليل القسم" if is_owner(chat_id) or "texts" in get_admin_permissions(chat_id) or "all" in get_admin_permissions(chat_id) else "🔙 الرجوع للقائمة الرئيسية")
        markup.add("🔙 الرجوع للقائمة الرئيسية")
        bot.send_message(chat_id, get_settings().get("guide_text", DEFAULT_GUIDE_TEXT), reply_markup=markup)
        return
        
    if isinstance(current_menu, dict):
        for key in current_menu.keys(): markup.add(KeyboardButton(key))
    for db_folder in folders_col.find({"parent_path": path_str}).sort([("sort_order", ASCENDING), ("folder_name", ASCENDING)]):
        markup.add(KeyboardButton(f"📁 {db_folder['folder_name']}"))
    for db_file in files_col.find({"menu_path": path_str}).sort([("sort_order", ASCENDING), ("name", ASCENDING)]).limit(80):
        icon = "📌" if db_file.get("type") == "text" else "🖼️" if db_file.get("type") == "photo" else "📄"
        markup.add(KeyboardButton(f"{icon} {db_file['name']}"))
        
    if path_str in global_academic_structure.keys(): markup.add(KeyboardButton("🔙 الرجوع للقائمة الرئيسية"))
    else: markup.add(KeyboardButton("🔙 الرجوع للقائمة السابقة"), KeyboardButton("🔝 القائمة الرئيسية"))
    
    if has_permission(chat_id, path_str):
        markup.add(KeyboardButton("➕ إضافة ملف/نص"), KeyboardButton("📂 إضافة مجلد"))
        if path_str not in ["", "STUDENT_FEATURES", "FAVORITES", "SUPER_ADMIN_PANEL", "GLOBAL_ADMIN_PANEL", "MANAGE_ADMINS", "ADMIN_PERMISSIONS", "TEXTS_PANEL", "EMERGENCY_PANEL", "LOGS_PANEL", "STATS_PANEL", "GUIDE_PANEL"]:
            markup.add(KeyboardButton("✏️ إعادة تسمية هذا القسم"), KeyboardButton("🗑️ حذف هذا القسم"))
            markup.add(KeyboardButton("🔼 نقل مجلد للأعلى"), KeyboardButton("🔽 نقل مجلد للأسفل"))
            
    bot.send_message(chat_id, render_path_header(path_str), reply_markup=markup, parse_mode="Markdown")

# ==========================================
# 8. معالجات الرسائل المركزية
# ==========================================

@bot.message_handler(commands=["start"])
def start_command(message):
    chat_id = message.chat.id
    user_data = users_col.find_one({"chat_id": chat_id})
    if user_data and user_data.get("blocked"): return
    settings = get_settings()
    if settings.get("status") == "inactive" and not is_any_admin(chat_id):
        bot.send_message(chat_id, "🚧 البوت حالياً تحت الصيانة. نعود قريباً.")
        return
    first_name = (message.from_user.first_name if message.from_user else "") or "طالبنا"
    ensure_user(chat_id, first_name, message.from_user.username if message.from_user else None)
    
    command_args = (message.text or "").split()
    if len(command_args) > 1:
        param = command_args[1].strip()
        if param.startswith("folder_"):
            try:
                f_obj = files_col.find_one({"_id": ObjectId(param.replace("folder_", ""))})
                if f_obj and f_obj.get("menu_path"):
                    user_path[chat_id] = f_obj["menu_path"].split(" > ")
                    show_menu(chat_id)
                    return
            except Exception: pass
        else:
            try:
                f_obj = files_col.find_one({"_id": ObjectId(param)})
                if f_obj:
                    files_col.update_one({"_id": f_obj["_id"]}, {"$inc": {"downloads": 1}})
                    send_file_to_user(chat_id, f_obj, has_permission(chat_id, f_obj["menu_path"]))
                    return
            except Exception: pass
            
    user_path[chat_id] = []
    reset_modes(chat_id)
    testing_mode[chat_id] = False
    bot.send_message(chat_id, settings.get("start_text", DEFAULT_START_TEXT).replace("{first_name}", first_name))
    show_menu(chat_id)

@bot.message_handler(commands=["info"])
def info_command_handler(message):
    bot.send_message(message.chat.id, get_settings().get("info_text", DEFAULT_INFO_TEXT))

def emit_contact_card(chat_id: int) -> None:
    dev_msg = get_settings().get("dev_text", DEFAULT_DEV_TEXT)
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("❓ استفسار", url="https://t.me/AlwatheqAssag"),
        InlineKeyboardButton("📝 ملاحظات", url="https://t.me/AlwatheqAssag"),
        InlineKeyboardButton("⚠️ بلاغ عن مقرر", url="https://t.me/AlwatheqAssag"),
        InlineKeyboardButton("📤 إرسال ملف أو ملخص", url="https://t.me/AlwatheqAssag"),
        InlineKeyboardButton("💬 فتح المحادثة المباشرة", url="https://t.me/AlwatheqAssag"),
    )
    bot.send_message(chat_id, dev_msg, reply_markup=markup)

@bot.message_handler(content_types=["text", "document", "photo", "video", "audio"])
def universal_handler(message):
    chat_id = message.chat.id
    if not check_rate_limit(chat_id): return
    system_stats["requests_24h"] += 1
    
    if message.chat.type in ["group", "supergroup"]: return
        
    text = message.text if message.content_type == "text" else ""
    path_str = get_path_string(chat_id)
    mode = admin_action_mode.get(chat_id)
    
    if text == "🛑 إلغاء الأمر":
        reset_modes(chat_id); bot.send_message(chat_id, "✅ تم الإلغاء."); show_menu(chat_id); return
        
    nav_buttons = ["🔝 القائمة الرئيسية", "🔙 الرجوع للقائمة السابقة", "🔙 الرجوع للقائمة الرئيسية", "🌟 ميزات الطالب", "📖 دليل القسم", "⭐ ملفاتي المفضلة", "📞 التواصل مع المشرف العام", "👑 لوحة المشرف الرئيسي", "🛡️ لوحة المشرف العام", "👥 إدارة المشرفين", "🔑 صلاحيات المشرفين", "✏️ تعديل نصوص البوت", "🚨 وضع الطوارئ", "📝 سجل العمليات", "📈 إحصائيات النظام", "📊 حالة النظام", "📊 إحصائيات المقررات", "⭐️ التقييمات", "⚙️ إعدادات جروب الدفعة"] + list(global_academic_structure.keys())
    
    if text in nav_buttons:
        if mode not in ["navigate_to_assign", "move_file_dest"]: reset_modes(chat_id)
        if text in ["🔝 القائمة الرئيسية", "🔙 الرجوع للقائمة الرئيسية"]: user_path[chat_id] = []
        elif text == "🔙 الرجوع للقائمة السابقة" and user_path.get(chat_id): user_path[chat_id].pop()
        elif text in global_academic_structure.keys(): user_path[chat_id] = [text]
        elif text == "🌟 ميزات الطالب": user_path[chat_id] = ["STUDENT_FEATURES"]
        elif text == "⭐ ملفاتي المفضلة": user_path[chat_id] = ["FAVORITES"]
        elif text == "👑 لوحة المشرف الرئيسي" and is_owner(chat_id): user_path[chat_id] = ["SUPER_ADMIN_PANEL"]
        elif text == "🛡️ لوحة المشرف العام" and is_admin(chat_id): user_path[chat_id] = ["GLOBAL_ADMIN_PANEL"]
        elif text == "👥 إدارة المشرفين" and is_owner(chat_id): user_path[chat_id] = ["MANAGE_ADMINS"]
        elif text == "🔑 صلاحيات المشرفين" and is_owner(chat_id): user_path[chat_id] = ["ADMIN_PERMISSIONS"]
        elif text == "✏️ تعديل نصوص البوت" and (is_owner(chat_id) or "texts" in get_admin_permissions(chat_id) or "all" in get_admin_permissions(chat_id)): user_path[chat_id] = ["TEXTS_PANEL"]
        elif text == "🚨 وضع الطوارئ" and (is_owner(chat_id) or "emergency" in get_admin_permissions(chat_id) or "all" in get_admin_permissions(chat_id)): user_path[chat_id] = ["EMERGENCY_PANEL"]
        elif text == "📝 سجل العمليات" and (is_owner(chat_id) or "logs" in get_admin_permissions(chat_id) or "all" in get_admin_permissions(chat_id)): user_path[chat_id] = ["LOGS_PANEL"]
        elif text in ["📈 إحصائيات النظام", "📊 حالة النظام", "📊 إحصائيات المقررات", "⭐️ التقييمات"] and (is_owner(chat_id) or "stats" in get_admin_permissions(chat_id) or "courses_stats" in get_admin_permissions(chat_id) or "all" in get_admin_permissions(chat_id)): user_path[chat_id] = ["STATS_PANEL"]
        elif text == "📖 دليل القسم": user_path[chat_id] = ["GUIDE_PANEL"]
        elif text == "📞 التواصل مع المشرف العام": emit_contact_card(chat_id); return
        elif text == "⚙️ إعدادات جروب الدفعة" and is_owner(chat_id):
            current_id = get_settings().get("target_group_id", "غير معيّن ❌")
            bot.send_message(chat_id, f"⚙️ *إعدادات جروب النشر الحالي:*\n\nالآيدي المسجل: `{current_id}`\n\nاضغط على الزر بالأسفل لتغييره أو تحديثه:", parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("✏️ تحديث آيدي الجروب", "🛑 إلغاء الأمر"))
            return
        show_menu(chat_id); return

    if text == "✏️ تحديث آيدي الجروب" and is_owner(chat_id):
        reset_modes(chat_id); admin_action_mode[chat_id] = "set_group_id_db"
        bot.send_message(chat_id, "📥 أرسل آيدي (ID) الجروب الجديد الآن (يبدأ بـ -100):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

    if mode == "set_group_id_db" and text and is_owner(chat_id):
        try:
            group_id_num = int(text.strip())
            save_settings({"target_group_id": group_id_num})
            log_action(chat_id, "SET_TARGET_GROUP_ID", f"New Group ID: {group_id_num}")
            bot.send_message(chat_id, f"✅ تم حفظ وتحديث آيدي جروب النشر بنجاح!\n🎯 الآيدي الحالي: `{group_id_num}`", parse_mode="Markdown")
            reset_modes(chat_id); user_path[chat_id] = ["SUPER_ADMIN_PANEL"]; show_menu(chat_id)
        except Exception: bot.send_message(chat_id, "❌ خطأ! يرجى إرسال أرقام فقط مع إشارة السالب.")
        return

    if text == "اللجنة العلمية" and path_str == "🌱 مستوى أول": bot.send_message(chat_id, get_settings().get("sci_text", DEFAULT_SCI_TEXT)); return
    
    if text == "🤖 المساعد الذكي (AI)":
        if get_settings().get("emergency_flags", {}).get("ai", False) and not is_any_admin(chat_id):
            bot.send_message(chat_id, "🚧 المساعد الذكي معطل حالياً للصيانة."); return
        reset_modes(chat_id); admin_action_mode[chat_id] = "ai_chat"; ai_memory.setdefault(chat_id, [])
        bot.send_message(chat_id, "🤖 أرسل سؤالك الأكاديمي الآن:"); return

    if mode == "ai_chat" and text:
        bot.send_message(chat_id, "⏳ جاري التفكير...")
        ans = get_ai_response(text, chat_id)
        ai_memory[chat_id].append({"q": text, "a": ans})
        ai_memory[chat_id] = ai_memory[chat_id][-3:]
        bot.send_message(chat_id, ans); reset_modes(chat_id); show_menu(chat_id); return

    if text == "🔍 بحث عن ملف":
        reset_modes(chat_id); admin_action_mode[chat_id] = "search_exec"; bot.send_message(chat_id, "🔍 أرسل كلمة البحث:"); return

    if mode == "search_exec" and text:
        results = search_file_fallback(text, path_str if path_str else "")
        if results:
            bot.send_message(chat_id, f"🔍 وجدنا {len(results)} نتيجة:")
            for item in results: send_file_to_user(chat_id, item, has_permission(chat_id, item.get("menu_path", "")))
        else: bot.send_message(chat_id, "❌ لم نجد مطابقة.")
        reset_modes(chat_id); show_menu(chat_id); return

    if text == "📢 إعلانات الدفعة": bot.send_message(chat_id, f"📢 *إعلان الدفعة:*\n\n{get_settings().get('last_announcement', 'لا إعلانات.')}", parse_mode="Markdown"); return
    
    if text == "🔥 الملفات الأكثر شعبية":
        pop = list(files_col.find({"downloads": {"$gt": 0}}).sort("downloads", DESCENDING).limit(5))
        if pop:
            bot.send_message(chat_id, "🔥 *أشهر الملفات:*", parse_mode="Markdown")
            for p in pop: send_file_to_user(chat_id, p, False)
        else: bot.send_message(chat_id, "لا إحصائيات بعد.")
        return

    if text == "🆕 تحديثات اليوم":
        rec = list(files_col.find({"upload_date": {"$gte": now_utc() - timedelta(days=1)}}).sort("upload_date", DESCENDING).limit(10))
        if rec:
            bot.send_message(chat_id, "🆕 *أحدث الملفات:*", parse_mode="Markdown")
            for r in rec: send_file_to_user(chat_id, r, False)
        else: bot.send_message(chat_id, "لا توجد ملفات جديدة اليوم.")
        return

    if text == "👤 عرض كمستخدم" and is_any_admin(chat_id):
        testing_mode[chat_id] = True; user_path[chat_id] = []; bot.send_message(chat_id, "👀 تم تفعيل العرض كمستخدم."); show_menu(chat_id); return

    if text == "🛑 إنهاء العرض كمستخدم" and testing_mode.get(chat_id, False):
        testing_mode[chat_id] = False; user_path[chat_id] = []; bot.send_message(chat_id, "💼 تم إنهاء العرض كمستخدم."); show_menu(chat_id); return

    if text == "💾 النسخ الاحتياطي اليدوي" and is_owner(chat_id):
        bot.send_message(chat_id, "⏳ جاري تصدير البيانات...")
        bkp = {"files": list(files_col.find({}, {"_id": 0})), "folders": list(folders_col.find({}, {"_id": 0}))}
        bio = io.BytesIO(json.dumps(bkp, default=json_util.default, ensure_ascii=False).encode("utf-8"))
        bio.name = f"DB_Backup_{now_utc().strftime('%Y%m%d_%H%M')}.json"
        bot.send_document(chat_id, bio, caption="💾 نسخة احتياطية JSON"); return

    if text == "📢 إدارة الإعلانات" and (is_owner(chat_id) or "broadcast" in get_admin_permissions(chat_id)):
        reset_modes(chat_id); broadcast_mode[chat_id] = True; bot.send_message(chat_id, "📢 أرسل الإعلان الآن:"); return

    if broadcast_mode.get(chat_id, False) and (is_owner(chat_id) or "broadcast" in get_admin_permissions(chat_id)):
        broadcast_mode[chat_id] = False; save_settings({"last_announcement": text or "مرفق إعلاني"})
        sent = 0
        for stu in list(users_col.find({}, {"chat_id": 1})):
            try: bot.copy_message(stu["chat_id"], chat_id, message.message_id); sent += 1
            except Exception: pass
        bot.send_message(chat_id, f"📢 تم إيصال الرسالة إلى {sent} مشترك."); log_action(chat_id, "ADD_ANNOUNCEMENT", "media"); show_menu(chat_id); return

    if text == "➕ إضافة ملف/نص" and has_permission(chat_id, path_str):
        reset_modes(chat_id); upload_mode[chat_id] = True; bot.send_message(chat_id, "📥 أرسل الملفات الآن (مفرد أو ألبوم):"); return

    if text == "📂 إضافة مجلد" and has_permission(chat_id, path_str):
        reset_modes(chat_id); add_folder_mode[chat_id] = True; bot.send_message(chat_id, "📂 اكتب اسم المجلد الجديد:"); return

    if text == "✏️ إعادة تسمية هذا القسم" and has_permission(chat_id, path_str) and path_str:
        reset_modes(chat_id); admin_action_mode[chat_id] = "rename_folder"; bot.send_message(chat_id, "✏️ أرسل الاسم الجديد للقسم:"); return

    if text == "🗑️ حذف هذا القسم" and has_permission(chat_id, path_str) and path_str:
        current_name = user_path[chat_id][-1]
        parent_p = " > ".join(user_path[chat_id][:-1]) if len(user_path.get(chat_id, [])) > 1 else ""
        folders_col.delete_one({"parent_path": parent_p, "folder_name": current_name})
        user_path[chat_id].pop(); bot.send_message(chat_id, "🗑️ تم الحذف."); show_menu(chat_id); return

    if text in ["🔼 نقل مجلد للأعلى", "🔽 نقل مجلد للأسفل"] and has_permission(chat_id, path_str) and path_str:
        current_name = user_path[chat_id][-1]
        parent_p = " > ".join(user_path[chat_id][:-1]) if len(user_path.get(chat_id, [])) > 1 else ""
        fld = folders_col.find_one({"parent_path": parent_p, "folder_name": current_name})
        if fld:
            inc = -10 if "الأعلى" in text else 10
            folders_col.update_one({"_id": fld["_id"]}, {"$inc": {"sort_order": inc}})
        show_menu(chat_id); return

    if mode == "rename_folder" and text and has_permission(chat_id, path_str) and path_str:
        old_name = user_path[chat_id][-1]
        parent_p = " > ".join(user_path[chat_id][:-1]) if len(user_path.get(chat_id, [])) > 1 else ""
        folders_col.update_one({"parent_path": parent_p, "folder_name": old_name}, {"$set": {"folder_name": text.strip()}})
        old_full = f"{parent_p} > {old_name}" if parent_p else old_name
        new_full = f"{parent_p} > {text.strip()}" if parent_p else text.strip()
        rename_folder_recursive(old_full, new_full)
        user_path[chat_id][-1] = text.strip()
        bot.send_message(chat_id, "✅ تم التعديل."); reset_modes(chat_id); show_menu(chat_id); return

    if mode == "rename_file" and text:
        fid = action_payload.get(chat_id)
        if fid: files_col.update_one({"_id": ObjectId(fid)}, {"$set": {"name": text.strip()}})
        bot.send_message(chat_id, "✅ تم التعديل."); reset_modes(chat_id); show_menu(chat_id); return

    if mode == "replace_file" and message.content_type in ["document", "photo", "video", "audio", "text"]:
        fid = action_payload.get(chat_id)
        if fid:
            doc = build_file_doc(message, path_str)
            upd = {"type": doc["type"], "file_id": doc["file_id"], "name": doc["name"], "caption": doc["caption"], "menu_path": path_str} if doc["file_id"] else {"type": "text", "content": text, "name": text[:60], "file_id": None, "menu_path": path_str}
            files_col.update_one({"_id": ObjectId(fid)}, {"$set": upd})
            bot.send_message(chat_id, "✅ تم الاستبدال.")
        reset_modes(chat_id); show_menu(chat_id); return

    if add_folder_mode.get(chat_id, False) and text and has_permission(chat_id, path_str):
        folders_col.insert_one(build_folder_doc(text.strip(), path_str))
        bot.send_message(chat_id, f"✅ تم إنشاء: {text.strip()}"); reset_modes(chat_id); show_menu(chat_id); return

    if upload_mode.get(chat_id, False) and message.content_type == "text" and has_permission(chat_id, path_str):
        files_col.insert_one({"menu_path": path_str, "name": text[:80].strip(), "type": "text", "content": text, "downloads": 0, "sort_order": get_next_sort_order(path_str, "file"), "upload_date": now_utc(), "uploader_id": chat_id})
        bot.send_message(chat_id, "✅ تم حفظ التلخيص."); return

    if message.content_type in ["document", "photo", "video", "audio"] and upload_mode.get(chat_id, False) and has_permission(chat_id, path_str):
        if getattr(message, "media_group_id", None):
            gid = str(message.media_group_id)
            upload_batches.setdefault(gid, []).append(message)
            schedule_batch_finalize(chat_id, gid, path_str)
        else:
            doc = build_file_doc(message, path_str)
            if not files_col.find_one({"menu_path": path_str, "file_id": doc["file_id"]}):
                files_col.insert_one(doc); bot.reply_to(message, f"✅ تم حفظ: {doc['name']}")
            else: bot.reply_to(message, "⚠️ الملف موجود بالفعل.")
        return

    if text.startswith("📁 "):
        user_path.setdefault(chat_id, []).append(text.replace("📁 ", "", 1).strip()); show_menu(chat_id); return

    if text and any(text.startswith(icon) for icon in ["📄 ", "📌 ", "🖼️ "]):
        ex_name = split_display_text(text)
        f_doc = files_col.find_one({"menu_path": path_str, "name": {"$regex": f"^{re.escape(ex_name)}$", "$options": "i"}})
        if not f_doc: f_doc = files_col.find_one({"name": {"$regex": f"^{re.escape(ex_name)}$", "$options": "i"}})
        if not f_doc:
            res = search_file_fallback(ex_name, path_str)
            f_doc = res[0] if res else None
        if f_doc:
            files_col.update_one({"_id": f_doc["_id"]}, {"$inc": {"downloads": 1}})
            send_file_to_user(chat_id, f_doc, has_permission(chat_id, f_doc.get("menu_path", "")))
        else: bot.send_message(chat_id, "❌ لم يتم العثور على الملف.")
        return

    current_menu = get_menu_by_path(user_path.get(chat_id, []))
    if isinstance(current_menu, dict) and text in current_menu:
        user_path.setdefault(chat_id, []).append(text); show_menu(chat_id); return

# ==========================================
# 9. معالج الأزرار الشفافة الشامل (Callback Handler)
# ==========================================

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    data = call.data or ""
    
    # تحرير الواجهة لمنع التعليق
    try: bot.answer_callback_query(call.id)
    except Exception: pass
    
    if "_" not in data: return
    try: action, obj_id = data.split("_", 1)
    except Exception: return

    # --- 1. المفضلة ---
    if action == "fv":
        users_col.update_one({"chat_id": chat_id}, {"$addToSet": {"favorites": obj_id}})
        try: bot.answer_callback_query(call.id, "❤️ تمت إضافته للمفضلة", show_alert=False)
        except Exception: pass
        return

    # --- 2. التقييم ---
    if action == "rt":
        m = InlineKeyboardMarkup(row_width=5)
        m.add(*[InlineKeyboardButton(str(i), callback_data=f"str_{i}_{obj_id}") for i in range(1, 11)])
        try: bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=m)
        except Exception: pass
        return

    if action == "str":
        try:
            score, f_id = obj_id.split("_", 1)
            score_i = int(score)
            ratings_col.update_one({"file_id": f_id, "user_id": chat_id}, {"$set": {"score": score_i, "updated_at": now_utc()}}, upsert=True)
            bot.answer_callback_query(call.id, f"⭐ تم حفظ تقييمك: {score_i}/10", show_alert=False)
            bot.delete_message(chat_id, call.message.message_id)
        except Exception: pass
        return

    # --- 3. تفاصيل إضافية ---
    if action == "rl":
        f_doc = files_col.find_one({"_id": ObjectId(obj_id)})
        if f_doc:
            rel = list(files_col.find({"menu_path": f_doc.get("menu_path", ""), "_id": {"$ne": ObjectId(obj_id)}}).limit(4))
            if rel:
                bot.send_message(chat_id, "💡 *ملفات إضافية من نفس المقرر:*", parse_mode="Markdown")
                for r in rel: send_file_to_user(chat_id, r, False)
        return

    # --- 4. النشر المباشر والمضمون في الجروب ---
    if action == "sh":
        f_doc = files_col.find_one({"_id": ObjectId(obj_id)})
        if not f_doc or not has_permission(chat_id, f_doc.get("menu_path", "")):
            try: bot.answer_callback_query(call.id, "❌ لا تمتلك الصلاحية.", show_alert=True)
            except Exception: pass
            return
            
        target_group_id = get_target_group_id()
        if not target_group_id:
            bot.send_message(chat_id, "❌ لم يتم ضبط آيدي الجروب في إعدادات البوت!")
            return
            
        try:
            bot.send_message(chat_id, "⏳ جاري إرسال الملف للجروب...")
            # has_perm=False لحماية خيارات المشرف داخل الجروب
            send_file_to_user(target_group_id, f_doc, has_perm=False)
            bot.send_message(chat_id, f"✅ تم نشر الملف `{f_doc.get('name')}` للجروب بنجاح!", parse_mode="Markdown")
            log_action(chat_id, "PUBLISH_FILE", f"{obj_id} -> {target_group_id}")
        except Exception as e:
            bot.send_message(chat_id, f"❌ فشل النشر للجروب. تأكد أن البوت مشرف هناك.\nالخطأ: {e}")
        return

    # --- 5. خيارات التحكم الإداري (حذف، تسمية، نقل) ---
    f_doc = files_col.find_one({"_id": ObjectId(obj_id)})
    if not f_doc or not has_permission(chat_id, f_doc.get("menu_path", "")):
        try: bot.answer_callback_query(call.id, "❌ غير مصرح", show_alert=True)
        except Exception: pass
        return
        
    if action == "dl":
        files_col.delete_one({"_id": f_doc["_id"]})
        try: bot.delete_message(chat_id, call.message.message_id)
        except Exception: pass
        show_menu(chat_id)
    elif action == "rn":
        admin_action_mode[chat_id] = "rename_file"; action_payload[chat_id] = obj_id
        bot.send_message(chat_id, "✏️ أرسل الاسم الجديد للملف:")
    elif action == "rp":
        admin_action_mode[chat_id] = "replace_file"; action_payload[chat_id] = obj_id
        bot.send_message(chat_id, "🔄 أرسل الملف البديل الآن:")
    elif action == "mv":
        admin_action_mode[chat_id] = "move_file_dest"; action_payload[chat_id] = obj_id
        user_path[chat_id] = []
        bot.send_message(chat_id, "📦 تصفح الأقسام للموقع الجديد ثم اضغط (📦 أنقل إلى هذا القسم).")
        show_menu(chat_id)
    elif action in ["up", "dn", "pn"]:
        inc = -10 if action == "up" else 10
        if action == "pn": inc = -999999
        files_col.update_one({"_id": ObjectId(obj_id)}, {"$inc": {"sort_order": inc}})
        show_menu(chat_id)

# ==========================================
# 10. إقلاع السيرفر والـ Webhook
# ==========================================

@app.route("/")
def index_home_route():
    return "LMS Bot V5.7 is RUNNING 🚀", 200

@app.route("/webhook", methods=["POST"])
def webhook_listen_route():
    if request.headers.get("content-type") == "application/json":
        update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
        bot.process_new_updates([update])
        return "!", 200
    return "Invalid", 403

@app.route("/f/<file_id>")
def fast_folder_redirect(file_id):
    return f"Use https://t.me/{BOT_USERNAME}?start={file_id}", 200

def configure_webhook_after_delay():
    time.sleep(3)
    try:
        if WEBHOOK_URL:
            bot.remove_webhook()
            bot.set_webhook(url=f"{WEBHOOK_URL.rstrip('/')}/webhook")
            logging.info("Webhook configured successfully!")
        else:
            bot.infinity_polling(timeout=20, long_polling_timeout=20)
    except Exception as e:
        logging.error(f"Webhook/polling startup error: {e}")

if __name__ == "__main__":
    threading.Thread(target=configure_webhook_after_delay, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT)
