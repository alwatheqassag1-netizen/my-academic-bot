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
from flask import Flask, request

# ==========================================
# 1. الإعدادات، المتغيرات البيئية، والسجلات
# ==========================================

if sys.version_info >= (3, 0):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

API_TOKEN = os.environ.get("API_TOKEN", "7524289470:AAGkeX96s1s6saxGP3uy14MN9it19nKn10A")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://Alwatheq:alwatheq73@cluster0.ft0mdkt.mongodb.net/?appName=Cluster0")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSy")
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
    settings_col.insert_one({"_id": "bot_general_settings", "status": "active", "emergency_flags": {"ai": False, "upload": False, "search": False, "ads": False}})

# ==========================================
# 4. الهيكل الأكاديمي الديناميكي (Hybrid Structure)
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

# مزامنة الهيكل الجديد لضمان تحديث (الترم الثاني) ومجلداته في قاعدة البيانات فوراً
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
BOT_USERNAME = bot.get_me().username

# ==========================================
# 5. دوال الصلاحيات المركزية (Roles System)
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

def check_rate_limit(chat_id):
    # ... كودك الحالي ...
    return True

# ضع الدالة الجديدة هنا:
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
# 6. نظام الذكاء الاصطناعي (مُحسّن بالسياق)
# ==========================================

def get_ai_response(prompt, chat_id):
    # 1. سجل المحادثة (السياق) - خاص بكل طلب
    history = ai_memory.get(chat_id, [])
    contents = [{"role": "user", "parts": [{"text": h['prompt']}]} if i % 2 == 0 else {"role": "model", "parts": [{"text": h['response']}]} for i, h in enumerate(history)]
    contents.append({"role": "user", "parts": [{"text": prompt}]})

    # --- الخدمة الأولى: Gemini API (منفصلة تماماً) ---
    if GEMINI_API_KEY and not GEMINI_API_KEY.startswith("AIzaSy"):
        for model in ["gemini-2.0-flash", "gemini-1.5-flash"]:
            try:
                response = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}",
                    json={"contents": contents}, timeout=8
                )
                if response.status_code == 200:
                    ans = response.json()['candidates'][0]['content']['parts'][0]['text'].strip()
                    return ans # نجاح الخدمة الأولى
            except Exception:
                pass # تجاهل الخطأ والمتابعة للخدمة التالية

    # --- الخدمة الثانية: OpenAI via Pollinations (منفصلة تماماً) ---
    try:
        response = requests.get(f"https://text.pollinations.ai/{requests.utils.quote(prompt)}?model=openai&seed=42", timeout=12)
        if response.status_code == 200 and response.text:
            return response.text.strip()
    except Exception:
        pass

    # --- الخدمة الثالثة: Mistral via Pollinations (منفصلة تماماً) ---
    try:
        response = requests.get(f"https://text.pollinations.ai/{requests.utils.quote(prompt)}?model=mistral&seed=42", timeout=12)
        if response.status_code == 200 and response.text:
            return response.text.strip()
    except Exception:
        pass

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

    user_path[chat_id] = []; reset_modes(chat_id); testing_mode[chat_id] = False
    start_txt = settings.get("start_text", DEFAULT_START_TEXT).replace("{first_name}", message.from_user.first_name or "طالبنا")
    bot.send_message(chat_id, start_txt)
    show_menu(chat_id)

@bot.message_handler(commands=['info'])
def info_command_handler(message):
    chat_id = message.chat.id
    settings = settings_col.find_one({"_id": "bot_general_settings"}) or {}
    bot.send_message(chat_id, settings.get("info_text", DEFAULT_INFO_TEXT))

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

    # [1] الصفحة الرئيسية
    if not path:
        for key in global_academic_structure.keys():
            markup.add(KeyboardButton(key))
        markup.add(KeyboardButton("🌟 ميزات الطالب"), KeyboardButton("📞 التواصل مع المشرف العام"))
        if is_owner(chat_id) and not testing_mode.get(chat_id):
            markup.add(KeyboardButton("👑 لوحة المشرف الرئيسي"))
        if is_admin(chat_id) and not is_owner(chat_id) and not testing_mode.get(chat_id):
            markup.add(KeyboardButton("🛡️ لوحة المشرف العام"))
        if is_admin(chat_id) or is_moderator(chat_id):
            markup.add(KeyboardButton("🛑 إنهاء العرض كمستخدم" if testing_mode.get(chat_id) else "👤 عرض كمستخدم"))
        bot.send_message(chat_id, "⚙️ القائمة الرئيسية:", reply_markup=markup); return

    # [2] اللوحات الإدارية
    if path_str == "SUPER_ADMIN_PANEL":
        markup.add("👥 إدارة المشرفين", "🔑 صلاحيات المشرفين")
        markup.add("📈 إحصائيات النظام", "📊 حالة النظام")
        markup.add("🚨 وضع الطوارئ", "📝 سجل العمليات")
        markup.add("📊 نشاط المشرفين", "🔍 كشف الملفات المكررة")
        markup.add("💾 النسخ الاحتياطي اليدوي", "✏️ تعديل نصوص البوت")
        markup.add("📢 إدارة الإعلانات", "🏷️ إدارة الأرشفة")
        markup.add("⭐️ التقييمات", "📊 إحصائيات المقررات")
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

    # [3] الأقسام الخاصة بالطالب
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
            if fav_id.startswith("path:"):
                markup.add(KeyboardButton(f"📁 {fav_id.replace('path:', '')}"))
        bot.send_message(chat_id, "⭐ *ملفاتك وأقسامك المفضلة:*", reply_markup=markup, parse_mode="Markdown")
        for fav_id in favs:
            if not fav_id.startswith("path:"):
                try: send_file_to_user(chat_id, files_col.find_one({"_id": ObjectId(fav_id)}), False)
                except: pass
        if not favs: bot.send_message(chat_id, "لا توجد ملفات أو أقسام في المفضلة.")
        return

    # [4] الأقسام والمجلدات الفعلية
    if isinstance(current_menu, dict):
        for key in current_menu.keys(): markup.add(KeyboardButton(key))
            
    # زر اللجنة العلمية يظهر حصرياً داخل مستوى أول
    if path_str == "🌱 مستوى أول":
        markup.add(KeyboardButton("اللجنة العلمية"))

    # استدعاء المجلدات الديناميكية للمسار الحالي (مهم جداً لتشغيل مجلدات المشرفين)
    for db_folder in folders_col.find({"parent_path": path_str}).sort([("sort_order", 1), ("folder_name", 1)]):
        markup.add(KeyboardButton(f"📁 {db_folder['folder_name']}"))
        
    for db_file in files_col.find({"menu_path": path_str}).sort([("sort_order", 1), ("_id", 1)]).limit(50):
        icon = "📌" if db_file.get("type") == "text" else "🖼️" if db_file.get("type") == "photo" else "📄"
        markup.add(KeyboardButton(f"{icon} {db_file['name']}"))
        
    # أزرار التنقل السفلية
    if path: 
        if len(path) == 1: markup.add("🔙 الرجوع للقائمة الرئيسية")
        else: markup.add("🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية")
        
    # الصلاحيات داخل المسار (للمشرفين)
    if is_moderator(chat_id, path_str):
        markup.add("➕ إضافة ملف/نص", "📂 إضافة مجلد")
        if current_menu is None or len(path) > 0: # تفعيل إعادة التسمية لجميع المجلدات
            markup.add("✏️ إعادة تسمية القسم", "🗑️ حذف القسم")
            markup.add("🔼 نقل مجلد للأعلى", "🔽 نقل مجلد للأسفل")
    
    if not is_owner(chat_id) or testing_mode.get(chat_id):
        if path_str: markup.add(KeyboardButton("⭐ إضافة هذا القسم للمفضلة"))
            
    bot.send_message(chat_id, f"📂 المسار الحالي:\n`{path_str}`" if path_str else "🏠 الرئيسية:", reply_markup=markup, parse_mode="Markdown")

