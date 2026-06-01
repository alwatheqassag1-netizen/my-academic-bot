# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys
import time
import io
import re
import json
import logging
import threading
from datetime import datetime, timedelta

import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
from bson.objectid import ObjectId
from bson import json_util
import requests
from flask import Flask, request, redirect

# ==========================================
# 1. الإعدادات، المتغيرات البيئية، والسجلات
# ==========================================

if sys.version_info >= (3, 0):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

API_TOKEN = os.environ.get("API_TOKEN", "7524289470:AAGkeX96s1s6saxGP3uy14MN9it19nKn10A").strip()
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://Alwatheq:alwatheq73@cluster0.ft0mdkt.mongodb.net/?appName=Cluster0").strip()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSy").strip()
SUPER_ADMIN_ID = 6842543527

START_TIME = datetime.utcnow()

user_path = {}
upload_mode = {}
add_folder_mode = {}
admin_action_mode = {}
testing_mode = {}
action_payload = {}
RATE_LIMIT_DICT = {}
ai_memory = {}
broadcast_mode = {}
system_stats = {"requests_24h": 0}

upload_batches = {}
upload_timers = {}

# ==========================================
# 2. النصوص الافتراضية الرسمية
# ==========================================

DEFAULT_START_TEXT = (
    "🌟 أهلاً وسهلاً بك يا {first_name} في المنصة الأكاديمية الرسمية لقسم الذكاء الاصطناعي وعلوم البيانات 🎓\n\n"
    "مرحباً بك في بوابتك التعليمية الرقمية الموحدة. يمكنك من خلال المنصة الوصول إلى المحاضرات، الملخصات، النماذج، والمراجع المعتمدة.\n\n"
    "👇 الرجاء اختيار القسم أو الخدمة المطلوبة من القائمة أدناه:"
)

DEFAULT_INFO_TEXT = (
    "🤖 المنصة الأكاديمية الذكية - قسم الذكاء الاصطناعي وعلوم البيانات\n\n"
    "نظام متكامل يهدف إلى أتمتة الوصول للموارد التعليمية، وتسهيل رحلة الطالب الأكاديمية عبر تقنيات برمجية حديثة وآمنة."
)

DEFAULT_DEV_TEXT = (
    "✉️ التواصل مع إدارة المنصة\n\n"
    "نحن نسعد باستقبال استفساراتكم، ملاحظاتكم، أو بلاغاتكم بشأن المقررات والملفات.\n"
    "يرجى اختيار نوع التواصل المناسب من الأزرار التفاعلية بالأسفل لضمان وصول رسالتك للجهة المختصة."
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
    "✨ ختاماً، نشكر كل من اقتطع من وقته لدعم زملائه.. دمتم سنداً لدفعتكم."
)

# ==========================================
# 3. الاتصال بقاعدة البيانات
# ==========================================

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client['academic_bot_db']
    files_col = db['uploaded_files']
    folders_col = db['dynamic_folders']
    users_col = db['bot_users']
    admins_col = db['admins_list']
    settings_col = db['bot_settings']
    hashtags_col = db['dynamic_hashtags']
    auth_groups_col = db['auth_groups']
    alerts_col = db['course_alerts']
    kb_col = db['knowledge_base']
    ai_usage_col = db['ai_usage']
    action_logs_col = db['action_logs']
    ratings_col = db['file_ratings']

    files_col.create_index([("name", "text"), ("caption", "text")])
    files_col.create_index([("menu_path", 1)])
    files_col.create_index([("file_id", 1)])
    logging.info("Database Connected Flawlessly!")
except Exception as db_err:
    logging.error(f"MongoDB Connection Error: {db_err}")

if admins_col.count_documents({"id": SUPER_ADMIN_ID}) == 0:
    admins_col.insert_one({"id": SUPER_ADMIN_ID, "type": "super", "allowed_paths": [], "permissions": ["all"], "active": True})

if settings_col.count_documents({"_id": "bot_general_settings"}) == 0:
    settings_col.insert_one({"_id": "bot_general_settings", "status": "active", "emergency_flags": {"ai": False, "upload": False, "search": False, "ads": False}, "target_group_id": None})

# ==========================================
# 4. الهيكل الأكاديمي الديناميكي
# ==========================================

ACADEMIC_STRUCTURE_DEFAULT = {
    "🌱 مستوى أول": {
        "📅 ترم أول": {},
        "📅 ترم ثاني": {
            "ثقافة اسلامية 🕋": {
                "محاضرات 📃": {},
                "نماذج اختبارات 📝": {}
            },
            "لغة عربية 2 🇾🇪": {
                "محاضرات 📃": {},
                "نماذج اختبارات 📝": {}
            },
            "لغة إنجليزية 2 🇺🇸": {
                "محاضرات 📃": {},
                "نماذج اختبارات 📝": {}
            },
            "تفاضل وتكامل   2 📐": {
                "محاضرات الدكتور 📃": {},
                "محاضرات تمارين📚": {},
                "نماذج اختبارات نظري📝": {},
                "نماذج تمارين 📝": {},
                "مراجع خارجية": {}
            },
            "مقدمة في علوم البيانات 📊": {
                "محاضرات الدكتور 📃": {},
                "📄 ملخصات محاضرات الدكتور 📄": {},
                "محاضرات العملي📚": {},
                "نماذج اختبارات نظري 📝": {}
            },
            "برمجة الحاسوب 🖥️": {
                "محاضرات الدكتور 📃": {},
                "محاضرات عملي برمجة": {},
                "نماذج اختبارات برمجة 📝": {},
                "تمارين ومشاريع عملية 📜": {}
            },
            "رياضيات متقطعة": {
                "محاضرات  الدكتور 📃": {},
                "محاضرات  التمارين": {},
                "نماذج اختبارات رياضيات متقطعة 📝": {},
                "مرجع  خارجي 📜": {}
            },
            "📁 تفاصيل الاختبارات النهائية ♨️": {}
        }
    },
    "🌿 مستوى ثاني": {"📅 ترم أول": {}, "📅 ترم ثاني": {}},
    "☘️ مستوى ثالث": {"📅 ترم أول": {}, "📅 ترم ثاني": {}},
    "🌳 مستوى رابع": {"📅 ترم أول": {}, "📅 ترم ثاني": {}},
    "📖 دليل القسم": {}
}

db_struct = settings_col.find_one({"_id": "academic_structure"})
term2_keys = db_struct.get("data", {}).get("🌱 مستوى أول", {}).get("📅 ترم ثاني", {}).keys() if db_struct else []

