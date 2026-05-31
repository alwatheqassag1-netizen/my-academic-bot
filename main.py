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
from flask import Flask, request

if sys.version_info >= (3, 0):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

API_TOKEN = os.getenv("API_TOKEN", "").strip()
MONGO_URI = os.getenv("MONGO_URI", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "0") or 0)
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()
TARGET_GROUP_ID_ENV = os.getenv("TARGET_GROUP_ID", "").strip()
PORT = int(os.getenv("PORT", "5000"))

if not API_TOKEN:
    raise RuntimeError("API_TOKEN is required")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI is required")

START_TIME = datetime.utcnow()

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
    settings_col.update_one({"_id": BOT_GENERAL_SETTINGS_ID}, {"$setOnInsert": {"_id": BOT_GENERAL_SETTINGS_ID, "status": "active", "emergency_flags": DEFAULT_EMERGENCY_FLAGS, "start_text": DEFAULT_START_TEXT, "info_text": DEFAULT_INFO_TEXT, "dev_text": DEFAULT_DEV_TEXT, "guide_text": DEFAULT_GUIDE_TEXT, "sci_text": DEFAULT_SCI_TEXT, "last_announcement": "", "target_group_id": TARGET_GROUP_ID_ENV or None}}, upsert=True)
    settings_col.update_one({"_id": ACADEMIC_STRUCTURE_ID}, {"$setOnInsert": {"_id": ACADEMIC_STRUCTURE_ID, "data": ACADEMIC_STRUCTURE_DEFAULT}}, upsert=True)

_ensure_bootstrap()

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

def log_action(admin_id: int, action_type: str, details: str) -> None:
    try:
        user = users_col.find_one({"chat_id": admin_id}) or {}
        action_logs_col.insert_one({"admin_id": admin_id, "admin_name": user.get("first_name", "Admin"), "action": action_type, "details": details, "timestamp": now_utc()})
    except Exception:
        pass

def is_owner(chat_id: int) -> bool:
    return chat_id == SUPER_ADMIN_ID

def is_admin(chat_id: int) -> bool:
    if is_owner(chat_id):
        return True
    adm = admins_col.find_one({"id": chat_id, "active": True})
    return bool(adm and adm.get("type") in ["global", "super"])

def is_any_admin(chat_id: int) -> bool:
    if is_owner(chat_id):
        return True
    return admins_col.find_one({"id": chat_id, "active": True}) is not None

def get_admin_permissions(chat_id: int) -> List[str]:
    if is_owner(chat_id):
        return ["all"]
    adm = admins_col.find_one({"id": chat_id, "active": True})
    return adm.get("permissions", []) if adm else []

def has_permission(chat_id: int, current_path_str: str) -> bool:
    if testing_mode.get(chat_id, False):
        return False
    if is_owner(chat_id):
        return True
    adm = admins_col.find_one({"id": chat_id, "active": True})
    if not adm:
        return False
    if adm.get("type") in ["global", "super"]:
        return True
    for allowed_p in adm.get("allowed_paths", []):
        if current_path_str.startswith(allowed_p) or current_path_str == allowed_p:
            return True
    return False

def get_menu_by_path(path: List[str]) -> Optional[Dict[str, Any]]:
    menu = global_academic_structure
    for segment in path:
        if isinstance(menu, dict) and segment in menu:
            menu = menu[segment]
        else:
            return None
    return menu

def get_path_string(chat_id: int) -> str:
    return " > ".join(user_path.get(chat_id, []))

def reset_modes(chat_id: int, clear_upload: bool = True) -> None:
    if clear_upload:
        upload_mode[chat_id] = False
    add_folder_mode[chat_id] = False
    admin_action_mode[chat_id] = None
    action_payload.pop(chat_id, None)
    broadcast_mode[chat_id] = False

def check_rate_limit(chat_id: int) -> bool:
    now = time.time()
    if chat_id in RATE_LIMIT_DICT and now - RATE_LIMIT_DICT[chat_id] < 0.6:
        return False
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

def notify_subscribers(file_name: str, path_str: str, uploader_id: int) -> None:
    try:
        subs = list(users_col.find({"smart_notifications": True}, {"chat_id": 1}))
        for sub in subs:
            if sub["chat_id"] != uploader_id:
                try:
                    bot.send_message(sub["chat_id"], f"🔔 وصول ملف أكاديمي جديد:\n• {file_name}\n📁 {path_str}")
                except Exception:
                    pass
    except Exception:
        pass

def split_display_text(text: str) -> str:
    return text.split(" ", 1)[1].strip() if " " in text else text.strip()

def search_file_fallback(query_text: str, current_path: str = "") -> List[Dict[str, Any]]:
    if current_path:
        q1 = {"menu_path": {"$regex": f"^{re.escape(current_path)}"}, "$or": [{"name": {"$regex": re.escape(query_text), "$options": "i"}}, {"caption": {"$regex": re.escape(query_text), "$options": "i"}}]}
        res = list(files_col.find(q1).sort([("sort_order", ASCENDING), ("_id", ASCENDING)]).limit(10))
        if res:
            return res
    q2 = {"$or": [{"name": {"$regex": re.escape(query_text), "$options": "i"}}, {"caption": {"$regex": re.escape(query_text), "$options": "i"}}, {"menu_path": {"$regex": re.escape(query_text), "$options": "i"}}]}
    return list(files_col.find(q2).sort([("sort_order", ASCENDING), ("_id", ASCENDING)]).limit(15))

def rename_folder_recursive(old_full: str, new_full: str) -> None:
    for f in files_col.find({"menu_path": {"$regex": f"^{re.escape(old_full)}"}}):
        files_col.update_one({"_id": f["_id"]}, {"$set": {"menu_path": f["menu_path"].replace(old_full, new_full, 1)}})
    for d in folders_col.find({"parent_path": {"$regex": f"^{re.escape(old_full)}"}}):
        folders_col.update_one({"_id": d["_id"]}, {"$set": {"parent_path": d["parent_path"].replace(old_full, new_full, 1)}})

def get_target_group_id() -> Optional[int]:
    tg = get_settings().get("target_group_id")
    if tg is None or tg == "":
        return None
    try:
        return int(tg)
    except Exception:
        return None

def get_file_ratings(file_id: str) -> Tuple[float, int]:
    docs = list(ratings_col.find({"file_id": file_id}, {"score": 1}))
    if not docs:
        return 0.0, 0
    total = sum(int(d.get("score", 0)) for d in docs)
    cnt = len(docs)
    return total / cnt, cnt

def system_counts_message() -> str:
    u_docs = list(users_col.find({}, {"chat_id": 1, "first_name": 1, "username": 1}))
    lines = [f"📊 إجمالي المشتركين: {len(u_docs)}", ""]
    for u in u_docs[:120]:
        lines.append(f"• {u.get('first_name', '-') } | {u.get('username', '-') or '-'} | `{u.get('chat_id', '-')}`")
    if len(u_docs) > 120:
        lines.append("")
        lines.append(f"… وتم إخفاء {len(u_docs) - 120} مشترك إضافي لتخفيف الرسالة.")
    return "\n".join(lines)

def render_path_header(path_str: str) -> str:
    return f"📂 المسار الحالي:\n`{path_str or 'الرئيسية'}`"

def get_ai_response(prompt: str, chat_id: int) -> str:
    cached = kb_col.find_one({"question": prompt})
    if cached:
        system_stats["cache_hits_today"] += 1
        kb_col.update_one({"_id": cached["_id"]}, {"$inc": {"hits": 1}, "$set": {"last_used": now_utc()}})
        return cached.get("answer", "")
    history = ai_memory.get(chat_id, [])[-3:]
    clean_prompt = "أنت مساعد أكاديمي مختصر ودقيق. أجب بالعربية وبأسلوب واضح:\n\n"
    for item in history:
        clean_prompt += f"س: {item['q']}\nج: {item['a']}\n"
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
            except Exception:
                continue
    for backup_model in ["openai", "llama", "mistral"]:
        try:
            url = f"https://text.pollinations.ai/{requests.utils.quote(clean_prompt)}?model={backup_model}&seed=42"
            res = requests.get(url, timeout=12)
            if res.status_code == 200 and res.text.strip():
                ans = res.text.strip()
                kb_col.insert_one({"question": prompt, "answer": ans, "hits": 1, "last_used": now_utc()})
                system_stats["ai_queries_today"] += 1
                return ans
        except Exception:
            continue
    return "🤖 نعتذر، هناك ضغط حالياً. يرجى إعادة إرسال استفسارك."