def send_file_to_user(chat_id, res, has_perm):
    try:
        if not res: return
        markup = InlineKeyboardMarkup(row_width=2)
        file_id_str = str(res['_id'])
        
        # إنشاء روابط تليجرام المباشرة (Deep Links)
        share_url = f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}?start={file_id_str}"
        deep_folder_url = f"https://t.me/{BOT_USERNAME}?start=folder_{file_id_str}"
        bot_link = f"https://t.me/{BOT_USERNAME}?start={file_id_str}"

        # بناء الأزرار التفاعلية للمحادثة المباشرة مع البوت
        if has_perm and not testing_mode.get(chat_id):
            markup.add(InlineKeyboardButton("✏️ تسمية", callback_data=f"rn_{file_id_str}"), InlineKeyboardButton("🔄 استبدال", callback_data=f"rp_{file_id_str}"))
            markup.add(InlineKeyboardButton("🗑️ حذف", callback_data=f"dl_{file_id_str}"), InlineKeyboardButton("📦 نقل", callback_data=f"mv_{file_id_str}"))
            markup.add(InlineKeyboardButton("🔼 للأعلى", callback_data=f"up_{file_id_str}"), InlineKeyboardButton("🔽 للأسفل", callback_data=f"dn_{file_id_str}"))
            markup.add(InlineKeyboardButton("📌 تثبيت", callback_data=f"pn_{file_id_str}"))
            
        markup.add(InlineKeyboardButton("🔗 مشاركة", url=share_url), InlineKeyboardButton("📂 عرض المقرر", url=deep_folder_url))
        markup.add(InlineKeyboardButton("📝 تفاصيل", callback_data=f"rl_{file_id_str}"), InlineKeyboardButton("⭐ تقييم", callback_data=f"rt_{file_id_str}"))
        markup.add(InlineKeyboardButton("❤️ المفضلة", callback_data=f"fv_{file_id_str}"))

        file_type, file_id, base_name = res.get('type', 'document'), res.get('file_id'), res.get('name', 'وثيقة')
        up_date = res.get('upload_date', datetime.utcnow()).strftime('%Y-%m-%d')
        
        ratings = list(ratings_col.find({"file_id": file_id_str}))
        avg_rt = sum(r['score'] for r in ratings)/len(ratings) if ratings else 0.0
        
        # --- التطوير المضمون: دمج روابط الانتقال داخل نص الشرح لحمايتها عند إعادة التحويل (Forward) ---
        # نستخدم Markdown V2 أو HTML لتنسيق النصوص والروابط بشكل احترافي
        custom_caption = (
            f"📄 *{base_name}*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📅 {up_date} | 🔻 {res.get('downloads', 0)} | ⭐️ {avg_rt:.1f}/10\n\n"
            f"🔗 [📂 فتح المقرر في المجلد]({deep_folder_url})\n"
            f"📥 [⚡ تحميل وتصفح الملف مباشرة]({bot_link})"
        )

        # إرسال الملف بناءً على نوعه مع تفعيل صيغة Markdown لتشغيل الروابط النصية
        if file_type == 'text': 
            # بالنسبة للنصوص نرسل الرابط بأسفل الرسالة النصية
            text_content = res.get('content', res['name'])
            text_content += f"\n\n🔗 [📂 فتح المقرر في المجلد]({deep_folder_url})\n📥 [⚡ تحميل الملف]({bot_link})"
            bot.send_message(chat_id, text_content, reply_markup=markup, parse_mode="Markdown")
        elif file_type == 'photo' and file_id: 
            bot.send_photo(chat_id, file_id, caption=custom_caption, reply_markup=markup, parse_mode="Markdown")
        elif file_id: 
            bot.send_document(chat_id, file_id, caption=custom_caption, reply_markup=markup, parse_mode="Markdown")
            
    except Exception as e: 
        logging.error(f"Send Error: {e}")


# ==========================================
# 10. المعالج المركزي (Router)
# ==========================================