if not db_struct or "ثقافة اسلامية 🕋" not in term2_keys or "محاضرات الدكتور 📃" not in db_struct.get("data", {}).get("🌱 مستوى أول", {}).get("📅 ترم ثاني", {}).get("برمجة الحاسوب 🖥️", {}).keys():
    settings_col.update_one({"_id": "academic_structure"}, {"$set": {"data": ACADEMIC_STRUCTURE_DEFAULT}}, upsert=True)
    global_academic_structure = ACADEMIC_STRUCTURE_DEFAULT
else:
    global_academic_structure = db_struct["data"]

def rename_in_structure(struct, old_k, new_k):
    for k in list(struct.keys()):
        if k == old_k:
            struct[new_k] = struct.pop(old_k)
            return True
        if isinstance(struct[k], dict):
            if rename_in_structure(struct[k], old_k, new_k):
                return True
    return False

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)
BOT_USERNAME = bot.get_me().username or "bot"

# ==========================================
# 5. دوال الصلاحيات المركزية
# ==========================================

def is_owner(chat_id): return chat_id == SUPER_ADMIN_ID

def is_admin(chat_id):
    if is_owner(chat_id): return True
    adm = admins_col.find_one({"id": chat_id, "active": True})
    return adm is not None and adm.get("type") == "global"

def is_moderator(chat_id, current_path_str=None):
    if is_admin(chat_id): return not testing_mode.get(chat_id)
    if testing_mode.get(chat_id): return False
    adm = admins_col.find_one({"id": chat_id, "active": True})
    if not adm: return False
    if adm.get("type") in ["global", "super"]: return True
    if current_path_str:
        for allowed_p in adm.get("allowed_paths", []):
            if current_path_str.startswith(allowed_p) or current_path_str == allowed_p: return True
    return False

def get_admin_permissions(chat_id):
    if is_owner(chat_id): return ["all"]
    admin = admins_col.find_one({"id": chat_id, "active": True})
    return admin.get("permissions", []) if admin else []

def log_action(admin_id, action_type, details):
    try:
        user = users_col.find_one({"chat_id": admin_id})
        admin_name = user.get("first_name", "Admin") if user else "Admin"
        action_logs_col.insert_one({"admin_id": admin_id, "admin_name": admin_name, "action": action_type, "details": details, "timestamp": datetime.utcnow()})
    except: pass

def get_menu_by_path(path):
    menu = global_academic_structure
    for segment in path:
        if isinstance(menu, dict) and segment in menu: menu = menu[segment]
        else: return None
    return menu

def get_path_string(chat_id): return " > ".join(user_path.get(chat_id, []))

def reset_modes(chat_id, clear_upload=True):
    if clear_upload: upload_mode[chat_id] = False
    add_folder_mode[chat_id] = False
    admin_action_mode[chat_id] = None
    action_payload.pop(chat_id, None)

def check_rate_limit(chat_id): return True

def check_ai_quota(chat_id):
    if is_owner(chat_id): return True
    user = users_col.find_one({"chat_id": chat_id})
    if not user: return True
    now = datetime.utcnow()
    last_reset = user.get("ai_reset_time", now - timedelta(days=1))
    if now - last_reset > timedelta(days=1):
        users_col.update_one({"chat_id": chat_id}, {"$set": {"ai_count": 1, "ai_reset_time": now}}, upsert=True)
        return True
    if user.get("ai_count", 0) < 7:
        users_col.update_one({"chat_id": chat_id}, {"$inc": {"ai_count": 1}})
        return True
    return False

# ==========================================
# 6. نظام الذكاء الاصطناعي
# ==========================================

def get_ai_response(prompt, chat_id):
    history = ai_memory.get(chat_id, [])
    contents = [{"role": "user", "parts": [{"text": h['prompt']}]} if i % 2 == 0 else {"role": "model", "parts": [{"text": h['response']}]} for i, h in enumerate(history)]
    contents.append({"role": "user", "parts": [{"text": prompt}]})

    if GEMINI_API_KEY and not GEMINI_API_KEY.startswith("AIzaSy"):
        for model in ["gemini-2.0-flash", "gemini-1.5-flash"]:
            try:
                response = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}",
                    json={"contents": contents}, timeout=8
                )
                if response.status_code == 200:
                    return response.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            except Exception: pass

    for backup in ["openai", "mistral"]:
        try:
            response = requests.get(f"https://text.pollinations.ai/{requests.utils.quote(prompt)}?model={backup}&seed=42", timeout=12)
            if response.status_code == 200 and response.text.strip(): return response.text.strip()
        except Exception: pass
    return "🤖 نعتذر، تعذر الوصول إلى جميع خوادم الذكاء الاصطناعي في هذه اللحظة."

# ==========================================
# 7. الرفع المتسلسل الذكي المتقدم
# ==========================================

def build_file_doc(message, path_str):
    if message.content_type == 'document': name, f_id = message.document.file_name or "مستند", message.document.file_id
    elif message.content_type == 'photo': name, f_id = "صورة توضيحية", message.photo[-1].file_id
    elif message.content_type == 'video': name, f_id = "مقطع مرئي", message.video.file_id
    elif message.content_type == 'audio': name, f_id = "ملف صوتي", message.audio.file_id
    else: name, f_id = "ملحق أكاديمي", None

    caption_text = message.caption or name
    clean_name = caption_text.replace("📄", "").replace("📌", "").replace("🖼️", "").strip()
    return {
        "menu_path": path_str, "name": clean_name[:80], "type": message.content_type, "caption": message.caption,
        "file_id": f_id, "downloads": 0, "sort_order": 0, "upload_date": datetime.utcnow(),
        "uploader_id": message.chat.id
    }

def process_user_batch(chat_id, path_str, is_mod):
    batch = upload_batches.pop(chat_id, [])
    if not batch: return
    batch.sort(key=lambda msg: msg.message_id) 
    succ = 0
    base_sort = int(time.time() * 10)
    for i, msg in enumerate(batch):
        if not is_mod and msg.content_type == 'document':
            ext = msg.document.file_name.split('.')[-1].lower() if msg.document.file_name else ""
            if ext not in ['pdf', 'docx', 'pptx']: continue
        doc = build_file_doc(msg, path_str)
        doc['sort_order'] = base_sort + i
        if doc['file_id'] and not files_col.find_one({"menu_path": path_str, "file_id": doc['file_id']}):
            files_col.insert_one(doc)
            succ += 1
    try:
        if succ > 0:
            bot.send_message(chat_id, f"✅ تم استلام ودمج الدفعة بالترتيب الصحيح.\n📦 عدد الملفات المضافة: {succ}\n📁 المسار: `{path_str}`", parse_mode="Markdown")
            log_action(chat_id, "BATCH_UPLOAD", f"{succ} files in {path_str}")
    except: pass