def schedule_batch_finalize(chat_id: int, media_group_id: str, path_str: str) -> None:
    def finalize():
        try:
            batch = upload_batches.pop(media_group_id, [])
            if not batch:
                return
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
                notify_subscribers(f"دفعة ملفات جديدة ({added})", path_str, chat_id)
        except Exception as e:
            logging.error(f"Batch finalize error: {e}")
    old_timer = upload_batch_watchers.get(media_group_id)
    if old_timer:
        try:
            old_timer.cancel()
        except Exception:
            pass
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
        if has_perm and not testing_mode.get(chat_id, False):
            markup.add(InlineKeyboardButton("✏️ تسمية", callback_data=f"rn_{file_id_str}"), InlineKeyboardButton("🔄 استبدال", callback_data=f"rp_{file_id_str}"))
            markup.add(InlineKeyboardButton("🗑️ حذف", callback_data=f"dl_{file_id_str}"), InlineKeyboardButton("📦 نقل", callback_data=f"mv_{file_id_str}"))
            markup.add(InlineKeyboardButton("🔼 للأعلى", callback_data=f"up_{file_id_str}"), InlineKeyboardButton("🔽 للأسفل", callback_data=f"dn_{file_id_str}"))
            markup.add(InlineKeyboardButton("📌 تثبيت", callback_data=f"pn_{file_id_str}"))
            markup.add(InlineKeyboardButton("📢 نشر في الجروب", callback_data=f"sh_{file_id_str}"))
        markup.add(InlineKeyboardButton("🔗 مشاركة", url=share_url), InlineKeyboardButton("📂 عرض المقرر", url=deep_folder_url))
        markup.add(InlineKeyboardButton("⭐ تقييم", callback_data=f"rt_{file_id_str}"), InlineKeyboardButton("❤️ مفضلة", callback_data=f"fv_{file_id_str}"))
        markup.add(InlineKeyboardButton("💡 ملفات من نفس المقرر", callback_data=f"rl_{file_id_str}"))
        file_type = res.get("type", "document")
        file_id = res.get("file_id")
        file_name = res.get("name", "وثيقة أكاديمية")
        caption = res.get("caption") or file_name
        up_date = res.get("upload_date", now_utc())
        if not isinstance(up_date, datetime):
            up_date = now_utc()
        avg_rt, rt_cnt = get_file_ratings(file_id_str)
        caption = f"{caption}\n\n📅 التاريخ: {up_date.strftime('%Y-%m-%d')}\n👤 بواسطة: {res.get('uploader_name', 'المنصة')}\n🔻 مرات الاستدعاء: {res.get('downloads', 0)}\n⭐ التقييم: {avg_rt:.1f}/10 ({rt_cnt})"
        if file_type == "text":
            bot.send_message(chat_id, res.get("content", file_name), reply_markup=markup)
        elif file_type == "photo" and file_id:
            bot.send_photo(chat_id, file_id, caption=caption, reply_markup=markup)
        elif file_id:
            bot.send_document(chat_id, file_id, caption=caption, reply_markup=markup)
        else:
            bot.send_message(chat_id, "❌ تنبيه: الملف غير متواجد بخوادم تيليجرام.", reply_markup=markup)
    except Exception as e:
        logging.error(f"Send File Error: {e}")
        try:
            bot.send_message(chat_id, f"❌ حدث خطأ عند عرض الملف: {e}")
        except Exception:
            pass

SPECIAL_PATHS = {"__STUDENT_FEATURES__": "STUDENT_FEATURES", "__FAVORITES__": "FAVORITES", "__SUPER_ADMIN_PANEL__": "SUPER_ADMIN_PANEL", "__GLOBAL_ADMIN_PANEL__": "GLOBAL_ADMIN_PANEL", "__MANAGE_ADMINS__": "MANAGE_ADMINS", "__ADMIN_PERMISSIONS__": "ADMIN_PERMISSIONS", "__TEXTS_PANEL__": "TEXTS_PANEL", "__EMERGENCY_PANEL__": "EMERGENCY_PANEL", "__LOGS_PANEL__": "LOGS_PANEL", "__STATS_PANEL__": "STATS_PANEL", "__GUIDE_PANEL__": "GUIDE_PANEL", "__SCI_PANEL__": "SCI_PANEL"}

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
        user_data = users_col.find_one({"chat_id": chat_id}) or {}
        notif_btn = "🔕 إلغاء الإشعارات" if user_data.get("smart_notifications") else "🔔 تفعيل الإشعارات"
        markup.add(KeyboardButton("🤖 المساعد الذكي (AI)"), KeyboardButton("🔍 بحث عن ملف"))
        markup.add(KeyboardButton("🔥 الملفات الأكثر شعبية"), KeyboardButton("🆕 تحديثات اليوم"))
        markup.add(KeyboardButton("📢 إعلانات الدفعة"), KeyboardButton("⭐ ملفاتي المفضلة"))
        markup.add(KeyboardButton(notif_btn))
        markup.add(KeyboardButton("🔙 الرجوع للقائمة الرئيسية"))
        bot.send_message(chat_id, "🌟 *ميزات الطالب:*", reply_markup=markup, parse_mode="Markdown")
        return
    if path_str == "FAVORITES":
        u_data = users_col.find_one({"chat_id": chat_id}) or {}
        favs = u_data.get("favorites", [])
        markup.add(KeyboardButton("🔙 الرجوع للقائمة الرئيسية"))
        bot.send_message(chat_id, "⭐ *المفضلة:*", reply_markup=markup, parse_mode="Markdown")
        if not favs:
            bot.send_message(chat_id, "لا توجد عناصر مفضلة بعد.")
            return
        for fav in favs:
            if isinstance(fav, str) and fav.startswith("path:"):
                markup.add(KeyboardButton(f"📁 {fav.replace('path:', '', 1)}"))
        for fav in favs:
            if isinstance(fav, str) and not fav.startswith("path:"):
                try:
                    f_doc = files_col.find_one({"_id": ObjectId(fav)})
                    if f_doc:
                        send_file_to_user(chat_id, f_doc, False)
                except Exception:
                    continue
        bot.send_message(chat_id, "يمكنك فتح الملف المفضل من بطاقته، أو استخدام المجلدات المفضلة أعلاه.")
        return
    if path_str == "SUPER_ADMIN_PANEL":
        markup.add("👥 إدارة المشرفين", "🔑 صلاحيات المشرفين")
        markup.add("📈 إحصائيات النظام", "📊 حالة النظام")
        markup.add("🚨 وضع الطوارئ", "📝 سجل العمليات")
        markup.add("📊 نشاط المشرفين", "🔍 كشف الملفات المكررة")
        markup.add("💾 النسخ الاحتياطي اليدوي", "✏️ تعديل نصوص البوت")
        markup.add("📢 إدارة الإعلانات", "🏷️ إدارة الأرشفة")
        markup.add("⭐️ التقييمات", "📊 إحصائيات المقررات")
        markup.add("🛠️ إدارة المشرف المخصص")
        markup.add("🔙 الرجوع للقائمة الرئيسية")
        bot.send_message(chat_id, "👑 *لوحة المشرف الرئيسي:*", reply_markup=markup, parse_mode="Markdown")
        return
    if path_str == "GLOBAL_ADMIN_PANEL":
        perms = get_admin_permissions(chat_id)
        if "all" in perms or "stats" in perms:
            markup.add("📊 حالة النظام", "📈 إحصائيات النظام")
        if "all" in perms or "broadcast" in perms:
            markup.add("📢 إدارة الإعلانات")
        if "all" in perms or "archives" in perms:
            markup.add("🏷️ إدارة الأرشفة")
        if "all" in perms or "courses_stats" in perms:
            markup.add("📊 إحصائيات المقررات")
        if "all" in perms or "texts" in perms:
            markup.add("✏️ تعديل نصوص البوت")
        if "all" in perms or "logs" in perms:
            markup.add("📝 سجل العمليات")
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
        markup.add("🔙 الرجوع للقائمة الرئيسية")
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
    if path_str == "SCI_PANEL":
        markup.add("✏️ تعديل اللجنة العلمية" if is_owner(chat_id) or "texts" in get_admin_permissions(chat_id) or "all" in get_admin_permissions(chat_id) else "🔙 الرجوع للقائمة الرئيسية")
        markup.add("🔙 الرجوع للقائمة الرئيسية")
        bot.send_message(chat_id, get_settings().get("sci_text", DEFAULT_SCI_TEXT), reply_markup=markup)
        return
    if isinstance(current_menu, dict):
        for key in current_menu.keys():
            markup.add(KeyboardButton(key))
    for db_folder in folders_col.find({"parent_path": path_str}).sort([("sort_order", ASCENDING), ("folder_name", ASCENDING)]):
        markup.add(KeyboardButton(f"📁 {db_folder['folder_name']}"))
    for db_file in files_col.find({"menu_path": path_str}).sort([("sort_order", ASCENDING), ("name", ASCENDING)]).limit(80):
        icon = "📌" if db_file.get("type") == "text" else "🖼️" if db_file.get("type") == "photo" else "📄"
        markup.add(KeyboardButton(f"{icon} {db_file['name']}"))
    if path_str in global_academic_structure.keys():
        markup.add(KeyboardButton("🔙 الرجوع للقائمة الرئيسية"))
    else:
        markup.add(KeyboardButton("🔙 الرجوع للقائمة السابقة"), KeyboardButton("🔝 القائمة الرئيسية"))
    if has_permission(chat_id, path_str):
        markup.add(KeyboardButton("➕ إضافة ملف/نص"), KeyboardButton("📂 إضافة مجلد"))
        if path_str not in ["", "STUDENT_FEATURES", "FAVORITES", "SUPER_ADMIN_PANEL", "GLOBAL_ADMIN_PANEL", "MANAGE_ADMINS", "ADMIN_PERMISSIONS", "TEXTS_PANEL", "EMERGENCY_PANEL", "LOGS_PANEL", "STATS_PANEL", "GUIDE_PANEL", "SCI_PANEL"]:
            markup.add(KeyboardButton("✏️ إعادة تسمية هذا القسم"), KeyboardButton("🗑️ حذف هذا القسم"))
            markup.add(KeyboardButton("🔼 نقل مجلد للأعلى"), KeyboardButton("🔽 نقل مجلد للأسفل"))
        if is_owner(chat_id):
            markup.add(KeyboardButton("🔗 ربط هاشتاج بالقسم"))
    bot.send_message(chat_id, render_path_header(path_str), reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=["start"])