@bot.message_handler(content_types=['text', 'document', 'photo', 'video', 'audio'])
def universal_handler(message):
    chat_id = message.chat.id
    
    # 1. جلب الإعدادات فوراً لفحص حالة البوت قبل معالجة أي طلب
    settings = settings_col.find_one({"_id": "bot_general_settings"}) or {}
    
    # 2. الطرد الفوري والصارم للمستخدمين العاديين إذا كان البوت متوقفاً (مع استثناء الإدارة)
    if settings.get("status") == "inactive" and not is_admin(chat_id):
        bot.send_message(chat_id, "🚧 المنصة الأكاديمية تحت الصيانة الدورية حالياً. نعود إليكم فور الانتهاء قريباً.")
        return  # قطع فوري يمنع تنفيذ أي سطر بالأسفل ويحمي السيرفر
        
    # 3. إعفاء تام للملفات والوسائط من الـ Rate Limit لتجنب ضياع الحزم (Batch Fix)
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

    # [ملاحة العرض كمستخدم]
    if text == "👤 عرض كمستخدم" and (is_admin(chat_id) or is_moderator(chat_id)):
        reset_modes(chat_id); testing_mode[chat_id] = True; user_path[chat_id] = []
        bot.send_message(chat_id, "👀 وضع الطالب مفعل: أنت الآن تتصفح المنصة كطالب عادي بدون أي صلاحيات إدارية.")
        show_menu(chat_id); return

    if text == "🛑 إنهاء العرض كمستخدم" and testing_mode.get(chat_id):
        reset_modes(chat_id); testing_mode[chat_id] = False; user_path[chat_id] = []
        bot.send_message(chat_id, "💼 تم إنهاء وضع الطالب، عدت الآن للإدارة.")
        show_menu(chat_id); return

    # [اللجنة العلمية الديناميكية - كزر نصي وليس مجلداً]
    if text == "اللجنة العلمية" and path_str == "🌱 مستوى أول":
        bot.send_message(chat_id, settings.get("sci_text", DEFAULT_SCI_TEXT)); return

    # [ملاحة القوائم المباشرة والديناميكية]
    main_nav = ["🔝 القائمة الرئيسية", "🔙 الرجوع للقائمة السابقة", "🔙 الرجوع للقائمة الرئيسية", "🌟 ميزات الطالب", "⭐ ملفاتي المفضلة", "📞 التواصل مع المشرف العام", "👑 لوحة المشرف الرئيسي", "🛡️ لوحة المشرف العام", "👥 إدارة المشرفين", "🔑 صلاحيات المشرفين", "👤 عرض كمستخدم", "🛑 إنهاء العرض كمستخدم"] + list(global_academic_structure.keys())
    
    current_menu = get_menu_by_path(user_path.get(chat_id, []))
    
    # التقاط مجلدات الهيكل الأكاديمي التي ليست في الرئيسية
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

    # [إضافة المسار للمفضلة]
    if text == "⭐ إضافة هذا القسم للمفضلة":
        if path_str:
            users_col.update_one({"chat_id": chat_id}, {"$addToSet": {"favorites": "path:" + path_str}})
            bot.send_message(chat_id, "✅ تم إضافة القسم للمفضلة بنجاح.")
        return

    # [الرفع الذكي الدفعي للمشرفين والطلاب بمهلة موسعة]
    if message.content_type in ['document', 'photo', 'video', 'audio'] and upload_mode.get(chat_id):
        if settings.get("emergency_flags", {}).get("upload", False) and not is_owner(chat_id):
            bot.send_message(chat_id, "🚧 عذراً، استقبال الملفات معطل حالياً للصيانة."); return
        
        if chat_id not in upload_batches: upload_batches[chat_id] = []
        upload_batches[chat_id].append(message)
        if chat_id in upload_timers: upload_timers[chat_id].cancel()
        upload_timers[chat_id] = threading.Timer(5.0, process_user_batch, args=[chat_id, path_str, is_mod])
        upload_timers[chat_id].start()
        return

    if settings.get("status") == "inactive" and not is_admin(chat_id):
        bot.send_message(chat_id, "🚧 المنصة تحت الصيانة. نعود قريباً."); return

    if text == "📦 أنقل إلى هذا القسم" and mode == "move_file_dest":
        f_id = action_payload.get(chat_id)
        if f_id:
            files_col.update_one({"_id": ObjectId(f_id)}, {"$set": {"menu_path": path_str}})
            log_action(chat_id, "MOVE_FILE", f"Moved to {path_str}")
        bot.send_message(chat_id, "✅ تم تنفيذ النقل بنجاح."); reset_modes(chat_id); show_menu(chat_id); return

    # [العمليات الإدارية للأدمن الرئيسي والعام]
    if text == "➕ إضافة مشرف عام" and is_owner(chat_id):
        reset_modes(chat_id); admin_action_mode[chat_id] = "add_glb"
        bot.send_message(chat_id, "أرسل المعرف الرقمي (ID) للمشرف:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

    if text == "➕ إضافة مشرف مخصص لمسار" or text == "🛠 إدارة المشرف المخصص" and is_owner(chat_id):
        reset_modes(chat_id); admin_action_mode[chat_id] = "navigate_to_assign"; user_path[chat_id] = []
        bot.send_message(chat_id, "📍 يرجى تصفح الأقسام للوصول للمقرر المطلوب، ثم اضغط (✅ تعيين مشرف لهذا القسم)."); show_menu(chat_id); return

    if mode == "navigate_to_assign" and text == "✅ تعيين مشرف لهذا القسم" and is_owner(chat_id):
        admin_action_mode[chat_id] = "ask_path_admin_id"
        bot.send_message(chat_id, f"👤 المسار: `{path_str}`\nأرسل الآيدي (ID):", parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

    if mode == "ask_path_admin_id" and text and is_owner(chat_id):
        try:
            tid = int(text.strip())
            admins_col.update_one({"id": tid}, {"$set": {"id": tid, "type": "path", "active": True}, "$addToSet": {"allowed_paths": path_str}}, upsert=True)
            log_action(chat_id, "ASSIGN_PATH_ADMIN", f"ID: {tid} Path: {path_str}")
            bot.send_message(chat_id, f"✅ تم تقييد صلاحيات المشرف على المسار بنجاح."); reset_modes(chat_id); show_menu(chat_id)
        except: bot.send_message(chat_id, "❌ يرجى إرسال أرقام فقط.")
        return

    if mode == "add_glb" and text and is_owner(chat_id):
        try:
            tid = int(text.strip())
            admins_col.update_one({"id": tid}, {"$set": {"id": tid, "type": "global", "permissions": ["all"], "active": True}}, upsert=True)
            log_action(chat_id, "ADD_ADMIN", f"ID: {tid}")
            bot.send_message(chat_id, "✅ تمت الإضافة بنجاح."); reset_modes(chat_id); show_menu(chat_id)
        except: bot.send_message(chat_id, "❌ يرجى إرسال أرقام فقط.")
        return

    if text == "➖ حذف مشرف" and is_owner(chat_id):
        reset_modes(chat_id); admin_action_mode[chat_id] = "rm_adm"
        bot.send_message(chat_id, "أرسل الآيدي لحذفه نهائياً من النظام:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

    if mode == "rm_adm" and text and is_owner(chat_id):
        try:
            tid = int(text.strip())
            if tid != SUPER_ADMIN_ID:
                admins_col.delete_one({"id": tid}); log_action(chat_id, "RM_ADMIN", f"ID: {tid}")
                bot.send_message(chat_id, "✅ تمت الإزالة بنجاح.")
            reset_modes(chat_id); show_menu(chat_id)
        except: bot.send_message(chat_id, "❌ يرجى إرسال أرقام فقط.")
        return

    if text == "🚫 تعطيل مشرف" and is_owner(chat_id):
        reset_modes(chat_id); admin_action_mode[chat_id] = "deac_adm"
        bot.send_message(chat_id, "أرسل الآيدي لإيقاف صلاحياته مؤقتاً:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

    if mode == "deac_adm" and text and is_owner(chat_id):
        try:
            tid = int(text.strip())
            if tid != SUPER_ADMIN_ID:
                admins_col.update_one({"id": tid}, {"$set": {"active": False}}); log_action(chat_id, "DISABLE_ADMIN", f"ID: {tid}")
                bot.send_message(chat_id, "✅ تم التعطيل بنجاح.")
            reset_modes(chat_id); show_menu(chat_id)
        except: bot.send_message(chat_id, "❌ يرجى إرسال أرقام فقط.")
        return

    if text == "✅ تفعيل مشرف" and is_owner(chat_id):
        reset_modes(chat_id); admin_action_mode[chat_id] = "ac_adm"
        bot.send_message(chat_id, "أرسل الآيدي لتفعيله مجدداً:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

    if mode == "ac_adm" and text and is_owner(chat_id):
        try:
            tid = int(text.strip())
            admins_col.update_one({"id": tid}, {"$set": {"active": True}}); log_action(chat_id, "ENABLE_ADMIN", f"ID: {tid}")
            bot.send_message(chat_id, "✅ تم التفعيل بنجاح."); reset_modes(chat_id); show_menu(chat_id)
        except: bot.send_message(chat_id, "❌ يرجى إرسال أرقام فقط.")
        return

    if text == "🔍 البحث عن مشرف" and is_owner(chat_id):
        reset_modes(chat_id); admin_action_mode[chat_id] = "srch_adm"
        bot.send_message(chat_id, "أرسل الآيدي:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

    if mode == "srch_adm" and text and is_owner(chat_id):
        try:
            adm = admins_col.find_one({"id": int(text.strip())})
            bot.send_message(chat_id, f"👤 نوع المشرف: {adm.get('type')}\nالحالة: {'نشط ✅' if adm.get('active') else 'معطل 🚫'}\nالصلاحيات: {adm.get('permissions', [])}" if adm else "❌ المشرف غير مسجل بالنظام.")
            reset_modes(chat_id); show_menu(chat_id)
        except: bot.send_message(chat_id, "❌ يرجى إرسال أرقام فقط.")
        return

    if text == "🟢 منح صلاحية محددة" and is_owner(chat_id):
        reset_modes(chat_id); admin_action_mode[chat_id] = "gnt_prm1"
        bot.send_message(chat_id, "أرسل آيدي المشرف:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

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

    if text == "🔴 سحب صلاحية محددة" and is_owner(chat_id):
        reset_modes(chat_id); admin_action_mode[chat_id] = "rvk_prm1"
        bot.send_message(chat_id, "أرسل آيدي المشرف:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

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

    if text == "📋 عرض صلاحيات المشرف" and is_owner(chat_id):
        reset_modes(chat_id); admin_action_mode[chat_id] = "vw_prms"
        bot.send_message(chat_id, "أرسل الآيدي:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

    if mode == "vw_prms" and text and is_owner(chat_id):
        try:
            adm = admins_col.find_one({"id": int(text.strip())})
            bot.send_message(chat_id, f"🔑 الصلاحيات الممنوحة: {adm.get('permissions', [])}" if adm else "❌ المشرف غير موجود.")
            reset_modes(chat_id); show_menu(chat_id)
        except: bot.send_message(chat_id, "❌ يرجى إرسال أرقام فقط.")
        return

    if text == "✏️ تعديل نصوص البوت" and (is_owner(chat_id) or "texts" in get_admin_permissions(chat_id)):
        reset_modes(chat_id)
        m = ReplyKeyboardMarkup(resize_keyboard=True).add("✏️ تعديل Start", "✏️ تعديل Info").add("✏️ تعديل المطور", "✏️ تعديل اللجنة").add("🛑 إلغاء الأمر")
        bot.send_message(chat_id, "يرجى اختيار النص المراد تعديله:", reply_markup=m); return

    if text in ["✏️ تعديل Start", "✏️ تعديل Info", "✏️ تعديل المطور", "✏️ تعديل اللجنة"] and is_admin(chat_id):
        admin_action_mode[chat_id] = "edit_txt_" + text.split()[2]
        bot.send_message(chat_id, "أرسل النص الجديد الآن:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

    if mode and mode.startswith("edit_txt_") and text:
        k = "start_text" if "Start" in mode else ("info_text" if "Info" in mode else ("sci_text" if "اللجنة" in mode else "dev_text"))
        settings_col.update_one({"_id": "bot_general_settings"}, {"$set": {k: text}}, upsert=True)
        log_action(chat_id, "EDIT_TEXT", f"Edited {k}")
        bot.send_message(chat_id, "✅ تم حفظ التعديلات بنجاح."); reset_modes(chat_id); show_menu(chat_id); return

    if text == "📢 إدارة الإعلانات" and (is_owner(chat_id) or "broadcast" in get_admin_permissions(chat_id)):
        reset_modes(chat_id); broadcast_mode[chat_id] = True
        bot.send_message(chat_id, "📢 الرجاء إرسال الإعلان الموجه للدفعة:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

    if broadcast_mode.get(chat_id) and text:
        broadcast_mode[chat_id] = False
        settings_col.update_one({"_id": "bot_general_settings"}, {"$set": {"last_announcement": text}}, upsert=True)
        log_action(chat_id, "ADD_ANNOUNCEMENT", "Added new announcement")
        bot.send_message(chat_id, "✅ تم حفظ وبث الإعلان للدفعة بنجاح.")
        show_menu(chat_id); return

    if text == "📢 إعلانات الدفعة":
        if settings.get("emergency_flags", {}).get("ads", False) and not is_owner(chat_id):
            bot.send_message(chat_id, "🚧 قسم الإعلانات معطل حالياً."); return
        ann = settings.get("last_announcement", "لا توجد إعلانات مسجلة حالياً.")
        bot.send_message(chat_id, f"📢 *إعلانات الدفعة الرسمية:*\n\n{ann}", parse_mode="Markdown"); return

    if text == "🤖 المساعد الذكي (AI)":
        if settings.get("emergency_flags", {}).get("ai", False) and not is_owner(chat_id):
            bot.send_message(chat_id, "🚧 المساعد الذكي معطل مؤقتاً للصيانة."); return
        
        # --- إضافة التحقق من الكوتا هنا ---
        if not check_ai_quota(chat_id):
            bot.send_message(chat_id, "⚠️ لقد استنفدت محاولاتك اليومية (7/7). سيتم تجديدها تلقائياً غداً.")
            return
            
        reset_modes(chat_id); admin_action_mode[chat_id] = "ai_chat"
        if chat_id not in ai_memory: ai_memory[chat_id] = []
        bot.send_message(chat_id, "🤖 أهلاً بك، تفضل بطرح سؤالك أو استفسارك الأكاديمي:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

    if mode == "ai_chat" and text:
        bot.send_message(chat_id, "⏳ جاري تحليل الاستفسار وإعداد الإجابة المناسبة...")
        ans = get_ai_response(text, chat_id)
        ai_memory[chat_id].append({"prompt": text, "response": ans})
        if len(ai_memory[chat_id]) > 4: ai_memory[chat_id].pop(0)
        bot.send_message(chat_id, ans, parse_mode="Markdown")
        return

    if text == "🔍 بحث عن ملف":
        if settings.get("emergency_flags", {}).get("search", False) and not is_owner(chat_id):
            bot.send_message(chat_id, "🚧 محرك البحث معطل حالياً."); return
        reset_modes(chat_id); admin_action_mode[chat_id] = "search_exec"
        bot.send_message(chat_id, "🔍 الرجاء إرسال الكلمة المفتاحية للبحث:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

    if mode == "search_exec" and text:
        query = {"$text": {"$search": text}}
        results = list(files_col.find(query, {"score": {"$meta": "textScore"}}).sort([("score", {"$meta": "textScore"})]).limit(10))
        if not results:
            results = list(files_col.find({"$or": [{"name": {"$regex": text, "$options": "i"}}, {"caption": {"$regex": text, "$options": "i"}}],}).limit(15))
        if results:
            bot.send_message(chat_id, f"🔍 تم العثور على {len(results)} نتائج مطابقة:")
            for item in results: send_file_to_user(chat_id, item, is_moderator(chat_id, item['menu_path']))
        else: bot.send_message(chat_id, "❌ لم نجد أي ملف يطابق بحثك.")
        reset_modes(chat_id); show_menu(chat_id); return

    if text == "🔥 الملفات الأكثر شعبية":
        pop = list(files_col.find({"downloads": {"$gt": 0}}).sort("downloads", -1).limit(5))
        if pop:
            bot.send_message(chat_id, "🔥 *قائمة الملفات الأكثر تحميلاً:*", parse_mode="Markdown")
            for p in pop: send_file_to_user(chat_id, p, False)
        else: bot.send_message(chat_id, "لم يتم تسجيل إحصائيات كافية بعد."); return

    if text == "🆕 تحديثات اليوم":
        rec = list(files_col.find({"upload_date": {"$gte": datetime.utcnow() - timedelta(days=1)}}).limit(10))
        if rec:
            bot.send_message(chat_id, "🆕 *أحدث الملفات المضافة للمنصة:*", parse_mode="Markdown")
            for r in rec: send_file_to_user(chat_id, r, False)
        else: bot.send_message(chat_id, "لا توجد ملفات حديثة مضافة خلال 24 ساعة."); return

    if text == "📡 إدارة القنوات والمجموعات" and (is_owner(chat_id) or "channels_mgt" in get_admin_permissions(chat_id)):
        bot.send_message(chat_id, "📡 تم تخصيص هذا القسم لربط القنوات والمجموعات الأكاديمية.\n*(جاري تفعيل الـ API للربط قريباً)*")
        return
        
    if text == "👥 إدارة المستخدمين" and (is_owner(chat_id) or "users_mgt" in get_admin_permissions(chat_id)):
        bot.send_message(chat_id, f"👥 إجمالي المستخدمين المسجلين: {users_col.count_documents({})}")
        return

    # [أدوات المشرف الرئيسي والعام مع المعالجة الكاملة]
    if text == "📊 حالة النظام" and is_admin(chat_id):
        try:
            u_c, f_c, d_c = users_col.count_documents({}), files_col.count_documents({}), folders_col.count_documents({})
            st = f"📊 *تقرير حالة النظام:*\n👥 المستخدمين: {u_c} | 📁 الملفات: {f_c} | 📂 المجلدات: {d_c}\n⏱️ وقت التشغيل الفعلي: {str(datetime.utcnow() - START_TIME).split('.')[0]}"
            bot.send_message(chat_id, st, parse_mode="Markdown")
        except Exception as e: bot.send_message(chat_id, f"حدث خطأ: {e}")
        return

    if text == "🔍 كشف الملفات المكررة" and is_admin(chat_id):
        try:
            dups = list(files_col.aggregate([{"$group": {"_id": "$file_id", "count": {"$sum": 1}, "names": {"$push": "$name"}}}, {"$match": {"count": {"$gt": 1}}}]))
            msg = "🔍 *تقرير بالملفات المكررة (معرفات متطابقة):*\n"
            for d in dups[:10]: msg += f"• عدد التكرار: {d['count']} | اسم الملف: {d['names'][0]}\n"
            bot.send_message(chat_id, msg if dups else "✅ النظام سليم ولا يوجد تكرار بالملفات.", parse_mode="Markdown")
        except Exception as e:
            bot.send_message(chat_id, f"❌ حدث خطأ أثناء الفحص: {e}")
        return

    if (text == "📊 إحصائيات المقررات" or text == "📊 الإحصائيات التفصيلية للمقررات") and is_admin(chat_id):
        stats = list(files_col.aggregate([{"$match": {"menu_path": {"$regex": "^🌱|^🌿|^☘️|^🌳"}}}, {"$group": {"_id": "$menu_path", "count": {"$sum": 1}, "downloads": {"$sum": "$downloads"}}}, {"$sort": {"downloads": -1}}, {"$limit": 15}]))
        msg = "📊 *الإحصائيات التفصيلية للمقررات:*\n\n"
        for s in stats: msg += f"📁 `{s['_id']}`\n📄 الملفات: {s['count']} | 🔻 عمليات التحميل: {s['downloads']}\n\n"
        bot.send_message(chat_id, msg if stats else "لا توجد إحصائيات كافية للمقررات.", parse_mode="Markdown"); return

    if text == "⭐️ التقييمات" and is_admin(chat_id):
        top = list(ratings_col.aggregate([{"$group": {"_id": "$file_id", "avg": {"$avg": "$score"}, "cnt": {"$sum": 1}}}, {"$sort": {"avg": -1}}, {"$limit": 10}]))
        msg = "⭐️ *قائمة أعلى الملفات تقييماً:*\n"
        for r in top:
            f = files_col.find_one({"_id": ObjectId(r["_id"])})
            if f: msg += f"• {f['name']} | متوسط: {r['avg']:.1f} ({r['cnt']} أصوات)\n"
        bot.send_message(chat_id, msg if top else "لا توجد تقييمات مسجلة بعد.", parse_mode="Markdown"); return

    if text == "📝 سجل العمليات" and is_owner(chat_id):
        try:
            logs = list(action_logs_col.find().sort("timestamp", -1).limit(20))
            msg = "📝 *سجل الإجراءات والعمليات الإدارية:*\n\n"
            for lg in logs:
                t_str = lg['timestamp'].strftime('%Y-%m-%d %H:%M')
                msg += f"🔸 `{t_str}`\n👤 {lg.get('admin_name','-')} | ⚙️ {lg['action']}\n\n"
            bot.send_message(chat_id, msg if logs else "السجل خالي من أي عمليات.", parse_mode="Markdown")
        except Exception as e:
            bot.send_message(chat_id, f"❌ حدث خطأ في جلب السجل: {e}")
        return

    if text == "📈 إحصائيات النظام" and (is_owner(chat_id) or "stats" in get_admin_permissions(chat_id)):
        all_u = list(users_col.find())
        sm = f"📊 إجمالي المشتركين بالمنصة: {len(all_u)}\n\n"
        for u in all_u:
            name = u.get('first_name', '-')
            uid = u.get('chat_id', '0')
            uname = u.get('username', 'لا يوجد')
            sm += f"• {name} | `{uid}` | @{uname}\n"
            
        if len(sm) > 3800:
            bio = io.BytesIO(sm.encode('utf-8'))
            bio.name = "Users_Stats.txt"
            bot.send_document(chat_id, bio, caption="📊 كشف تفصيلي بالطلاب")
        else: 
            bot.send_message(chat_id, sm, parse_mode="Markdown")
        return

    if text == "📊 نشاط المشرفين" or text == "📊 لوحة نشاط المشرفين" and is_owner(chat_id):
        logs = list(action_logs_col.aggregate([{"$group": {"_id": "$admin_name", "count": {"$sum": 1}}}]))
        msg = "📊 *إحصائيات نشاط المشرفين:*\n"
        for l in logs: msg += f"• {l['_id']}: {l['count']} إجراء مسجل\n"
        bot.send_message(chat_id, msg if logs else "لا توجد نشاطات مسجلة للمشرفين.", parse_mode="Markdown"); return

    if text == "💾 النسخ الاحتياطي اليدوي" and is_owner(chat_id):
        bot.send_message(chat_id, "⏳ جاري تصدير قواعد البيانات...")
        bkp = {"files": list(files_col.find({}, {"_id": 0})), "folders": list(folders_col.find({}, {"_id": 0}))}
        bio = io.BytesIO(json.dumps(bkp, default=json_util.default, ensure_ascii=False).encode('utf-8'))
        bio.name = "DB_Backup.json"
        bot.send_document(chat_id, bio, caption="💾 نسخة احتياطية من البيانات (JSON)."); return

    if text == "🚨 وضع الطوارئ" and (is_owner(chat_id) or "emergency" in get_admin_permissions(chat_id)):
        flags = settings.get("emergency_flags", {})
        m = ReplyKeyboardMarkup(resize_keyboard=True)
        m.add(f"{'🟢' if not flags.get('ai') else '🔴'} الذكاء الاصطناعي", f"{'🟢' if not flags.get('upload') else '🔴'} الرفع")
        m.add(f"{'🟢' if not flags.get('search') else '🔴'} البحث", f"{'🟢' if not flags.get('ads') else '🔴'} الإعلانات")
        bot_status_btn = "🟢 تشغيل البوت كلياً" if settings.get("status") == "inactive" else "🛑 إيقاف البوت كلياً"
        m.add(bot_status_btn, "🔙 الرجوع للقائمة السابقة")
        bot.send_message(chat_id, "🚨 *لوحة تحكم الطوارئ المركزية:*", reply_markup=m, parse_mode="Markdown"); return

    if text in ["🟢 الذكاء الاصطناعي", "🔴 الذكاء الاصطناعي", "🟢 الرفع", "🔴 الرفع", "🟢 البحث", "🔴 البحث", "🟢 الإعلانات", "🔴 الإعلانات"] and is_admin(chat_id):
        key = "ai" if "الذكاء" in text else ("upload" if "الرفع" in text else ("search" if "البحث" in text else "ads"))
        cur = settings.get("emergency_flags", {}).get(key, False)
        settings_col.update_one({"_id": "bot_general_settings"}, {"$set": {f"emergency_flags.{key}": not cur}})
        log_action(chat_id, "EMERGENCY_TOGGLE", f"Toggled {key}")
        bot.send_message(chat_id, f"✅ تم تبديل الحالة بنجاح."); show_menu(chat_id); return

    if text in ["🛑 إيقاف البوت كلياً", "🟢 تشغيل البوت كلياً"] and is_owner(chat_id):
        new_status = "inactive" if "إيقاف" in text else "active"
        settings_col.update_one({"_id": "bot_general_settings"}, {"$set": {"status": new_status}})
        log_action(chat_id, "BOT_TOGGLE", f"Set bot status to {new_status}")
        bot.send_message(chat_id, f"✅ تم {'إيقاف' if new_status == 'inactive' else 'تشغيل'} البوت بنجاح."); show_menu(chat_id); return

    # [العمليات الإدارية داخل الأقسام الديناميكية والمجلدات]
    # تم تنظيف هذا الجزء بإزالة "مساهمة بملف"
    if path_str and path_str not in ["SUPER_ADMIN_PANEL", "GLOBAL_ADMIN_PANEL", "STUDENT_FEATURES", "FAVORITES", "MANAGE_ADMINS", "ADMIN_PERMISSIONS"]:
        
        # هنا كان يوجد كود مساهمة بملف، تم حذفه بالكامل للحفاظ على نظافة الكود.
        
        # إذا كان لديك أوامر أخرى هنا (مثل إضافة ملف للمشرفين)، ستظل تعمل بشكل طبيعي.
        if is_mod:
            if text == "➕ إضافة ملف/نص":
                reset_modes(chat_id); upload_mode[chat_id] = True
                bot.send_message(chat_id, "📥 قم بإرسال أو تحويل الملفات (سيتم ترتيبها وتصنيفها برمجياً):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

            if text == "📂 إضافة مجلد":
                reset_modes(chat_id); add_folder_mode[chat_id] = True
                bot.send_message(chat_id, "📂 الرجاء كتابة اسم المجلد الجديد:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

            if text == "✏️ إعادة تسمية القسم":
                reset_modes(chat_id); admin_action_mode[chat_id] = "rn_fld"
                bot.send_message(chat_id, "✏️ الرجاء إرسال الاسم الجديد للمجلد:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

            if text == "🗑️ حذف القسم":
                parent = path_str.rsplit(' > ', 1)[0] if ' > ' in path_str else ""
                folders_col.delete_one({"parent_path": parent, "folder_name": user_path[chat_id][-1]})
                user_path[chat_id].pop(); bot.send_message(chat_id, "🗑️ تم تنفيذ عملية الحذف بنجاح."); show_menu(chat_id); return

            if text in ["🔼 نقل مجلد للأعلى", "🔽 نقل مجلد للأسفل"]:
                parent = path_str.rsplit(' > ', 1)[0] if ' > ' in path_str else ""
                fld = folders_col.find_one({"parent_path": parent, "folder_name": user_path[chat_id][-1]})
                if fld:
                    folders_col.update_one({"_id": fld["_id"]}, {"$inc": {"sort_order": -1 if "للأعلى" in text else 1}})
                    user_path[chat_id].pop(); bot.send_message(chat_id, "✅ تم تغيير الترتيب بنجاح.")
                    show_menu(chat_id); return

    if mode == "rn_fld" and text:
        old_name = user_path[chat_id][-1]
        parent_p = path_str.rsplit(' > ', 1)[0] if ' > ' in path_str else ""
        new_name = text.strip()
        
        # 1. تحديث الاسم في الهيكل الديناميكي إن وجد
        renamed_in_struct = rename_in_structure(global_academic_structure, old_name, new_name)
        if renamed_in_struct:
            settings_col.update_one({"_id": "academic_structure"}, {"$set": {"data": global_academic_structure}})
            
        # 2. تحديثه في المجلدات الديناميكية الإضافية
        folders_col.update_one({"parent_path": parent_p, "folder_name": old_name}, {"$set": {"folder_name": new_name}})
        
        # 3. تحديث مسار الملفات التابعة (Recursive Update)
        old_f = f"{parent_p} > {old_name}" if parent_p else old_name
        new_f = f"{parent_p} > {new_name}" if parent_p else new_name
        
        for f in files_col.find({"menu_path": {"$regex": f"^{re.escape(old_f)}" }}):
            files_col.update_one({"_id": f["_id"]}, {"$set": {"menu_path": f['menu_path'].replace(old_f, new_f, 1)}})
        for d in folders_col.find({"parent_path": {"$regex": f"^{re.escape(old_f)}" }}):
            folders_col.update_one({"_id": d["_id"]}, {"$set": {"parent_path": d['parent_path'].replace(old_f, new_f, 1)}})
            
        user_path[chat_id][-1] = new_name
        log_action(chat_id, "RENAME_FOLDER", f"{old_name} to {new_name}")
        bot.send_message(chat_id, "✅ تم التعديل وتحديث مسارات كافة الملفات التابعة بأمان."); reset_modes(chat_id); show_menu(chat_id); return

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

    # [الاستماع للمجلدات المضافة يدوياً - لمعالجة المجلدات الديناميكية]
    if text.startswith("📁 ") and " > " in text:
        user_path[chat_id] = text.replace("📁 ", "").strip().split(" > ")
        show_menu(chat_id); return
    elif text.startswith("📁 "):
        user_path[chat_id].append(text.replace("📁 ", "").strip())
        show_menu(chat_id); return
        
    # [فتح الملفات]
    if text and (text.startswith("📄 ") or text.startswith("📌 ") or text.startswith("🖼️ ")):
        ex_name = text.replace("📄 ", "").replace("📌 ", "").replace("🖼️ ", "").strip()
        f_doc = files_col.find_one({"menu_path": path_str, "name": {"$regex": f"^{re.escape(ex_name)}$", "$options": "i"}})
        if f_doc:
            files_col.update_one({"_id": f_doc["_id"]}, {"$inc": {"downloads": 1}})
            send_file_to_user(chat_id, f_doc, is_moderator(chat_id, path_str))
        return

# ==========================================
# 11. أزرار التحكم الجانبية (Inline Callbacks)
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith(('rn_', 'rp_', 'dl_', 'mv_', 'up_', 'dn_', 'pn_', 'fv_', 'rt_', 'str_', 'rl_')))
def handle_inline_callbacks(call):
    chat_id = call.message.chat.id
    try: action, obj_id = call.data.split('_', 1)
    except: return

    if action == 'fv':
        users_col.update_one({"chat_id": chat_id}, {"$addToSet": {"favorites": obj_id}})
        bot.answer_callback_query(call.id, "❤️ تمت إضافة الملف لمفضلتك بنجاح!", show_alert=True); return
        
    if action == 'rt':
        m = InlineKeyboardMarkup(row_width=5)
        m.add(*[InlineKeyboardButton(str(i), callback_data=f"str_{i}_{obj_id}") for i in range(1, 11)])
        try: bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=m)
        except: pass
        return
        
    if action == 'str':
        score, f_id = obj_id.split('_')
        ratings_col.update_one({"file_id": f_id, "user_id": chat_id}, {"$set": {"score": int(score)}}, upsert=True)
        bot.answer_callback_query(call.id, f"⭐️ تم حفظ تقييمك: {score}/10", show_alert=True)
        try: bot.delete_message(chat_id, call.message.message_id)
        except: pass
        return

    if action == 'rl':
        f_doc = files_col.find_one({"_id": ObjectId(obj_id)})
        if f_doc:
            bot.answer_callback_query(call.id, f"📝 الملف: {f_doc.get('name')}\n📥 التحميلات: {f_doc.get('downloads', 0)}\n📅 الرفع: {f_doc.get('upload_date', datetime.utcnow()).strftime('%Y-%m-%d')}", show_alert=True)
        return

    f_doc = files_col.find_one({"_id": ObjectId(obj_id)})
    if not f_doc or not is_moderator(chat_id, f_doc['menu_path']): bot.answer_callback_query(call.id, "❌ عذراً، لا تمتلك الصلاحية الكافية.", show_alert=True); return

    if action == 'dl':
        files_col.delete_one({"_id": ObjectId(obj_id)})
        log_action(chat_id, "DELETE_FILE", f_doc['name'])
        try: bot.delete_message(chat_id, call.message.message_id)
        except: pass
        show_menu(chat_id)
    elif action == 'rn':
        reset_modes(chat_id); admin_action_mode[chat_id] = "rename_file"; action_payload[chat_id] = obj_id
        bot.send_message(chat_id, "✏️ الرجاء إرسال الاسم الجديد للملف الآن:")
    elif action == 'rp':
        reset_modes(chat_id); admin_action_mode[chat_id] = "replace_file"; action_payload[chat_id] = obj_id
        bot.send_message(chat_id, "🔄 الرجاء إرسال الملف البديل الآن:")
    elif action == 'mv':
        reset_modes(chat_id); admin_action_mode[chat_id] = "move_file_dest"; action_payload[chat_id] = obj_id
        bot.send_message(chat_id, "📦 يرجى تصفح الأقسام للوصول لموقع النقل واضغط زر التأكيد.")
        user_path[chat_id] = []; show_menu(chat_id)
    elif action in ['up', 'dn', 'pn']:
        if action == 'pn': files_col.update_one({"_id": ObjectId(obj_id)}, {"$set": {"sort_order": -999}})
        else: files_col.update_one({"_id": ObjectId(obj_id)}, {"$inc": {"sort_order": -1 if action == 'up' else 1}})
        bot.answer_callback_query(call.id, "✅ تم تحديث الترتيب بنجاح.", show_alert=False); show_menu(chat_id)

# ==========================================
# 12. تشغيل السيرفر (Webhook Setup)
# ==========================================

@app.route('/webhook', methods=['POST'])
def webhook_listen_route():
    if request.headers.get('content-type') == 'application/json':
        bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
        return "!", 200
    return "Invalid", 403

@app.route("/")
def index_home_route(): return "Bot V5.7 LMS Master Active & Running 🚀", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