# ==========================================
# 8. التوجيه وأوامر البداية
# ==========================================

@bot.message_handler(commands=['start'])
def start_command(message):
    chat_id = message.chat.id
    user_data = users_col.find_one({"chat_id": chat_id})
    if user_data and user_data.get("blocked"): return

    settings = settings_col.find_one({"_id": "bot_general_settings"}) or {}
    if settings.get("status") == "inactive" and not is_admin(chat_id):
        bot.send_message(chat_id, "🚧 المنصة الأكاديمية تحت الصيانة الدورية. نعود إليكم قريباً."); return

    users_col.update_one(
        {"chat_id": chat_id},
        {"$set": {"first_name": message.from_user.first_name, "username": f"@{message.from_user.username}", "last_interaction": datetime.utcnow()}, "$setOnInsert": {"smart_notifications": True, "favorites": []}},
        upsert=True
    )

    command_args = message.text.split()
    if len(command_args) > 1:
        param = command_args[1]
        try:
            f_obj = files_col.find_one({"_id": ObjectId(param.replace("folder_", ""))})
            if f_obj:
                if param.startswith("folder_") and f_obj.get('menu_path'):
                    user_path[chat_id] = f_obj['menu_path'].split(' > ')
                    bot.send_message(chat_id, f"📂 تم التوجيه إلى المسار:\n`{f_obj['menu_path']}`", parse_mode="Markdown")
                    show_menu(chat_id); return
                else:
                    files_col.update_one({"_id": f_obj["_id"]}, {"$inc": {"downloads": 1}})
                    send_file_to_user(chat_id, f_obj, is_moderator(chat_id, f_obj['menu_path'])); return
        except: pass

    user_path[chat_id] = []
    reset_modes(chat_id)
    testing_mode[chat_id] = False
    start_txt = settings.get("start_text", DEFAULT_START_TEXT).replace("{first_name}", message.from_user.first_name or "طالبنا")
    bot.send_message(chat_id, start_txt)
    show_menu(chat_id)

@bot.message_handler(commands=['info'])
def info_command_handler(message):
    settings = settings_col.find_one({"_id": "bot_general_settings"}) or {}
    bot.send_message(message.chat.id, settings.get("info_text", DEFAULT_INFO_TEXT))

# ==========================================
# 9. ديناميكية القوائم وتوليد واجهة المستخدم
# ==========================================

def show_menu(chat_id):
    path, path_str = user_path.get(chat_id, []), get_path_string(chat_id)
    current_menu = get_menu_by_path(path)
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mode = admin_action_mode.get(chat_id)

    if mode == "move_file_dest":
        markup.add(KeyboardButton("📦 أنقل إلى هذا القسم"), KeyboardButton("🛑 إلغاء الأمر"))
        bot.send_message(chat_id, f"📦 تصفح للوصول للموقع الجديد ثم اضغط تأكيد.\n📌 المسار الحالي: {path_str or 'الرئيسية'}", reply_markup=markup); return

    if mode == "navigate_to_assign":
        markup.add(KeyboardButton("✅ تعيين مشرف لهذا القسم"), KeyboardButton("🛑 إلغاء الأمر"))

    if not path:
        for key in global_academic_structure.keys(): markup.add(KeyboardButton(key))
        markup.add(KeyboardButton("🌟 ميزات الطالب"), KeyboardButton("📞 التواصل مع المشرف العام"))
        if is_owner(chat_id) and not testing_mode.get(chat_id): markup.add(KeyboardButton("👑 لوحة المشرف الرئيسي"))
        if is_admin(chat_id) and not is_owner(chat_id) and not testing_mode.get(chat_id): markup.add(KeyboardButton("🛡️ لوحة المشرف العام"))
        if is_admin(chat_id) or is_moderator(chat_id): markup.add(KeyboardButton("🛑 إنهاء العرض كمستخدم" if testing_mode.get(chat_id) else "👤 عرض كمستخدم"))
        if is_owner(chat_id) and not testing_mode.get(chat_id): markup.add(KeyboardButton("⚙️ إعدادات جروب الدفعة"))
        bot.send_message(chat_id, "⚙️ القائمة الرئيسية:", reply_markup=markup); return

    if path_str == "SUPER_ADMIN_PANEL":
        markup.add("👥 إدارة المشرفين", "🔑 صلاحيات المشرفين")
        markup.add("📈 إحصائيات النظام", "📊 حالة النظام")
        markup.add("🚨 وضع الطوارئ", "📝 سجل العمليات")
        markup.add("📊 نشاط المشرفين", "🔍 كشف الملفات المكررة")
        markup.add("💾 النسخ الاحتياطي اليدوي", "✏️ تعديل نصوص البوت")
        markup.add("📢 إدارة الإعلانات", "🏷️ إدارة الأرشفة")
        markup.add("⭐️ التقييمات", "📊 إحصائيات المقررات")
        markup.add("⚙️ إعدادات جروب الدفعة")
        markup.add("🔙 الرجوع للقائمة الرئيسية")
        bot.send_message(chat_id, "👑 *لوحة المشرف الرئيسي:*", reply_markup=markup, parse_mode="Markdown"); return

    if path_str == "MANAGE_ADMINS":
        markup.add("➕ إضافة مشرف عام", "➕ إضافة مشرف مخصص لمسار")
        markup.add("✅ تفعيل مشرف", "🚫 تعطيل مشرف")
        markup.add("➖ حذف مشرف", "🟢 منح صلاحية محددة")
        markup.add("🔴 سحب صلاحية محددة", "📋 عرض صلاحيات المشرف")
        markup.add("📊 لوحة نشاط المشرفين", "📝 سجل العمليات")
        markup.add("🔍 البحث عن مشرف", "🛠 إدارة المشرف المخصص")
        markup.add("🔙 الرجوع للقائمة السابقة")
        bot.send_message(chat_id, "👥 *إدارة المشرفين:*", reply_markup=markup, parse_mode="Markdown"); return

    if path_str == "ADMIN_PERMISSIONS":
        markup.add("🟢 منح صلاحية محددة", "🔴 سحب صلاحية محددة")
        markup.add("📋 عرض صلاحيات المشرف", "🔙 الرجوع للقائمة الرئيسية")
        bot.send_message(chat_id, "🔑 *صلاحيات المشرفين:*", reply_markup=markup, parse_mode="Markdown"); return

    if path_str == "GLOBAL_ADMIN_PANEL":
        markup.add("📊 حالة النظام", "🔍 كشف الملفات المكررة")
        markup.add("📊 إحصائيات المقررات", "⭐️ التقييمات")
        markup.add("🔙 الرجوع للقائمة الرئيسية")
        bot.send_message(chat_id, "🛡️ *لوحة المشرف العام:*", reply_markup=markup, parse_mode="Markdown"); return

    if path_str == "STUDENT_FEATURES":
        markup.add("🤖 المساعد الذكي (AI)", "🔍 بحث عن ملف")
        markup.add("🔥 الملفات الأكثر شعبية", "🆕 تحديثات اليوم")
        markup.add("📢 إعلانات الدفعة", "⭐ ملفاتي المفضلة")
        markup.add("🔙 الرجوع للقائمة الرئيسية")
        bot.send_message(chat_id, "🌟 *ميزات الطالب:*", reply_markup=markup, parse_mode="Markdown"); return

    if path_str == "FAVORITES":
        u_data = users_col.find_one({"chat_id": chat_id})
        favs = u_data.get("favorites", []) if u_data else []
        markup.add("🔙 الرجوع للقائمة الرئيسية")
        for fav_id in favs:
            if fav_id.startswith("path:"): markup.add(KeyboardButton(f"📁 {fav_id.replace('path:', '')}"))
        bot.send_message(chat_id, "⭐ *ملفاتك وأقسامك المفضلة:*", reply_markup=markup, parse_mode="Markdown")
        for fav_id in favs:
            if not fav_id.startswith("path:"):
                try: send_file_to_user(chat_id, files_col.find_one({"_id": ObjectId(fav_id)}), False)
                except: pass
        if not favs: bot.send_message(chat_id, "لا توجد ملفات أو أقسام في المفضلة.")
        return

    if isinstance(current_menu, dict):
        for key in current_menu.keys(): markup.add(KeyboardButton(key))
            
    if path_str == "🌱 مستوى أول": markup.add(KeyboardButton("اللجنة العلمية"))

    for db_folder in folders_col.find({"parent_path": path_str}).sort([("sort_order", 1), ("folder_name", 1)]):
        markup.add(KeyboardButton(f"📁 {db_folder['folder_name']}"))
        
    for db_file in files_col.find({"menu_path": path_str}).sort([("sort_order", 1), ("_id", 1)]).limit(50):
        icon = "📌" if db_file.get("type") == "text" else "🖼️" if db_file.get("type") == "photo" else "📄"
        markup.add(KeyboardButton(f"{icon} {db_file['name']}"))
        
    if path: 
        if len(path) == 1: markup.add("🔙 الرجوع للقائمة الرئيسية")
        else: markup.add("🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية")
        
    if is_moderator(chat_id, path_str):
        markup.add("➕ إضافة ملف/نص", "📂 إضافة مجلد")
        if current_menu is None or len(path) > 0: 
            markup.add("✏️ إعادة تسمية القسم", "🗑️ حذف القسم")
            markup.add("🔼 نقل مجلد للأعلى", "🔽 نقل مجلد للأسفل")
    
    if not is_owner(chat_id) or testing_mode.get(chat_id):
        if path_str: markup.add(KeyboardButton("⭐ إضافة هذا القسم للمفضلة"))
            
    bot.send_message(chat_id, f"📂 المسار الحالي:\n`{path_str}`" if path_str else "🏠 الرئيسية:", reply_markup=markup, parse_mode="Markdown")