def start_command(message):
    chat_id = message.chat.id
    user_data = users_col.find_one({"chat_id": chat_id})
    if user_data and user_data.get("blocked"):
        bot.send_message(chat_id, "🚫 عذراً، تم حظرك وتقييد وصولك للأرشيف.")
        return
    settings = get_settings()
    if settings.get("status") == "inactive" and not is_any_admin(chat_id):
        bot.send_message(chat_id, "🚧 البوت حالياً تحت التحديث والصيانة. نعود إليكم قريباً.")
        return
    if settings.get("emergency_flags", {}).get("all", False) and not is_any_admin(chat_id):
        bot.send_message(chat_id, "🚧 الخدمة تحت التحديث والصيانة حالياً.")
        return
    first_name = (message.from_user.first_name if message.from_user else "") or "أيها الطالب الطموح"
    ensure_user(chat_id, first_name, message.from_user.username if message.from_user else None)
    command_args = (message.text or "").split()
    if len(command_args) > 1:
        param = command_args[1].strip()
        if param.startswith("folder_"):
            try:
                f_obj = files_col.find_one({"_id": ObjectId(param.replace("folder_", ""))})
                if f_obj and f_obj.get("menu_path"):
                    user_path[chat_id] = f_obj["menu_path"].split(" > ")
                    bot.send_message(chat_id, f"📂 تم توجيهك إلى المسار:\n`{f_obj['menu_path']}`", parse_mode="Markdown")
                    show_menu(chat_id)
                    return
            except Exception:
                pass
        else:
            try:
                f_obj = files_col.find_one({"_id": ObjectId(param)})
                if f_obj:
                    files_col.update_one({"_id": f_obj["_id"]}, {"$inc": {"downloads": 1}})
                    bot.send_message(chat_id, "📥 جاري سحب الملف المطلوب...")
                    send_file_to_user(chat_id, f_obj, has_permission(chat_id, f_obj["menu_path"]))
                    return
            except Exception:
                pass
    user_path[chat_id] = []
    reset_modes(chat_id)
    testing_mode[chat_id] = False
    bot.send_message(chat_id, get_settings().get("start_text", DEFAULT_START_TEXT).replace("{first_name}", first_name))
    show_menu(chat_id)

@bot.message_handler(commands=["info"])
def info_command_handler(message):
    bot.send_message(message.chat.id, get_settings().get("info_text", DEFAULT_INFO_TEXT))

@bot.message_handler(commands=["auth"])
def auth_command(message):
    if message.chat.type in ["group", "supergroup"] and message.from_user and message.from_user.id == SUPER_ADMIN_ID:
        auth_groups_col.update_one({"chat_id": message.chat.id}, {"$set": {"title": message.chat.title, "authenticated_at": now_utc()}}, upsert=True)
        bot.reply_to(message, "✅ تم اعتماد هذه المجموعة رسمياً.")