# ==========================================
# دالة إرسال الملفات السليمة والخالية من الأخطاء
# ==========================================
def send_file_to_user(chat_id, res, has_perm):
    try:
        if not res: return
        file_id_str = str(res['_id'])
        share_url = f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}?start={file_id_str}"
        deep_folder_url = f"https://t.me/{BOT_USERNAME}?start=folder_{file_id_str}"

        # 1. القناة الوسيطة للأرشيف
        STORAGE_CHANNEL_ID = -1003769719318 

        # 2. بناء اسم الزر الشفاف للمجلد
        channel_markup = InlineKeyboardMarkup(row_width=1)
        path_str = res.get('menu_path', '')
        btn_name = "📁 المجلد الرئيسي" 
        
        if path_str:
            parts = path_str.split(' > ')
            clean_parts = [p.replace("🕋","").replace("🇺🇸","").replace("🇾🇪","").replace("📊","").replace("🖥️","").replace("📐","").replace("📃","").replace("📝","").replace("📚","").strip() for p in parts]
            if len(clean_parts) >= 2:
                section = clean_parts[-1]
                course = clean_parts[-2]
                if "نماذج" in section: section = "نماذج"
                if "محاضرات" in section: section = "محاضرات"
                if "ملخصات" in section: section = "ملخصات"
                btn_name = f"📁 {section} - {course}"
            elif len(clean_parts) == 1:
                btn_name = f"📁 {clean_parts[0]}"

        channel_markup.add(InlineKeyboardButton(btn_name, url=deep_folder_url))

        # 3. أزرار التفاعل والإشراف الخاصة بالطالب والمشرف
        private_markup = InlineKeyboardMarkup(row_width=2)
        if has_perm and not testing_mode.get(chat_id):
            private_markup.add(InlineKeyboardButton("✏️ تسمية", callback_data=f"rn_{file_id_str}"), InlineKeyboardButton("🔄 استبدال", callback_data=f"rp_{file_id_str}"))
            private_markup.add(InlineKeyboardButton("🗑️ حذف", callback_data=f"dl_{file_id_str}"), InlineKeyboardButton("📦 نقل", callback_data=f"mv_{file_id_str}"))
            private_markup.add(InlineKeyboardButton("🔼 للأعلى", callback_data=f"up_{file_id_str}"), InlineKeyboardButton("🔽 للأسفل", callback_data=f"dn_{file_id_str}"))
            private_markup.add(InlineKeyboardButton("📌 تثبيت", callback_data=f"pn_{file_id_str}"))
            private_markup.add(InlineKeyboardButton("📢 نشر في جروب الدفعة", callback_data=f"sh_{file_id_str}"))
            
        private_markup.add(InlineKeyboardButton("🔗 مشاركة الملف", url=share_url))
        private_markup.add(InlineKeyboardButton("📝 تفاصيل", callback_data=f"rl_{file_id_str}"), InlineKeyboardButton("⭐ تقييم", callback_data=f"rt_{file_id_str}"))
        private_markup.add(InlineKeyboardButton("❤️ المفضلة", callback_data=f"fv_{file_id_str}"))

        file_type = res.get('type', 'document')
        file_id = res.get('file_id')
        base_name = res.get('name', 'وثيقة')
        up_date = res.get('upload_date', datetime.utcnow()).strftime('%Y-%m-%d')
        
        try:
            ratings = list(ratings_col.find({"file_id": file_id_str}))
            avg_rt = sum(r['score'] for r in ratings)/len(ratings) if ratings else 0.0
        except Exception:
            avg_rt = 0.0
            
        caption = (res.get('caption') or base_name) + f"\n\n📅 {up_date} | 🔻 {res.get('downloads', 0)} | ⭐️ {avg_rt:.1f}/10"

        posted_msg = None
        try:
            if file_type == 'text': posted_msg = bot.send_message(STORAGE_CHANNEL_ID, res.get('content', res['name']), reply_markup=channel_markup)
            elif file_type == 'photo' and file_id: posted_msg = bot.send_photo(STORAGE_CHANNEL_ID, file_id, caption=caption, reply_markup=channel_markup)
            elif file_id: posted_msg = bot.send_document(STORAGE_CHANNEL_ID, file_id, caption=caption, reply_markup=channel_markup)
        except Exception as channel_err:
            logging.error(f"Channel Storage Error: {channel_err}")

        if posted_msg:
            bot.forward_message(chat_id, STORAGE_CHANNEL_ID, posted_msg.message_id)
            bot.send_message(chat_id, "⚙️ *خيارات وإدارة الملف:*", reply_markup=private_markup, parse_mode="Markdown")
        else:
            private_markup.add(InlineKeyboardButton(btn_name, url=deep_folder_url))
            if file_type == 'text': bot.send_message(chat_id, res.get('content', res['name']), reply_markup=private_markup)
            elif file_type == 'photo' and file_id: bot.send_photo(chat_id, file_id, caption=caption, reply_markup=private_markup)
            elif file_id: bot.send_document(chat_id, file_id, caption=caption, reply_markup=private_markup)
            
    except Exception as e: 
        logging.error(f"Send Error: {e}")