@bot.message_handler(commands=["unauth"])
def unauth_command(message):
    if message.chat.type in ["group", "supergroup"] and message.from_user and message.from_user.id == SUPER_ADMIN_ID:
        auth_groups_col.delete_one({"chat_id": message.chat.id})
        bot.reply_to(message, "⛔ تم سحب الاعتماد.")

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
    if not check_rate_limit(chat_id):
        return
    system_stats["requests_24h"] += 1
    user_data = users_col.find_one({"chat_id": chat_id})
    if user_data and user_data.get("blocked"):
        return
    settings = get_settings()
    text = message.text if message.content_type == "text" else ""
    path_str = get_path_string(chat_id)
    mode = admin_action_mode.get(chat_id)
    if message.chat.type in ["group", "supergroup"]:
        try:
            if message.content_type != "text":
                auto_archive_handler_logic(message)
        except Exception:
            pass
        if message.content_type != "text" or not text.startswith("/"):
            return
    if text == "🛑 إلغاء الأمر":
        reset_modes(chat_id)
        bot.send_message(chat_id, "✅ تم الإلغاء.")
        show_menu(chat_id)
        return
    nav_buttons = ["🔝 القائمة الرئيسية", "🔙 الرجوع للقائمة السابقة", "🔙 الرجوع للقائمة الرئيسية", "🌟 ميزات الطالب", "📖 دليل القسم", "⭐ ملفاتي المفضلة", "📞 التواصل مع المشرف العام", "👑 لوحة المشرف الرئيسي", "🛡️ لوحة المشرف العام", "👥 إدارة المشرفين", "🔑 صلاحيات المشرفين", "✏️ تعديل نصوص البوت", "🚨 وضع الطوارئ", "📝 سجل العمليات", "📈 إحصائيات النظام", "📊 حالة النظام", "📊 إحصائيات المقررات", "⭐️ التقييمات"] + list(global_academic_structure.keys())
    if text in nav_buttons:
        if mode not in ["navigate_to_assign", "move_file_dest"]:
            reset_modes(chat_id)
        if text in ["🔝 القائمة الرئيسية", "🔙 الرجوع للقائمة الرئيسية"]:
            user_path[chat_id] = []
        elif text == "🔙 الرجوع للقائمة السابقة" and user_path.get(chat_id):
            user_path[chat_id].pop()
        elif text in global_academic_structure.keys():
            user_path[chat_id] = [text]
        elif text == "🌟 ميزات الطالب":
            user_path[chat_id] = ["STUDENT_FEATURES"]
        elif text == "⭐ ملفاتي المفضلة":
            user_path[chat_id] = ["FAVORITES"]
        elif text == "👑 لوحة المشرف الرئيسي" and is_owner(chat_id):
            user_path[chat_id] = ["SUPER_ADMIN_PANEL"]
        elif text == "🛡️ لوحة المشرف العام" and is_admin(chat_id):
            user_path[chat_id] = ["GLOBAL_ADMIN_PANEL"]
        elif text == "👥 إدارة المشرفين" and is_owner(chat_id):
            user_path[chat_id] = ["MANAGE_ADMINS"]
        elif text == "🔑 صلاحيات المشرفين" and is_owner(chat_id):
            user_path[chat_id] = ["ADMIN_PERMISSIONS"]
        elif text == "✏️ تعديل نصوص البوت" and (is_owner(chat_id) or "texts" in get_admin_permissions(chat_id) or "all" in get_admin_permissions(chat_id)):
            user_path[chat_id] = ["TEXTS_PANEL"]
        elif text == "🚨 وضع الطوارئ" and (is_owner(chat_id) or "emergency" in get_admin_permissions(chat_id) or "all" in get_admin_permissions(chat_id)):
            user_path[chat_id] = ["EMERGENCY_PANEL"]
        elif text == "📝 سجل العمليات" and (is_owner(chat_id) or "logs" in get_admin_permissions(chat_id) or "all" in get_admin_permissions(chat_id)):
            user_path[chat_id] = ["LOGS_PANEL"]
        elif text in ["📈 إحصائيات النظام", "📊 حالة النظام", "📊 إحصائيات المقررات", "⭐️ التقييمات"] and (is_owner(chat_id) or "stats" in get_admin_permissions(chat_id) or "courses_stats" in get_admin_permissions(chat_id) or "all" in get_admin_permissions(chat_id)):
            user_path[chat_id] = ["STATS_PANEL"]
        elif text == "📖 دليل القسم":
            user_path[chat_id] = ["GUIDE_PANEL"]
        elif text == "📞 التواصل مع المشرف العام":
            emit_contact_card(chat_id)
            return
        show_menu(chat_id)
        return
    if text == "📞 التواصل مع المشرف العام":
        emit_contact_card(chat_id)
        return
    if text == "اللجنة العلمية" and path_str == "🌱 مستوى أول":
        bot.send_message(chat_id, get_settings().get("sci_text", DEFAULT_SCI_TEXT))
        return
    if text == "🤖 المساعد الذكي (AI)":
        if settings.get("emergency_flags", {}).get("ai", False) and not is_any_admin(chat_id):
            bot.send_message(chat_id, "🚧 المساعد الذكي معطل حالياً للصيانة.")
            return
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "ai_chat"
        ai_memory.setdefault(chat_id, [])
        bot.send_message(chat_id, "🤖 أرسل سؤالك الآن:")
        return
    if mode == "ai_chat" and text:
        if len(ai_memory.get(chat_id, [])) >= 7 and not is_any_admin(chat_id):
            bot.send_message(chat_id, "🛑 لقد استنفدت حصتك الحالية.")
            reset_modes(chat_id)
            show_menu(chat_id)
            return
        bot.send_message(chat_id, "⏳ جاري التفكير...")
        ans = get_ai_response(text, chat_id)
        ai_memory[chat_id].append({"q": text, "a": ans})
        ai_memory[chat_id] = ai_memory[chat_id][-3:]
        bot.send_message(chat_id, ans)
        reset_modes(chat_id)
        show_menu(chat_id)
        return
    if text == "🔍 بحث عن ملف":
        if settings.get("emergency_flags", {}).get("search", False) and not is_any_admin(chat_id):
            bot.send_message(chat_id, "🚧 البحث معطل حالياً.")
            return
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "search_exec"
        bot.send_message(chat_id, "🔍 أرسل كلمة البحث:")
        return
    if mode == "search_exec" and text:
        results = search_file_fallback(text, path_str if path_str else "")
        if results:
            bot.send_message(chat_id, f"🔍 وجدنا {len(results)} نتيجة:")
            for item in results:
                send_file_to_user(chat_id, item, has_permission(chat_id, item.get("menu_path", "")))
        else:
            bot.send_message(chat_id, "❌ لم نجد مطابقة.")
        reset_modes(chat_id)
        show_menu(chat_id)
        return
    if text == "📢 إعلانات الدفعة":
        ann = settings.get("last_announcement") or "لا توجد إعلانات حالياً."
        bot.send_message(chat_id, f"📢 *إعلان الدفعة:*\n\n{ann}", parse_mode="Markdown")
        return
    if text == "🔥 الملفات الأكثر شعبية":
        pop = list(files_col.find({"downloads": {"$gt": 0}}).sort("downloads", DESCENDING).limit(5))
        if pop:
            bot.send_message(chat_id, "🔥 *أشهر الملفات:*", parse_mode="Markdown")
            for p in pop:
                send_file_to_user(chat_id, p, False)
        else:
            bot.send_message(chat_id, "لا إحصائيات بعد.")
        return
    if text == "🆕 تحديثات اليوم":
        rec = list(files_col.find({"upload_date": {"$gte": now_utc() - timedelta(days=1)}}).sort("upload_date", DESCENDING).limit(10))
        if rec:
            bot.send_message(chat_id, "🆕 *أحدث الملفات:*", parse_mode="Markdown")
            for r in rec:
                send_file_to_user(chat_id, r, False)
        else:
            bot.send_message(chat_id, "لا توجد ملفات جديدة اليوم.")
        return
    if text in ["🔔 تفعيل الإشعارات", "🔕 إلغاء الإشعارات"]:
        users_col.update_one({"chat_id": chat_id}, {"$set": {"smart_notifications": text == "🔔 تفعيل الإشعارات"}})
        bot.send_message(chat_id, "✅ تم التحديث.")
        show_menu(chat_id)
        return
    if text == "⭐ ملفاتي المفضلة":
        user_path[chat_id] = ["FAVORITES"]
        show_menu(chat_id)
        return
    if text == "👤 عرض كمستخدم" and is_any_admin(chat_id):
        testing_mode[chat_id] = True
        user_path[chat_id] = []
        bot.send_message(chat_id, "👀 تم تفعيل العرض كمستخدم.")
        show_menu(chat_id)
        return
    if text == "🛑 إنهاء العرض كمستخدم" and testing_mode.get(chat_id, False):
        testing_mode[chat_id] = False
        user_path[chat_id] = []
        bot.send_message(chat_id, "💼 تم إنهاء العرض كمستخدم.")
        show_menu(chat_id)
        return
    if text == "📈 إحصائيات النظام" and (is_owner(chat_id) or "stats" in get_admin_permissions(chat_id) or "all" in get_admin_permissions(chat_id)):
        bot.send_message(chat_id, system_counts_message())
        return
    if text == "📊 حالة النظام" and (is_owner(chat_id) or "stats" in get_admin_permissions(chat_id) or "all" in get_admin_permissions(chat_id)):
        u_c = users_col.count_documents({})
        f_c = files_col.count_documents({})
        d_c = folders_col.count_documents({})
        db_size = db.command("dbstats").get("dataSize", 0) / (1024 * 1024)
        ai_ratio = (system_stats["cache_hits_today"] / (system_stats["ai_queries_today"] + system_stats["cache_hits_today"] + 0.001)) * 100
        try:
            with open("/proc/loadavg", "r") as f:
                cpu = f.read().split()[0]
            with open("/proc/meminfo", "r") as f:
                mem = f.read()
            m_tot = int(re.search(r"MemTotal:\s+(\d+)", mem).group(1))
            m_av = int(re.search(r"MemAvailable:\s+(\d+)", mem).group(1))
            ram = f"{(m_tot - m_av) / 1024:.1f}/{m_tot / 1024:.1f} MB"
        except Exception:
            cpu, ram = "N/A", "N/A"
        st = f"📊 *حالة النظام:*\n👥 المستخدمين: {u_c}\n📁 الملفات: {f_c}\n📂 المجلدات: {d_c}\n💾 حجم DB التقريبي: {db_size:.2f} MB\n🤖 AI queries: {system_stats['ai_queries_today']} | ⚡ cache: {system_stats['cache_hits_today']} ({ai_ratio:.1f}% توفير)\n🔄 طلبات 24 ساعة: {system_stats['requests_24h']}\n⚙️ CPU: {cpu} | 🧠 RAM: {ram}\n⏱️ وقت التشغيل: {str(now_utc() - START_TIME).split('.')[0]}"
        bot.send_message(chat_id, st, parse_mode="Markdown")
        return
    if text == "💾 النسخ الاحتياطي اليدوي" and is_owner(chat_id):
        bot.send_message(chat_id, "⏳ جاري تصدير البيانات...")
        bkp = {"files": list(files_col.find({}, {"_id": 0})), "folders": list(folders_col.find({}, {"_id": 0})), "admins": list(admins_col.find({}, {"_id": 0})), "settings": list(settings_col.find({}, {"_id": 0}))}
        bio = io.BytesIO(json.dumps(bkp, default=json_util.default, ensure_ascii=False).encode("utf-8"))
        bio.name = f"DB_Backup_{now_utc().strftime('%Y%m%d_%H%M')}.json"
        bot.send_document(chat_id, bio, caption="💾 نسخة احتياطية JSON")
        return
    if text == "📝 سجل العمليات" and (is_owner(chat_id) or "logs" in get_admin_permissions(chat_id) or "all" in get_admin_permissions(chat_id)):
        logs = list(action_logs_col.find().sort("timestamp", DESCENDING).limit(30))
        if not logs:
            bot.send_message(chat_id, "السجل فارغ.")
            return
        lines = ["📝 *سجل العمليات:*", ""]
        for lg in logs:
            ts = lg.get("timestamp", now_utc())
            if not isinstance(ts, datetime):
                ts = now_utc()
            lines.append(f"• {ts.strftime('%m-%d %H:%M')} | {lg.get('admin_name', '-') } | {lg.get('action', '-')}")
        msg = "\n".join(lines)
        bot.send_message(chat_id, msg[:3900], parse_mode="Markdown")
        return
    if text == "📊 نشاط المشرفين" and is_owner(chat_id):
        agg = list(action_logs_col.aggregate([{"$group": {"_id": "$admin_name", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]))
        if not agg:
            bot.send_message(chat_id, "لا نشاط.")
        else:
            msg = "📊 *نشاط المشرفين:*\n\n" + "\n".join([f"• {x['_id']}: {x['count']} عملية" for x in agg])
            bot.send_message(chat_id, msg, parse_mode="Markdown")
        return
    if text == "🔍 كشف الملفات المكررة" and is_owner(chat_id):
        dups = list(files_col.aggregate([{"$group": {"_id": "$file_id", "count": {"$sum": 1}, "names": {"$push": "$name"}}}, {"$match": {"count": {"$gt": 1}}}]))
        if not dups:
            bot.send_message(chat_id, "✅ لا توجد ملفات مكررة.")
        else:
            msg = "🔍 *ملفات مكررة:*\n\n" + "\n".join([f"• {d.get('names', ['-'])[0]} | {d['count']}" for d in dups[:20]])
            bot.send_message(chat_id, msg, parse_mode="Markdown")
        return
    if text == "📊 إحصائيات المقررات" and (is_owner(chat_id) or "courses_stats" in get_admin_permissions(chat_id) or "all" in get_admin_permissions(chat_id)):
        stats = list(files_col.aggregate([{"$group": {"_id": "$menu_path", "count": {"$sum": 1}, "downloads": {"$sum": "$downloads"}}}, {"$sort": {"downloads": -1}}, {"$limit": 40}]))
        if not stats:
            bot.send_message(chat_id, "لا توجد إحصائيات.")
        else:
            msg = "📊 *إحصائيات المقررات:*\n\n"
            for s in stats:
                msg += f"📁 `{s['_id']}`\n📄 الملفات: {s['count']} | 🔻 التحميلات: {s['downloads']}\n\n"
            bot.send_message(chat_id, msg[:3900], parse_mode="Markdown")
        return
    if text == "⭐️ التقييمات" and (is_owner(chat_id) or "courses_stats" in get_admin_permissions(chat_id) or "all" in get_admin_permissions(chat_id)):
        top = list(ratings_col.aggregate([{"$group": {"_id": "$file_id", "avg": {"$avg": "$score"}, "cnt": {"$sum": 1}}}, {"$sort": {"avg": -1}}, {"$limit": 15}]))
        if not top:
            bot.send_message(chat_id, "لا تقييمات مسجلة بعد.")
        else:
            lines = ["⭐️ *أعلى الملفات تقييماً:*", ""]
            for r in top:
                try:
                    f = files_col.find_one({"_id": ObjectId(r["_id"])})
                    if f:
                        lines.append(f"• {f.get('name', '-')}: {r['avg']:.1f} ({r['cnt']} أصوات)")
                except Exception:
                    continue
            bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")
        return
    if text == "📢 إدارة الإعلانات" and (is_owner(chat_id) or "broadcast" in get_admin_permissions(chat_id) or "all" in get_admin_permissions(chat_id)):
        reset_modes(chat_id)
        broadcast_mode[chat_id] = True
        bot.send_message(chat_id, "📢 أرسل الإعلان الآن:")
        return
    if broadcast_mode.get(chat_id, False) and (is_owner(chat_id) or "broadcast" in get_admin_permissions(chat_id) or "all" in get_admin_permissions(chat_id)):
        broadcast_mode[chat_id] = False
        save_settings({"last_announcement": text or "مرفق إعلاني"})
        sent = 0
        for stu in list(users_col.find({}, {"chat_id": 1})):
            try:
                bot.copy_message(stu["chat_id"], chat_id, message.message_id)
                sent += 1
            except Exception:
                pass
        bot.send_message(chat_id, f"📢 تم إيصال الرسالة إلى {sent} مشترك.")
        log_action(chat_id, "ADD_ANNOUNCEMENT", text[:200] if text else "media")
        show_menu(chat_id)
        return
    if text == "🏷️ إدارة الأرشفة" and (is_owner(chat_id) or "archives" in get_admin_permissions(chat_id) or "all" in get_admin_permissions(chat_id)):
        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add("📋 عرض الهاشتاجات", "🗑️ حذف هاشتاج")
        markup.add("🔗 ربط هاشتاج بالقسم", "🔙 الرجوع للقائمة الرئيسية")
        bot.send_message(chat_id, "🏷️ *إدارة الأرشفة:*", reply_markup=markup, parse_mode="Markdown")
        return
    if text == "📋 عرض الهاشتاجات" and (is_any_admin(chat_id) or is_owner(chat_id)):
        active_tags = list(hashtags_col.find())
        if not active_tags:
            bot.send_message(chat_id, "لا توجد هاشتاجات.")
        else:
            msg = "🏷️ *الهاشتاجات النشطة:*\n\n" + "\n".join([f"🔸 {t['tag']} ⇦ {t['path'].split(' > ')[-1]}" for t in active_tags])
            bot.send_message(chat_id, msg, parse_mode="Markdown")
        return
    if text == "🗑️ حذف هاشتاج" and is_owner(chat_id):
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "del_hashtag"
        bot.send_message(chat_id, "أرسل الهاشتاج المراد حذفه:")
        return
    if mode == "del_hashtag" and text and is_owner(chat_id):
        final_tag = text.strip() if text.strip().startswith("#") else "#" + text.strip()
        hashtags_col.delete_one({"tag": final_tag})
        bot.send_message(chat_id, "✅ تم الحذف.")
        log_action(chat_id, "DELETE_HASHTAG", final_tag)
        reset_modes(chat_id)
        show_menu(chat_id)
        return
    if text == "👥 إدارة المشرفين" and is_owner(chat_id):
        user_path[chat_id] = ["MANAGE_ADMINS"]
        show_menu(chat_id)
        return
    if text == "🔑 صلاحيات المشرفين" and is_owner(chat_id):
        user_path[chat_id] = ["ADMIN_PERMISSIONS"]
        show_menu(chat_id)
        return
    if text == "✏️ تعديل نصوص البوت" and (is_owner(chat_id) or "texts" in get_admin_permissions(chat_id) or "all" in get_admin_permissions(chat_id)):
        user_path[chat_id] = ["TEXTS_PANEL"]
        show_menu(chat_id)
        return
    if text == "🚨 وضع الطوارئ" and (is_owner(chat_id) or "emergency" in get_admin_permissions(chat_id) or "all" in get_admin_permissions(chat_id)):
        user_path[chat_id] = ["EMERGENCY_PANEL"]
        show_menu(chat_id)
        return
    if text == "📝 سجل العمليات" and (is_owner(chat_id) or "logs" in get_admin_permissions(chat_id) or "all" in get_admin_permissions(chat_id)):
        user_path[chat_id] = ["LOGS_PANEL"]
        show_menu(chat_id)
        return
    if text in ["📈 إحصائيات النظام", "📊 حالة النظام", "📊 إحصائيات المقررات", "⭐️ التقييمات"] and (is_owner(chat_id) or "stats" in get_admin_permissions(chat_id) or "courses_stats" in get_admin_permissions(chat_id) or "all" in get_admin_permissions(chat_id)):
        user_path[chat_id] = ["STATS_PANEL"]
        show_menu(chat_id)
        return
    if text == "📖 دليل القسم":
        user_path[chat_id] = ["GUIDE_PANEL"]
        show_menu(chat_id)
        return
    if text == "🟢 الذكاء الاصطناعي" or text == "🔴 الذكاء الاصطناعي" or text == "🟢 الرفع" or text == "🔴 الرفع" or text == "🟢 البحث" or text == "🔴 البحث" or text == "🟢 الإعلانات" or text == "🔴 الإعلانات" or text == "🟢 الخدمة الكلية" or text == "🔴 الخدمة الكلية":
        key = None
        if "الذكاء الاصطناعي" in text:
            key = "ai"
        elif "الرفع" in text:
            key = "upload"
        elif "البحث" in text:
            key = "search"
        elif "الإعلانات" in text:
            key = "ads"
        elif "الخدمة الكلية" in text:
            key = "all"
        if key and (is_owner(chat_id) or "emergency" in get_admin_permissions(chat_id) or "all" in get_admin_permissions(chat_id)):
            flags = dict(get_settings().get("emergency_flags", DEFAULT_EMERGENCY_FLAGS))
            flags[key] = not flags.get(key, False)
            save_settings({"emergency_flags": flags})
            bot.send_message(chat_id, f"✅ تم تحديث وضع الطوارئ: {key} = {flags[key]}")
            log_action(chat_id, "TOGGLE_EMERGENCY", f"{key} -> {flags[key]}")
            show_menu(chat_id)
        return
    if text == "🛑 إيقاف البوت كلياً" and (is_owner(chat_id) or "emergency" in get_admin_permissions(chat_id) or "all" in get_admin_permissions(chat_id)):
        save_settings({"status": "inactive"})
        bot.send_message(chat_id, "✅ تم إيقاف البوت للطلاب.")
        log_action(chat_id, "STOP_SERVICE", "inactive")
        show_menu(chat_id)
        return
    if text == "▶️ تشغيل البوت" and (is_owner(chat_id) or "emergency" in get_admin_permissions(chat_id) or "all" in get_admin_permissions(chat_id)):
        save_settings({"status": "active"})
        bot.send_message(chat_id, "✅ تم تشغيل البوت.")
        log_action(chat_id, "START_SERVICE", "active")
        show_menu(chat_id)
        return
    if text == "🛠️ إدارة المشرف المخصص" and is_owner(chat_id):
        user_path[chat_id] = ["MANAGE_ADMINS"]
        show_menu(chat_id)
        return
    if text == "➕ إضافة مشرف عام" and is_owner(chat_id):
        admin_action_mode[chat_id] = "add_glb"
        bot.send_message(chat_id, "أرسل الآيدي الرقمي للمشرف العام:")
        return
    if mode == "add_glb" and text and is_owner(chat_id):
        try:
            tid = int(text.strip())
            admins_col.update_one({"id": tid}, {"$set": {"id": tid, "type": "global", "permissions": ["all"], "active": True}}, upsert=True)
            bot.send_message(chat_id, "✅ تمت الإضافة.")
            log_action(chat_id, "ADD_ADMIN", f"{tid}")
            reset_modes(chat_id)
            show_menu(chat_id)
        except Exception:
            bot.send_message(chat_id, "❌ أرقام فقط.")
        return
    if text == "➕ إضافة مشرف مخصص لمسار" and is_owner(chat_id):
        admin_action_mode[chat_id] = "navigate_to_assign"
        user_path[chat_id] = []
        bot.send_message(chat_id, "📍 تصفح الأقسام للوصول للمسار ثم اضغط (✅ تعيين مشرف لهذا القسم).")
        show_menu(chat_id)
        return
    if mode == "navigate_to_assign" and text == "✅ تعيين مشرف لهذا القسم" and is_owner(chat_id):
        admin_action_mode[chat_id] = "ask_path_admin_id"
        bot.send_message(chat_id, f"👤 المسار المختار:\n`{path_str}`\nأرسل الآيدي الرقمي للمشرف:", parse_mode="Markdown")
        return
    if mode == "ask_path_admin_id" and text and is_owner(chat_id):
        try:
            tid = int(text.strip())
            admins_col.update_one({"id": tid}, {"$set": {"id": tid, "type": "path", "active": True}, "$addToSet": {"allowed_paths": path_str}}, upsert=True)
            bot.send_message(chat_id, "✅ تم تقييد المشرف على هذا المسار.")
            log_action(chat_id, "ADD_PATH_ADMIN", f"{tid} -> {path_str}")
            reset_modes(chat_id)
            show_menu(chat_id)
        except Exception:
            bot.send_message(chat_id, "❌ الآيدي يجب أن يكون أرقاماً فقط.")
        return
    if text == "✅ تفعيل مشرف" and is_owner(chat_id):
        admin_action_mode[chat_id] = "activate_admin"
        bot.send_message(chat_id, "أرسل آيدي المشرف:")
        return
    if mode == "activate_admin" and text and is_owner(chat_id):
        try:
            tid = int(text.strip())
            admins_col.update_one({"id": tid}, {"$set": {"active": True}}, upsert=True)
            bot.send_message(chat_id, "✅ تم التفعيل.")
            log_action(chat_id, "ACTIVATE_ADMIN", f"{tid}")
            reset_modes(chat_id)
            show_menu(chat_id)
        except Exception:
            bot.send_message(chat_id, "❌ أرقام فقط.")
        return
    if text == "🚫 تعطيل مشرف" and is_owner(chat_id):
        admin_action_mode[chat_id] = "deactivate_admin"
        bot.send_message(chat_id, "أرسل آيدي المشرف:")
        return
    if mode == "deactivate_admin" and text and is_owner(chat_id):
        try:
            tid = int(text.strip())
            if tid == SUPER_ADMIN_ID:
                bot.send_message(chat_id, "❌ لا يمكن تعطيل المشرف الرئيسي.")
            else:
                admins_col.update_one({"id": tid}, {"$set": {"active": False}}, upsert=True)
                bot.send_message(chat_id, "✅ تم التعطيل.")
                log_action(chat_id, "DEACTIVATE_ADMIN", f"{tid}")
            reset_modes(chat_id)
            show_menu(chat_id)
        except Exception:
            bot.send_message(chat_id, "❌ أرقام فقط.")
        return
    if text == "➖ حذف مشرف" and is_owner(chat_id):
        admin_action_mode[chat_id] = "delete_admin"
        bot.send_message(chat_id, "أرسل الآيدي للحذف النهائي:")
        return
    if mode == "delete_admin" and text and is_owner(chat_id):
        try:
            tid = int(text.strip())
            if tid == SUPER_ADMIN_ID:
                bot.send_message(chat_id, "❌ لا يمكن حذف المشرف الرئيسي.")
            else:
                admins_col.delete_one({"id": tid})
                bot.send_message(chat_id, "✅ تم الحذف.")
                log_action(chat_id, "DELETE_ADMIN", f"{tid}")
            reset_modes(chat_id)
            show_menu(chat_id)
        except Exception:
            bot.send_message(chat_id, "❌ أرقام فقط.")
        return
    if text == "🔍 البحث عن مشرف" and is_owner(chat_id):
        admin_action_mode[chat_id] = "search_admin"
        bot.send_message(chat_id, "أرسل الآيدي:")
        return
    if mode == "search_admin" and text and is_owner(chat_id):
        try:
            tid = int(text.strip())
            adm = admins_col.find_one({"id": tid})
            if not adm:
                bot.send_message(chat_id, "❌ غير موجود.")
            else:
                bot.send_message(chat_id, f"👤 النوع: {adm.get('type')}\nنشط: {adm.get('active', True)}\nصلاحيات: {adm.get('permissions', [])}\nمسارات: {adm.get('allowed_paths', [])}")
            reset_modes(chat_id)
            show_menu(chat_id)
        except Exception:
            bot.send_message(chat_id, "❌ أرقام فقط.")
        return
    if text == "🟢 منح صلاحية محددة" and is_owner(chat_id):
        admin_action_mode[chat_id] = "grant_perm_admin"
        bot.send_message(chat_id, "أرسل آيدي المشرف:")
        return
    if mode == "grant_perm_admin" and text and is_owner(chat_id):
        try:
            tid = int(text.strip())
            action_payload[chat_id] = tid
            admin_action_mode[chat_id] = "grant_perm_choice"
            m = ReplyKeyboardMarkup(resize_keyboard=True)
            m.add("إعلانات", "إحصائيات")
            m.add("طوارئ", "تعديل نصوص")
            m.add("أرشفة", "سجل العمليات")
            m.add("إحصائيات المقررات", "النسخ الاحتياطي")
            bot.send_message(chat_id, "اختر الصلاحية:", reply_markup=m)
        except Exception:
            bot.send_message(chat_id, "❌ أرقام فقط.")
        return
    if mode == "grant_perm_choice" and text and is_owner(chat_id):
        p_map = {"إعلانات": "broadcast", "إحصائيات": "stats", "طوارئ": "emergency", "تعديل نصوص": "texts", "أرشفة": "archives", "سجل العمليات": "logs", "إحصائيات المقررات": "courses_stats", "النسخ الاحتياطي": "backup"}
        if text in p_map:
            admins_col.update_one({"id": action_payload.get(chat_id)}, {"$addToSet": {"permissions": p_map[text]}}, upsert=True)
            bot.send_message(chat_id, "✅ تم المنح.")
            log_action(chat_id, "GRANT_PERMISSION", f"{action_payload.get(chat_id)} -> {p_map[text]}")
            reset_modes(chat_id)
            show_menu(chat_id)
        return
    if text == "🔴 سحب صلاحية محددة" and is_owner(chat_id):
        admin_action_mode[chat_id] = "revoke_perm_admin"
        bot.send_message(chat_id, "أرسل آيدي المشرف:")
        return
    if mode == "revoke_perm_admin" and text and is_owner(chat_id):
        try:
            tid = int(text.strip())
            action_payload[chat_id] = tid
            admin_action_mode[chat_id] = "revoke_perm_choice"
            m = ReplyKeyboardMarkup(resize_keyboard=True)
            m.add("إعلانات", "إحصائيات")
            m.add("طوارئ", "تعديل نصوص")
            m.add("أرشفة", "سجل العمليات")
            m.add("إحصائيات المقررات", "النسخ الاحتياطي")
            bot.send_message(chat_id, "اختر الصلاحية لسحبها:", reply_markup=m)
        except Exception:
            bot.send_message(chat_id, "❌ أرقام فقط.")
        return
    if mode == "revoke_perm_choice" and text and is_owner(chat_id):
        p_map = {"إعلانات": "broadcast", "إحصائيات": "stats", "طوارئ": "emergency", "تعديل نصوص": "texts", "أرشفة": "archives", "سجل العمليات": "logs", "إحصائيات المقررات": "courses_stats", "النسخ الاحتياطي": "backup"}
        if text in p_map:
            admins_col.update_one({"id": action_payload.get(chat_id)}, {"$pull": {"permissions": p_map[text]}}, upsert=True)
            bot.send_message(chat_id, "✅ تم السحب.")
            log_action(chat_id, "REVOKE_PERMISSION", f"{action_payload.get(chat_id)} -> {p_map[text]}")
            reset_modes(chat_id)
            show_menu(chat_id)
        return
    if text == "📋 عرض صلاحيات المشرف" and is_owner(chat_id):
        admin_action_mode[chat_id] = "view_permissions"
        bot.send_message(chat_id, "أرسل آيدي المشرف:")
        return
    if mode == "view_permissions" and text and is_owner(chat_id):
        try:
            tid = int(text.strip())
            adm = admins_col.find_one({"id": tid})
            bot.send_message(chat_id, f"صلاحياته: {adm.get('permissions', [])}" if adm else "❌ غير موجود.")
            reset_modes(chat_id)
            show_menu(chat_id)
        except Exception:
            bot.send_message(chat_id, "❌ أرقام فقط.")
        return
    if text == "➕ إضافة ملف/نص" and has_permission(chat_id, path_str):
        if settings.get("emergency_flags", {}).get("upload", False) and not is_any_admin(chat_id):
            bot.send_message(chat_id, "🚧 الرفع معطل حالياً.")
            return
        reset_modes(chat_id)
        upload_mode[chat_id] = True
        bot.send_message(chat_id, "📥 أرسل الملفات الآن (مفرد أو ألبوم):")
        return
    if text == "📂 إضافة مجلد" and has_permission(chat_id, path_str):
        reset_modes(chat_id)
        add_folder_mode[chat_id] = True
        bot.send_message(chat_id, "📂 اكتب اسم المجلد الجديد:")
        return
    if text == "✏️ إعادة تسمية هذا القسم" and has_permission(chat_id, path_str) and path_str:
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "rename_folder"
        bot.send_message(chat_id, "✏️ أرسل الاسم الجديد للقسم:")
        return
    if text == "🗑️ حذف هذا القسم" and has_permission(chat_id, path_str) and path_str:
        current_name = user_path[chat_id][-1]
        parent_p = " > ".join(user_path[chat_id][:-1]) if len(user_path.get(chat_id, [])) > 1 else ""
        folders_col.delete_one({"parent_path": parent_p, "folder_name": current_name})
        log_action(chat_id, "DELETE_FOLDER", f"{current_name} in {parent_p}")
        user_path[chat_id].pop()
        bot.send_message(chat_id, "🗑️ تم الحذف.")
        show_menu(chat_id)
        return
    if text in ["🔼 نقل مجلد للأعلى", "🔽 نقل مجلد للأسفل"] and has_permission(chat_id, path_str) and path_str:
        current_name = user_path[chat_id][-1]
        parent_p = " > ".join(user_path[chat_id][:-1]) if len(user_path.get(chat_id, [])) > 1 else ""
        fld = folders_col.find_one({"parent_path": parent_p, "folder_name": current_name})
        if fld:
            inc = -10 if "الأعلى" in text else 10
            folders_col.update_one({"_id": fld["_id"]}, {"$inc": {"sort_order": inc}})
            log_action(chat_id, "REORDER_FOLDER", f"{current_name} {inc}")
        show_menu(chat_id)
        return
    if mode == "rename_folder" and text and has_permission(chat_id, path_str) and path_str:
        old_folder_name = user_path[chat_id][-1]
        parent_p_str = " > ".join(user_path[chat_id][:-1]) if len(user_path.get(chat_id, [])) > 1 else ""
        new_folder_name = text.strip()
        folders_col.update_one({"parent_path": parent_p_str, "folder_name": old_folder_name}, {"$set": {"folder_name": new_folder_name}})
        old_full = f"{parent_p_str} > {old_folder_name}" if parent_p_str else old_folder_name
        new_full = f"{parent_p_str} > {new_folder_name}" if parent_p_str else new_folder_name
        rename_folder_recursive(old_full, new_full)
        user_path[chat_id][-1] = new_folder_name
        log_action(chat_id, "RENAME_FOLDER", f"{old_folder_name} -> {new_folder_name}")
        bot.send_message(chat_id, "✅ تم التعديل وتحديث المسارات بأمان.")
        reset_modes(chat_id)
        show_menu(chat_id)
        return
    if mode == "rename_file" and text:
        fid = action_payload.get(chat_id)
        if fid:
            files_col.update_one({"_id": ObjectId(fid)}, {"$set": {"name": text.strip()}})
            log_action(chat_id, "RENAME_FILE", f"{fid} -> {text[:40]}")
            bot.send_message(chat_id, "✅ تم التعديل.")
        reset_modes(chat_id)
        show_menu(chat_id)
        return
    if mode == "replace_file" and message.content_type in ["document", "photo", "video", "audio", "text"]:
        fid = action_payload.get(chat_id)
        if fid:
            doc = build_file_doc(message, path_str)
            if doc["file_id"]:
                update_data = {"type": doc["type"], "file_id": doc["file_id"], "name": doc["name"], "caption": doc["caption"], "menu_path": path_str}
            else:
                update_data = {"type": "text", "content": text, "name": text[:60], "file_id": None, "menu_path": path_str}
            files_col.update_one({"_id": ObjectId(fid)}, {"$set": update_data})
            log_action(chat_id, "REPLACE_FILE", fid)
            bot.send_message(chat_id, "✅ تم الاستبدال.")
        reset_modes(chat_id)
        show_menu(chat_id)
        return
    if add_folder_mode.get(chat_id, False) and text and has_permission(chat_id, path_str):
        folder_name = text.strip()
        folders_col.insert_one(build_folder_doc(folder_name, path_str))
        log_action(chat_id, "ADD_FOLDER", f"{folder_name} in {path_str}")
        bot.send_message(chat_id, f"✅ تم إنشاء: {folder_name}")
        reset_modes(chat_id)
        show_menu(chat_id)
        return
    if upload_mode.get(chat_id, False) and message.content_type == "text" and has_permission(chat_id, path_str):
        files_col.insert_one({"menu_path": path_str, "name": text[:80].strip(), "type": "text", "content": text, "downloads": 0, "sort_order": get_next_sort_order(path_str, "file"), "upload_date": now_utc(), "uploader_id": chat_id, "uploader_name": (message.from_user.first_name if message.from_user else "") or "المنصة"})
        bot.send_message(chat_id, "✅ تم حفظ التلخيص.")
        log_action(chat_id, "ADD_TEXT_FILE", f"{path_str}")
        return
    if message.content_type in ["document", "photo", "video", "audio"] and upload_mode.get(chat_id, False) and has_permission(chat_id, path_str):
        if getattr(message, "media_group_id", None):
            gid = str(message.media_group_id)
            upload_batches.setdefault(gid, [])
            upload_batches[gid].append(message)
            schedule_batch_finalize(chat_id, gid, path_str)
        else:
            doc = build_file_doc(message, path_str)
            if not files_col.find_one({"menu_path": path_str, "file_id": doc["file_id"]}):
                files_col.insert_one(doc)
                bot.reply_to(message, f"✅ تم حفظ: {doc['name']}")
                notify_subscribers(doc["name"], path_str, chat_id)
                log_action(chat_id, "ADD_FILE", f"{doc['name']} in {path_str}")
            else:
                bot.reply_to(message, "⚠️ الملف موجود بالفعل.")
        return
    if text.startswith("📁 "):
        folder_name = text.replace("📁 ", "", 1).strip()
        user_path.setdefault(chat_id, [])
        user_path[chat_id].append(folder_name)
        show_menu(chat_id)
        return
    if text.startswith("📄 ") or text.startswith("📌 ") or text.startswith("🖼️ "):
        ex_name = split_display_text(text)
        f_doc = files_col.find_one({"menu_path": path_str, "name": ex_name})
        if not f_doc:
            f_doc = files_col.find_one({"menu_path": path_str, "name": {"$regex": f"^{re.escape(ex_name)}$", "$options": "i"}})
        if not f_doc:
            results = search_file_fallback(ex_name, path_str)
            f_doc = results[0] if results else None
        if f_doc:
            files_col.update_one({"_id": f_doc["_id"]}, {"$inc": {"downloads": 1}})
            send_file_to_user(chat_id, f_doc, has_permission(chat_id, f_doc.get("menu_path", "")))
        else:
            bot.send_message(chat_id, "❌ لم يتم العثور على الملف.")
        return
    current_menu = get_menu_by_path(user_path.get(chat_id, []))
    if isinstance(current_menu, dict) and text in current_menu:
        user_path.setdefault(chat_id, [])
        user_path[chat_id].append(text)
        show_menu(chat_id)
        return

def auto_archive_handler_logic(message):
    if not auth_groups_col.find_one({"chat_id": message.chat.id}):
        return
    caption = message.caption or ""
    for tag_data in list(hashtags_col.find()):
        if tag_data.get("tag") and tag_data["tag"] in caption:
            doc = build_file_doc(message, tag_data["path"])
            doc["name"] = sanitize_name(doc["name"].replace(tag_data["tag"], "")).strip() or "مؤرشف تلقائياً"
            if doc["file_id"] and not files_col.find_one({"menu_path": doc["menu_path"], "file_id": doc["file_id"]}):
                files_col.insert_one(doc)
                try:
                    bot.reply_to(message, f"🎯 تمت الأرشفة إلى:\n🛡️ {tag_data['path'].split(' > ')[-1]}")
                except Exception:
                    pass
            break

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    chat_id = call.message.chat.id
    data = call.data or ""
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    try:
        if "_" not in data:
            return
        action, obj_id = data.split("_", 1)
        if action == "fv":
            users_col.update_one({"chat_id": chat_id}, {"$addToSet": {"favorites": obj_id}})
            bot.answer_callback_query(call.id, "❤️ تمت إضافته للمفضلة", show_alert=False)
            return
        if action == "cp":
            if is_favorite_path(chat_id, obj_id):
                user_unfavorite_path(chat_id, obj_id)
                bot.send_message(chat_id, "⭐ تم حذف المقرر من المفضلة.")
            else:
                user_favorite_path(chat_id, obj_id)
                bot.send_message(chat_id, "⭐ تم حفظ المقرر في المفضلة.")
            return
        if action == "rt":
            m = InlineKeyboardMarkup(row_width=5)
            btns = [InlineKeyboardButton(str(i), callback_data=f"str_{i}_{obj_id}") for i in range(1, 11)]
            m.add(*btns)
            try:
                bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=m)
            except Exception:
                pass
            return
        if action == "str":
            score, f_id = obj_id.split("_", 1)
            score_i = int(score)
            if score_i < 1 or score_i > 10:
                return
            ratings_col.update_one({"file_id": f_id, "user_id": chat_id}, {"$set": {"score": score_i, "updated_at": now_utc()}}, upsert=True)
            bot.answer_callback_query(call.id, f"⭐ تم حفظ تقييمك: {score_i}/10", show_alert=False)
            try:
                f_doc = files_col.find_one({"_id": ObjectId(f_id)})
                if f_doc:
                    send_file_to_user(chat_id, f_doc, has_permission(chat_id, f_doc.get("menu_path", "")))
            except Exception:
                pass
            return
        if action == "rl":
            f_doc = files_col.find_one({"_id": ObjectId(obj_id)})
            if not f_doc:
                return
            rel = list(files_col.find({"menu_path": f_doc.get("menu_path", ""), "_id": {"$ne": ObjectId(obj_id)}}).sort([("sort_order", ASCENDING), ("_id", ASCENDING)]).limit(4))
            if rel:
                bot.send_message(chat_id, "💡 *ملفات إضافية من نفس المقرر:*", parse_mode="Markdown")
                for r in rel:
                    send_file_to_user(chat_id, r, False)
            else:
                bot.send_message(chat_id, "لا توجد ملفات أخرى في هذا المقرر.")
            return
        if action == "sh":
            if not (is_owner(chat_id) or "broadcast" in get_admin_permissions(chat_id) or "all" in get_admin_permissions(chat_id)):
                bot.send_message(chat_id, "❌ لا تمتلك الصلاحية.")
                return
            target_group_id = get_target_group_id()
            if not target_group_id:
                bot.send_message(chat_id, "❌ لم يتم ضبط target_group_id في الإعدادات.")
                return
            f_doc = files_col.find_one({"_id": ObjectId(obj_id)})
            if not f_doc:
                bot.send_message(chat_id, "❌ الملف غير موجود.")
                return
            send_file_to_user(target_group_id, f_doc, False)
            bot.send_message(chat_id, f"✅ تم نشر الملف إلى المجموعة {target_group_id}.")
            log_action(chat_id, "PUBLISH_FILE", f"{obj_id} -> {target_group_id}")
            return
        f_doc = None
        try:
            f_doc = files_col.find_one({"_id": ObjectId(obj_id)})
        except Exception:
            f_doc = None
        if action in ["rn", "rp", "dl", "mv", "up", "dn", "pn"] and f_doc:
            if not has_permission(chat_id, f_doc.get("menu_path", "")):
                bot.send_message(chat_id, "❌ لا تمتلك الصلاحية.")
                return
            if action == "dl":
                files_col.delete_one({"_id": f_doc["_id"]})
                log_action(chat_id, "DELETE_FILE", f_doc.get("name", obj_id))
                try:
                    bot.delete_message(chat_id, call.message.message_id)
                except Exception:
                    pass
                show_menu(chat_id)
                return
            if action == "rn":
                admin_action_mode[chat_id] = "rename_file"
                action_payload[chat_id] = obj_id
                bot.send_message(chat_id, "✏️ أرسل الاسم الجديد:")
                return
            if action == "rp":
                admin_action_mode[chat_id] = "replace_file"
                action_payload[chat_id] = obj_id
                bot.send_message(chat_id, "🔄 أرسل الملف البديل الآن:")
                return
            if action == "mv":
                admin_action_mode[chat_id] = "move_file_dest"
                action_payload[chat_id] = obj_id
                user_path[chat_id] = []
                bot.send_message(chat_id, "📦 تصفح الأقسام للوصول للموقع الجديد ثم اضغط (📦 أنقل إلى هذا القسم).")
                show_menu(chat_id)
                return
            if action == "up":
                files_col.update_one({"_id": ObjectId(obj_id)}, {"$inc": {"sort_order": -10}})
                show_menu(chat_id)
                return
            if action == "dn":
                files_col.update_one({"_id": ObjectId(obj_id)}, {"$inc": {"sort_order": 10}})
                show_menu(chat_id)
                return
            if action == "pn":
                files_col.update_one({"_id": ObjectId(obj_id)}, {"$set": {"sort_order": -999999}})
                show_menu(chat_id)
                return
    except Exception as e:
        logging.error(f"Callback error: {e}")
        try:
            bot.send_message(chat_id, f"❌ حدث خطأ في الزر: {e}")
        except Exception:
            pass

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
            logging.info("Webhook configured.")
        else:
            logging.warning("WEBHOOK_URL is empty; starting polling fallback.")
            bot.infinity_polling(timeout=20, long_polling_timeout=20)
    except Exception as e:
        logging.error(f"Webhook/polling startup error: {e}")

if __name__ == "__main__":
    threading.Thread(target=configure_webhook_after_delay, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT)