# ==========================================
# 10. المعالج المركزي (Router)
# ==========================================

@bot.message_handler(content_types=['text', 'document', 'photo', 'video', 'audio'])
def universal_handler(message):
    chat_id = message.chat.id
    settings = settings_col.find_one({"_id": "bot_general_settings"}) or {}
    
    if settings.get("status") == "inactive" and not is_admin(chat_id):
        bot.send_message(chat_id, "🚧 المنصة الأكاديمية تحت الصيانة الدورية حالياً. نعود إليكم فور الانتهاء قريباً.")
        return 
        
    if message.content_type == 'text':
        if not check_rate_limit(chat_id): return
        
    global system_stats; system_stats["requests_24h"] += 1

    user_data = users_col.find_one({"chat_id": chat_id})
    if user_data and user_data.get("blocked"): return
    
    text = message.text if message.content_type == 'text' else ""
    path_str = get_path_string(chat_id)
    mode = admin_action_mode.get(chat_id)
    is_mod = is_moderator(chat_id, path_str)

    if text == "🛑 إلغاء الأمر":
        reset_modes(chat_id); bot.send_message(chat_id, "✅ تم إلغاء العملية الجارية."); show_menu(chat_id); return

    if text == "👤 عرض كمستخدم" and (is_admin(chat_id) or is_moderator(chat_id)):
        reset_modes(chat_id); testing_mode[chat_id] = True; user_path[chat_id] = []
        bot.send_message(chat_id, "👀 وضع الطالب مفعل: أنت الآن تتصفح المنصة كطالب عادي بدون أي صلاحيات إدارية.")
        show_menu(chat_id); return

    if text == "🛑 إنهاء العرض كمستخدم" and testing_mode.get(chat_id):
        reset_modes(chat_id); testing_mode[chat_id] = False; user_path[chat_id] = []
        bot.send_message(chat_id, "💼 تم إنهاء وضع الطالب، عدت الآن للإدارة.")
        show_menu(chat_id); return

    if text == "اللجنة العلمية" and path_str == "🌱 مستوى أول":
        bot.send_message(chat_id, settings.get("sci_text", DEFAULT_SCI_TEXT)); return

    main_nav = ["🔝 القائمة الرئيسية", "🔙 الرجوع للقائمة السابقة", "🔙 الرجوع للقائمة الرئيسية", "🌟 ميزات الطالب", "⭐ ملفاتي المفضلة", "📞 التواصل مع المشرف العام", "👑 لوحة المشرف الرئيسي", "🛡️ لوحة المشرف العام", "👥 إدارة المشرفين", "🔑 صلاحيات المشرفين", "👤 عرض كمستخدم", "🛑 إنهاء العرض كمستخدم", "⚙️ إعدادات جروب الدفعة"] + list(global_academic_structure.keys())
    
    current_menu = get_menu_by_path(user_path.get(chat_id, []))
    
    if text not in main_nav and isinstance(current_menu, dict) and text in current_menu.keys():
        if mode not in ["navigate_to_assign", "move_file_dest"]: reset_modes(chat_id)
        user_path[chat_id].append(text)
        show_menu(chat_id)
        return

    if text in main_nav:
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
        elif text == "⚙️ إعدادات جروب الدفعة" and is_owner(chat_id):
            current_id = settings.get("target_group_id", "غير معيّن ❌")
            bot.send_message(chat_id, f"⚙️ *إعدادات جروب النشر الحالي:*\n\nالآيدي المسجل: `{current_id}`\n\nاضغط على الزر بالأسفل لتغييره أو تحديثه:", parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("✏️ تحديث آيدي الجروب", "🛑 إلغاء الأمر"))
            return
        elif text == "📞 التواصل مع المشرف العام":
            dev_msg = settings.get("dev_text", DEFAULT_DEV_TEXT)
            markup = InlineKeyboardMarkup(row_width=1)
            markup.add(
                InlineKeyboardButton("❓ استفسار أكاديمي", url="https://t.me/AlwatheqAssag"),
                InlineKeyboardButton("📝 ملاحظات واقتراحات", url="https://t.me/AlwatheqAssag"),
                InlineKeyboardButton("⚠️ بلاغ عن مشكلة بمقرر", url="https://t.me/AlwatheqAssag"),
                InlineKeyboardButton("📤 إرسال ملف أو ملخص", url="https://t.me/AlwatheqAssag"),
                InlineKeyboardButton("💬 فتح المحادثة المباشرة", url="https://t.me/AlwatheqAssag")
            )
            bot.send_message(chat_id, dev_msg, reply_markup=markup, parse_mode="Markdown"); return
        show_menu(chat_id); return

    if text == "✏️ تحديث آيدي الجروب" and is_owner(chat_id):
        reset_modes(chat_id); admin_action_mode[chat_id] = "set_group_id_db"
        bot.send_message(chat_id, "📥 أرسل آيدي (ID) الجروب الجديد الآن (يبدأ بـ -100):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

    if mode == "set_group_id_db" and text and is_owner(chat_id):
        try:
            group_id_num = int(text.strip())
            settings_col.update_one({"_id": "bot_general_settings"}, {"$set": {"target_group_id": group_id_num}}, upsert=True)
            log_action(chat_id, "SET_TARGET_GROUP_ID", f"New Group ID: {group_id_num}")
            bot.send_message(chat_id, f"✅ تم حفظ وتحديث آيدي جروب النشر بنجاح!\n🎯 الآيدي الحالي: `{group_id_num}`", parse_mode="Markdown")
            reset_modes(chat_id); user_path[chat_id] = ["SUPER_ADMIN_PANEL"]; show_menu(chat_id)
        except: bot.send_message(chat_id, "❌ خطأ! يرجى إرسال أرقام فقط مع إشارة السالب.")
        return

    if text == "⭐ إضافة هذا القسم للمفضلة":
        if path_str:
            users_col.update_one({"chat_id": chat_id}, {"$addToSet": {"favorites": "path:" + path_str}})
            bot.send_message(chat_id, "✅ تم إضافة القسم للمفضلة بنجاح.")
        return

    if message.content_type in ['document', 'photo', 'video', 'audio'] and upload_mode.get(chat_id):
        if settings.get("emergency_flags", {}).get("upload", False) and not is_owner(chat_id):
            bot.send_message(chat_id, "🚧 عذراً، استقبال الملفات معطل حالياً للصيانة."); return
        
        if chat_id not in upload_batches: upload_batches[chat_id] = []
        upload_batches[chat_id].append(message)
        if chat_id in upload_timers: upload_timers[chat_id].cancel()
        upload_timers[chat_id] = threading.Timer(5.0, process_user_batch, args=[chat_id, path_str, is_mod])
        upload_timers[chat_id].start()
        return

    if text == "📦 أنقل إلى هذا القسم" and mode == "move_file_dest":
        f_id = action_payload.get(chat_id)
        if f_id:
            files_col.update_one({"_id": ObjectId(f_id)}, {"$set": {"menu_path": path_str}})
            log_action(chat_id, "MOVE_FILE", f"Moved to {path_str}")
        bot.send_message(chat_id, "✅ تم تنفيذ النقل بنجاح."); reset_modes(chat_id); show_menu(chat_id); return

    if mode == "add_glb" and text and is_owner(chat_id):
        try:
            tid = int(text.strip())
            admins_col.update_one({"id": tid}, {"$set": {"id": tid, "type": "global", "permissions": ["all"], "active": True}}, upsert=True)
            log_action(chat_id, "ADD_ADMIN", f"ID: {tid}")
            bot.send_message(chat_id, "✅ تمت الإضافة بنجاح."); reset_modes(chat_id); show_menu(chat_id)
        except: bot.send_message(chat_id, "❌ يرجى إرسال أرقام فقط.")
        return

    if mode == "ask_path_admin_id" and text and is_owner(chat_id):
        try:
            tid = int(text.strip())
            admins_col.update_one({"id": tid}, {"$set": {"id": tid, "type": "path", "active": True}, "$addToSet": {"allowed_paths": action_payload.get(chat_id, path_str)}}, upsert=True)
            log_action(chat_id, "ASSIGN_PATH_ADMIN", f"ID: {tid}")
            bot.send_message(chat_id, "✅ تم تقييد صلاحيات المشرف المخصص بنجاح."); reset_modes(chat_id); show_menu(chat_id)
        except: bot.send_message(chat_id, "❌ يرجى إرسال أرقام فقط.")
        return

    if mode == "rm_adm" and text and is_owner(chat_id):
        try:
            tid = int(text.strip())
            if tid != SUPER_ADMIN_ID:
                admins_col.delete_one({"id": tid}); log_action(chat_id, "RM_ADMIN", f"ID: {tid}")
                bot.send_message(chat_id, "✅ تمت الإزالة بنجاح.")
            reset_modes(chat_id); show_menu(chat_id)
        except: bot.send_message(chat_id, "❌ يرجى إرسال أرقام فقط.")
        return

    if mode == "deac_adm" and text and is_owner(chat_id):
        try:
            tid = int(text.strip())
            if tid != SUPER_ADMIN_ID:
                admins_col.update_one({"id": tid}, {"$set": {"active": False}}); log_action(chat_id, "DISABLE_ADMIN", f"ID: {tid}")
                bot.send_message(chat_id, "✅ تم التعطيل بنجاح.")
            reset_modes(chat_id); show_menu(chat_id)
        except: bot.send_message(chat_id, "❌ يرجى إرسال أرقام فقط.")
        return

    if mode == "ac_adm" and text and is_owner(chat_id):
        try:
            tid = int(text.strip())
            admins_col.update_one({"id": tid}, {"$set": {"active": True}}); log_action(chat_id, "ENABLE_ADMIN", f"ID: {tid}")
            bot.send_message(chat_id, "✅ تم التفعيل بنجاح."); reset_modes(chat_id); show_menu(chat_id)
        except: bot.send_message(chat_id, "❌ يرجى إرسال أرقام فقط.")
        return

    if mode == "srch_adm" and text and is_owner(chat_id):
        try:
            adm = admins_col.find_one({"id": int(text.strip())})
            bot.send_message(chat_id, f"👤 نوع المشرف: {adm.get('type')}\nالحالة: {'نشط ✅' if adm.get('active') else 'معطل 🚫'}\nالصلاحيات: {adm.get('permissions', [])}" if adm else "❌ المشرف غير مسجل بالنظام.")
            reset_modes(chat_id); show_menu(chat_id)
        except: bot.send_message(chat_id, "❌ يرجى إرسال أرقام فقط.")
        return

    if mode == "gnt_prm1" and text and is_owner(chat_id):
        try:
            action_payload[chat_id] = int(text.strip()); admin_action_mode[chat_id] = "gnt_prm2"
            m = ReplyKeyboardMarkup(resize_keyboard=True).add("إعلانات", "إحصائيات", "طوارئ", "تعديل نصوص", "أرشفة").add("إحصائيات المقررات", "إدارة المستخدمين", "إدارة القنوات").add("🛑 إلغاء الأمر")
            bot.send_message(chat_id, "اختر الصلاحية المراد منحها:", reply_markup=m)
        except: bot.send_message(chat_id, "❌ يرجى إرسال أرقام فقط.")
        return

    if mode == "gnt_prm2" and text and is_owner(chat_id):
        p_map = {"إعلانات":"broadcast", "إحصائيات":"stats", "طوارئ":"emergency", "تعديل نصوص":"texts", "أرشفة":"archives", "إحصائيات المقررات":"courses_stats", "إدارة المستخدمين":"users_mgt", "إدارة القنوات":"channels_mgt"}
        if text in p_map:
            admins_col.update_one({"id": action_payload.get(chat_id)}, {"$addToSet": {"permissions": p_map[text]}})
            bot.send_message(chat_id, "✅ تم منح الصلاحية بنجاح."); reset_modes(chat_id); show_menu(chat_id); return

    if mode == "rvk_prm1" and text and is_owner(chat_id):
        try:
            action_payload[chat_id] = int(text.strip()); admin_action_mode[chat_id] = "rvk_prm2"
            m = ReplyKeyboardMarkup(resize_keyboard=True).add("إعلانات", "إحصائيات", "طوارئ", "تعديل نصوص", "أرشفة").add("إحصائيات المقررات", "إدارة المستخدمين", "إدارة القنوات").add("🛑 إلغاء الأمر")
            bot.send_message(chat_id, "اختر الصلاحية المراد سحبها:", reply_markup=m)
        except: bot.send_message(chat_id, "❌ يرجى إرسال أرقام فقط.")
        return

    if mode == "rvk_prm2" and text and is_owner(chat_id):
        p_map = {"إعلانات":"broadcast", "إحصائيات":"stats", "طوارئ":"emergency", "تعديل نصوص":"texts", "أرشفة":"archives", "إحصائيات المقررات":"courses_stats", "إدارة المستخدمين":"users_mgt", "إدارة القنوات":"channels_mgt"}
        if text in p_map:
            admins_col.update_one({"id": action_payload.get(chat_id)}, {"$pull": {"permissions": p_map[text]}})
            bot.send_message(chat_id, "✅ تم سحب الصلاحية بنجاح."); reset_modes(chat_id); show_menu(chat_id); return

    if mode == "vw_prms" and text and is_owner(chat_id):
        try:
            adm = admins_col.find_one({"id": int(text.strip())})
            bot.send_message(chat_id, f"🔑 الصلاحيات الممنوحة: {adm.get('permissions', [])}" if adm else "❌ المشرف غير موجود.")
            reset_modes(chat_id); show_menu(chat_id)
        except: bot.send_message(chat_id, "❌ يرجى إرسال أرقام فقط.")
        return

    if mode and mode.startswith("edit_txt_") and text:
        k = "start_text" if "Start" in mode else ("info_text" if "Info" in mode else ("sci_text" if "اللجنة" in mode else "dev_text"))
        settings_col.update_one({"_id": "bot_general_settings"}, {"$set": {k: text}}, upsert=True)
        log_action(chat_id, "EDIT_TEXT", f"Edited {k}")
        bot.send_message(chat_id, "✅ تم حفظ التعديلات بنجاح."); reset_modes(chat_id); show_menu(chat_id); return

    if mode == "rename_file" and text:
        files_col.update_one({"_id": ObjectId(action_payload.get(chat_id))}, {"$set": {"name": text.strip()}})
        log_action(chat_id, "RENAME_FILE", text[:20])
        bot.send_message(chat_id, "✅ تم تحديث اسم الملف في قاعدة البيانات، وسيظهر بالاسم الجديد فوراً دون الحاجة لإعادة رفعه."); reset_modes(chat_id); show_menu(chat_id); return

    if mode == "replace_file":
        doc = build_file_doc(message, path_str)
        update_data = {"type": doc['type'], "file_id": doc['file_id'], "name": doc['name'], "caption": doc['caption']} if doc['file_id'] else {"type": "text", "content": text, "name": text[:30], "file_id": None}
        files_col.update_one({"_id": ObjectId(action_payload.get(chat_id))}, {"$set": update_data})
        log_action(chat_id, "REPLACE_FILE", "Replaced a file")
        bot.send_message(chat_id, "✅ تم استبدال الملف بنجاح."); reset_modes(chat_id); show_menu(chat_id); return

    if add_folder_mode.get(chat_id) and text and is_mod:
        folders_col.insert_one({"parent_path": path_str, "folder_name": text.strip(), "sort_order": 0})
        log_action(chat_id, "CREATE_FOLDER", text.strip())
        bot.send_message(chat_id, f"✅ تم إنشاء المجلد: {text.strip()}"); reset_modes(chat_id); show_menu(chat_id); return

    if upload_mode.get(chat_id) and message.content_type == 'text' and is_mod:
        files_col.insert_one({"menu_path": path_str, "name": text[:60].strip(), "type": "text", "content": text, "downloads": 0, "upload_date": datetime.utcnow(), "sort_order": 0})
        bot.send_message(chat_id, "✅ تم حفظ التلخيص النصي بنجاح."); return

    if mode == "rn_fld" and text:
        old_name = user_path[chat_id][-1]
        parent_p = path_str.rsplit(' > ', 1)[0] if ' > ' in path_str else ""
        new_name = text.strip()
        
        renamed_in_struct = rename_in_structure(global_academic_structure, old_name, new_name)
        if renamed_in_struct:
            settings_col.update_one({"_id": "academic_structure"}, {"$set": {"data": global_academic_structure}})
            
        folders_col.update_one({"parent_path": parent_p, "folder_name": old_name}, {"$set": {"folder_name": new_name}})
        
        old_f = f"{parent_p} > {old_name}" if parent_p else old_name
        new_f = f"{parent_p} > {new_name}" if parent_p else new_name
        
        for f in files_col.find({"menu_path": {"$regex": f"^{re.escape(old_f)}" }}):
            files_col.update_one({"_id": f["_id"]}, {"$set": {"menu_path": f['menu_path'].replace(old_f, new_f, 1)}})
        for d in folders_col.find({"parent_path": {"$regex": f"^{re.escape(old_f)}" }}):
            folders_col.update_one({"_id": d["_id"]}, {"$set": {"parent_path": d['parent_path'].replace(old_f, new_f, 1)}})
            
        user_path[chat_id][-1] = new_name
        log_action(chat_id, "RENAME_FOLDER", f"{old_name} to {new_name}")
        bot.send_message(chat_id, "✅ تم التعديل وتحديث مسارات كافة الملفات التابعة بأمان."); reset_modes(chat_id); show_menu(chat_id); return

    if text.startswith("📁 ") and " > " in text:
        user_path[chat_id] = text.replace("📁 ", "").strip().split(" > ")
        show_menu(chat_id); return
    elif text.startswith("📁 "):
        user_path[chat_id].append(text.replace("📁 ", "").strip())
        show_menu(chat_id); return
        
    if text and any(text.startswith(icon) for icon in ["📄 ", "📌 ", "🖼️ "]):
        ex_name = text.split(" ", 1)[1].strip()
        f_doc = files_col.find_one({"menu_path": path_str, "name": {"$regex": f"^{re.escape(ex_name)}$", "$options": "i"}})
        if not f_doc:
            f_doc = files_col.find_one({"name": {"$regex": f"^{re.escape(ex_name)}$", "$options": "i"}})
            
        if f_doc:
            files_col.update_one({"_id": f_doc["_id"]}, {"$inc": {"downloads": 1}})
            send_file_to_user(chat_id, f_doc, is_moderator(chat_id, f_doc.get('menu_path', path_str)))
        else:
            bot.send_message(chat_id, "❌ لم يتم العثور على هذا الملف في قاعدة البيانات، يرجى إشعار المسؤول لتحديث مساره.")
        return

# =========================================================
# 11. معالج الأزرار الشفافة المركزي (Callback Handler)
# =========================================================

@bot.callback_query_handler(func=lambda call: True)
def handle_inline_callbacks(call):
    chat_id = call.message.chat.id
    data = call.data or ""
    
    # تحرير فوري لتجنب تعليق واجهة تيليجرام
    try: bot.answer_callback_query(call.id)
    except Exception: pass

    if "_" not in data: return
    try: action, obj_id = data.split('_', 1)
    except Exception: return

    if action == 'fv':
        users_col.update_one({"chat_id": chat_id}, {"$addToSet": {"favorites": obj_id}})
        try: bot.answer_callback_query(call.id, "❤️ تمت الإضافة للمفضلة الأكاديمية!")
        except Exception: pass
        return
        
    if action == 'rt':
        m = InlineKeyboardMarkup(row_width=5)
        m.add(*[InlineKeyboardButton(str(i), callback_data=f"str_{i}_{obj_id}") for i in range(1, 11)])
        try: bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=m)
        except Exception: pass
        return
        
    # 🔥 [إصلاح حاسم]: تقسيم الأصوات مع تفرع محدود لحماية MongoDB من الانهيار عند الحفظ
    if action == 'str':
        try:
            score, f_id = obj_id.split('_', 1)
            ratings_col.update_one({"file_id": f_id, "user_id": chat_id}, {"$set": {"score": int(score)}}, upsert=True)
            try: bot.answer_callback_query(call.id, f"⭐️ تم حفظ تقييمك: {score}/10")
            except Exception: pass
            bot.delete_message(chat_id, call.message.message_id)
        except Exception: pass
        return

    if action == 'rl':
        f_doc = files_col.find_one({"_id": ObjectId(obj_id)})
        if f_doc:
            try: bot.answer_callback_query(call.id, f"📝 الملف: {f_doc.get('name')}\n📥 التحميلات: {f_doc.get('downloads', 0)}")
            except Exception: pass
        return

    # 🔥 [إصلاح حاسم]: النشر المباشر السلس لجروب الدفعة ديناميكياً وحماية الصلاحيات الحساسة
    if action == 'sh':
        f_doc = files_col.find_one({"_id": ObjectId(obj_id)})
        if not f_doc or not (is_admin(chat_id) or is_moderator(chat_id, f_doc.get('menu_path'))):
            try: bot.answer_callback_query(call.id, "❌ لا تمتلك الصلاحية الإدارية.", show_alert=True)
            except Exception: pass
            return
            
        settings = settings_col.find_one({"_id": "bot_general_settings"}) or {}
        TARGET_GROUP_ID = settings.get("target_group_id")
        
        if not TARGET_GROUP_ID:
            bot.send_message(chat_id, "❌ فشل النشر! آيدي جروب الدفعة غير معيّن من لوحة التحكم الرئيسي.")
            return
            
        try:
            # النشر المباشر للجروب كرسالة أصلية صامدة (has_perm=False لحماية خيارات الأدمن)
            send_file_to_user(TARGET_GROUP_ID, f_doc, has_perm=False)
            bot.send_message(chat_id, f"✅ تم قذف المستند والأزرار الطلابية الشفافة بنجاح داخل جروب الدفعة المعتمد!")
            log_action(chat_id, "PUBLISH_TO_GROUP", f_doc['name'])
        except Exception as share_err:
            bot.send_message(chat_id, f"❌ تعذر النشر للجروب، تأكد من وجود البوت فيه كمشرف بالكامل.\nالخطأ: `{share_err}`")
        return

    f_doc = files_col.find_one({"_id": ObjectId(obj_id)})
    if not f_doc or not (is_admin(chat_id) or is_moderator(chat_id, f_doc.get('menu_path'))):
        try: bot.answer_callback_query(call.id, "❌ عذراً، لا تمتلك الصلاحية الكافية.", show_alert=True)
        except Exception: pass
        return

    if action == 'dl':
        files_col.delete_one({"_id": ObjectId(obj_id)})
        log_action(chat_id, "DELETE_FILE", f_doc['name'])
        try: bot.delete_message(chat_id, call.message.message_id)
        except Exception: pass
        show_menu(chat_id)
    elif action == 'rn':
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "rename_file"
        action_payload[chat_id] = obj_id
        bot.send_message(chat_id, "✏️ الرجاء إرسال الاسم الجديد للملف الآن:")
    elif action == 'rp':
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "replace_file"
        action_payload[chat_id] = obj_id
        bot.send_message(chat_id, "🔄 الرجاء إرسال الملف البديل الآن:")
    elif action == 'mv':
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "move_file_dest"
        action_payload[chat_id] = obj_id
        user_path[chat_id] = []
        bot.send_message(chat_id, "📦 يرجى تصفح الأقسام للوصول لموقع النقل واضغط زر التأكيد.")
        show_menu(chat_id)
    elif action in ['up', 'dn', 'pn']:
        if action == 'pn': files_col.update_one({"_id": ObjectId(obj_id)}, {"$set": {"sort_order": -999}})
        else: files_col.update_one({"_id": ObjectId(obj_id)}, {"$inc": {"sort_order": -1 if action == 'up' else 1}})
        show_menu(chat_id)

# =========================================================
# 12. تشغيل السيرفر واستقبال التحديثات بأمان (Webhook Listener)
# =========================================================

@app.route('/webhook', methods=['POST'])
def webhook_listen_route():
    try:
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
    except Exception as e:
        logging.error(f"Webhook processing error: {e}")
    return "!", 200

@app.route("/")
def index_home_route(): 
    return "Bot V5.7 LMS Master Active & Running 🚀", 200

from flask import redirect

@app.route('/f/<folder_id>')
def redirect_to_folder(folder_id):
    return redirect(f"https://t.me/{BOT_USERNAME}?start=folder_{folder_id}")

def configure_webhook_safely():
    time.sleep(3)
    try:
        bot.remove_webhook()
        bot.set_webhook(url="https://academic-bot-iyuy.onrender.com/webhook")
        logging.info("Webhook configured successfully via Background Thread!")
    except Exception as e:
        logging.error(f"Webhook connection error: {e}")

if __name__ == "__main__":
    threading.Thread(target=configure_webhook_safely, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
