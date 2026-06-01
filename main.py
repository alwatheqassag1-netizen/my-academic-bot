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
# 3. الاتصال بقاعدة البيانات والفهارس
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
    "🌳 مستوى رابع": {"📅 ترم أول": {}, "📅 ترم ثاني": {}}
}

def load_academic_structure():
    db_struct = settings_col.find_one({"_id": "academic_structure"})
    if not db_struct:
        settings_col.insert_one({"_id": "academic_structure", "data": ACADEMIC_STRUCTURE_DEFAULT})
        return ACADEMIC_STRUCTURE_DEFAULT
    return db_struct["data"]

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
# 5. دوال الصلاحيات والتحكم الآمن
# ==========================================

def is_owner(chat_id): return chat_id == SUPER_ADMIN_ID

def is_admin(chat_id):
    if is_owner(chat_id): return True
    adm = admins_col.find_one({"id": chat_id, "active": True})
    return adm is not None and adm.get("type") in ["global", "super"]

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
    menu = load_academic_structure()
    for segment in path:
        if isinstance(menu, dict) and segment in menu: menu = menu[segment]
        else: return None
    return menu

def get_path_string(chat_id): return " > ".join(user_path.setdefault(chat_id, []))

def reset_modes(chat_id, clear_upload=True):
    if clear_upload: upload_mode[chat_id] = False
    add_folder_mode[chat_id] = False
    admin_action_mode[chat_id] = None
    action_payload.pop(chat_id, None)
    broadcast_mode[chat_id] = False

def check_rate_limit(chat_id): return True

# ==========================================
# 6. الذكاء الاصطناعي 
# ==========================================

def get_ai_response(prompt, chat_id):
    if GEMINI_API_KEY and not GEMINI_API_KEY.startswith("AIzaSy"):
        for model in ["gemini-2.0-flash", "gemini-1.5-flash"]:
            try:
                response = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}",
                    json={"contents": [{"role": "user", "parts": [{"text": prompt}]}]}, timeout=8
                )
                if response.status_code == 200:
                    return response.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            except Exception: pass

    try:
        response = requests.get(f"https://text.pollinations.ai/{requests.utils.quote(prompt)}?model=openai&seed=42", timeout=12)
        if response.status_code == 200 and response.text: return response.text.strip()
    except Exception: pass
    return "🤖 نعتذر، تعذر الوصول إلى خوادم الذكاء الاصطناعي حالياً."

# ==========================================
# 7. الرفع المتسلسل الذكي للملفات
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
# 8. ديناميكية القوائم وبناء الواجهة (Routing)
# ==========================================

def show_menu(chat_id):
    path = user_path.setdefault(chat_id, [])
    path_str = get_path_string(chat_id)
    current_menu = get_menu_by_path(path)
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mode = admin_action_mode.get(chat_id)

    if mode == "move_file_dest":
        markup.add(KeyboardButton("📦 أنقل إلى هذا القسم"), KeyboardButton("🛑 إلغاء الأمر"))
        bot.send_message(chat_id, f"📦 تصفح الأقسام للوصول للموقع الجديد ثم اضغط تأكيد.\n📌 المسار الحالي: {path_str or 'الرئيسية'}", reply_markup=markup); return

    if mode == "navigate_to_assign":
        markup.add(KeyboardButton("✅ تعيين مشرف لهذا القسم"), KeyboardButton("🛑 إلغاء الأمر"))

    if not path:
        struct = load_academic_structure()
        for key in struct.keys(): markup.add(KeyboardButton(key))
        markup.add(KeyboardButton("🌟 ميزات الطالب"), KeyboardButton("📖 دليل القسم"))
        markup.add(KeyboardButton("📞 التواصل مع المشرف العام"), KeyboardButton("🛡️ لوحة الإشراف"))
        if is_any_admin(chat_id): markup.add(KeyboardButton("🛑 إنهاء العرض كمستخدم" if testing_mode.get(chat_id) else "👤 عرض كمستخدم"))
        bot.send_message(chat_id, "⚙️ القائمة الرئيسية:", reply_markup=markup); return

    if path_str == "ADMIN_PANEL_ROOT":
        if is_owner(chat_id): markup.add(KeyboardButton("👑 لوحة المشرف الرئيسي"))
        if is_admin(chat_id): markup.add(KeyboardButton("🛡️ لوحة المشرف العام"))
        markup.add("🔙 الرجوع للقائمة الرئيسية")
        bot.send_message(chat_id, "🛡️ *لوحات الإشراف المتاحة لك:*", reply_markup=markup, parse_mode="Markdown"); return

    if path_str == "SUPER_ADMIN_PANEL":
        markup.add("إدارة المشرفين 👥", "صلاحيات المشرفين 🔑")
        markup.add("سجل العمليات 📝", "وضع الطوارئ 🚨")
        markup.add("تعديل نصوص البوت ✏️", "النسخ الاحتياطي اليدوي 💾")
        markup.add("إدارة الأرشفة 🏷️", "إدارة الإعلانات 📢")
        markup.add("التقييمات ⭐️", "إحصائيات المقررات 📊")
        markup.add("حظر مستخدم 🚫", "إضافة مجلد بالرئيسية 📂")
        markup.add("🔙 الرجوع للقائمة الرئيسية")
        bot.send_message(chat_id, "👑 *لوحة المشرف الرئيسي:*", reply_markup=markup, parse_mode="Markdown"); return

    if path_str == "MANAGE_ADMINS":
        markup.add("➕ إضافة مشرف عام", "➕ إضافة مشرف مخصص لمسار")
        markup.add("✅ تفعيل مشرف", "🚫 تعطيل مشرف")
        markup.add("➖ حذف مشرف", "🔍 البحث عن مشرف")
        markup.add("🔙 الرجوع لقائمة المشرف الرئيسية")
        bot.send_message(chat_id, "👥 *إدارة المشرفين:*", reply_markup=markup, parse_mode="Markdown"); return

    if path_str == "ADMIN_PERMISSIONS":
        markup.add("🟢 منح صلاحية محددة", "🔴 سحب صلاحية محددة")
        markup.add("📋 عرض صلاحيات المشرف", "🔙 الرجوع لقائمة المشرف الرئيسية")
        bot.send_message(chat_id, "🔑 *صلاحيات المشرفين:*", reply_markup=markup, parse_mode="Markdown"); return

    if path_str == "GLOBAL_ADMIN_PANEL":
        perms = get_admin_permissions(chat_id)
        if "stats" in perms or "all" in perms: markup.add("📈 إحصائيات النظام", "📊 حالة النظام")
        if "broadcast" in perms or "all" in perms: markup.add("📢 إدارة الإعلانات")
        if "archives" in perms or "all" in perms: markup.add("🏷️ إدارة الأرشفة")
        if "courses_stats" in perms or "all" in perms: markup.add("📊 إحصائيات المقررات")
        markup.add("🔙 الرجوع للقائمة الرئيسية")
        bot.send_message(chat_id, "🛡️ *لوحة المشرف العام:*\nصلاحياتك الحالية:", reply_markup=markup, parse_mode="Markdown"); return

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

    # الأقسام المبرمجة والمجلدات الفعلية
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
        if path_str and not path_str.startswith("SUPER_") and not path_str.startswith("GLOBAL_") and not path_str.startswith("STUDENT_") and not path_str.startswith("FAVORITES") and not path_str.startswith("ADMIN_"):
            markup.add(KeyboardButton("⭐ إضافة هذا القسم للمفضلة"))
            
    bot.send_message(chat_id, f"📂 المسار الحالي:\n`{path_str}`" if path_str else "🏠 الرئيسية:", reply_markup=markup, parse_mode="Markdown")

# ==========================================
# 9. إرسال الملفات مع الأزرار الشفافة للمشرف
# ==========================================

def send_file_to_user(chat_id, res, has_perm):
    try:
        if not res: return
        file_id_str = str(res['_id'])
        share_url = f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}?start={file_id_str}"
        deep_folder_url = f"https://t.me/{BOT_USERNAME}?start=folder_{file_id_str}"

        path_str = res.get('menu_path', '')
        btn_name = "📁 المجلد الرئيسي"
        if path_str:
            parts = path_str.split(' > ')
            clean_parts = [p.replace("🕋","").replace("🇺🇸","").replace("🇾🇪","").replace("📊","").replace("🖥️","").replace("📐","").replace("📃","").replace("📝","").replace("📚","").strip() for p in parts]
            if len(clean_parts) >= 2: btn_name = f"📁 {clean_parts[-1]} - {clean_parts[-2]}"
            elif len(clean_parts) == 1: btn_name = f"📁 {clean_parts[0]}"

        markup = InlineKeyboardMarkup(row_width=2)
        
        # أزرار الإدارة الشفافة تلتصق بالملف هنا
        if has_perm and not testing_mode.get(chat_id):
            markup.add(InlineKeyboardButton("✏️ تسمية", callback_data=f"rn_{file_id_str}"), InlineKeyboardButton("🔄 استبدال", callback_data=f"rp_{file_id_str}"))
            markup.add(InlineKeyboardButton("🗑️ حذف", callback_data=f"dl_{file_id_str}"), InlineKeyboardButton("📦 نقل", callback_data=f"mv_{file_id_str}"))
            markup.add(InlineKeyboardButton("🔼 للأعلى", callback_data=f"up_{file_id_str}"), InlineKeyboardButton("🔽 للأسفل", callback_data=f"dn_{file_id_str}"))
            markup.add(InlineKeyboardButton("📌 تثبيت", callback_data=f"pn_{file_id_str}"))
            
        markup.add(InlineKeyboardButton("🔗 مشاركة", url=share_url), InlineKeyboardButton(btn_name, url=deep_folder_url))
        markup.add(InlineKeyboardButton("📝 تفاصيل", callback_data=f"rl_{file_id_str}"), InlineKeyboardButton("⭐ تقييم", callback_data=f"rt_{file_id_str}"))
        markup.add(InlineKeyboardButton("❤️ المفضلة", callback_data=f"fv_{file_id_str}"))

        file_type = res.get('type', 'document')
        file_id = res.get('file_id')
        base_name = res.get('name', 'وثيقة')
        up_date = res.get('upload_date', datetime.utcnow()).strftime('%Y-%m-%d')
        
        try:
            ratings = list(ratings_col.find({"file_id": file_id_str}))
            avg_rt = sum(r['score'] for r in ratings)/len(ratings) if ratings else 0.0
        except: avg_rt = 0.0
            
        caption = (res.get('caption') or base_name) + f"\n\n📅 {up_date} | 🔻 {res.get('downloads', 0)} | ⭐️ {avg_rt:.1f}/10"

        # الإرسال المباشر يضمن عدم الانفصال وعدم التعليق
        if file_type == 'text': bot.send_message(chat_id, res.get('content', res['name']), reply_markup=markup)
        elif file_type == 'photo' and file_id: bot.send_photo(chat_id, file_id, caption=caption, reply_markup=markup)
        elif file_type == 'video' and file_id: bot.send_video(chat_id, file_id, caption=caption, reply_markup=markup)
        elif file_type == 'audio' and file_id: bot.send_audio(chat_id, file_id, caption=caption, reply_markup=markup)
        elif file_id: bot.send_document(chat_id, file_id, caption=caption, reply_markup=markup)
    except Exception as e: logging.error(f"Send File Error: {e}")


# ==========================================
# 10. أوامر البدء
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
# 11. المعالج المركزي والموجه الذكي الشامل
# ==========================================

@bot.message_handler(content_types=['text', 'document', 'photo', 'video', 'audio'])
def universal_handler(message):
    chat_id = message.chat.id
    user_path.setdefault(chat_id, [])
    
    settings = settings_col.find_one({"_id": "bot_general_settings"}) or {}
    if settings.get("status") == "inactive" and not is_admin(chat_id):
        bot.send_message(chat_id, "🚧 المنصة الأكاديمية تحت الصيانة الدورية حالياً. نعود إليكم فور الانتهاء قريباً."); return 
        
    if message.content_type == 'text':
        if not check_rate_limit(chat_id): return
        
    global system_stats; system_stats["requests_24h"] += 1

    user_data = users_col.find_one({"chat_id": chat_id})
    if user_data and user_data.get("blocked"): return
    
    text = message.text if message.content_type == 'text' else ""
    path_str = get_path_string(chat_id)
    mode = admin_action_mode.get(chat_id)
    is_mod = is_moderator(chat_id, path_str)

    # 1. التوجيه الأساسي والإلغاء (يعمل دائماً كأولوية)
    if text == "🛑 إلغاء الأمر":
        reset_modes(chat_id); bot.send_message(chat_id, "✅ تم الإلغاء."); show_menu(chat_id); return

    struct_instant = load_academic_structure()
    current_menu = get_menu_by_path(user_path.get(chat_id, []))
    
    nav_buttons = [
        "🔝 القائمة الرئيسية", "🔙 الرجوع للقائمة السابقة", "🔙 الرجوع للقائمة الرئيسية", 
        "🌟 ميزات الطالب", "📖 دليل القسم", "⭐ ملفاتي المفضلة", "📞 التواصل مع المشرف العام", 
        "🛡️ لوحة الإشراف", "👑 لوحة المشرف الرئيسي", "🛡️ لوحة المشرف العام", 
        "👥 إدارة المشرفين", "إدارة المشرفين 👥", "🔑 صلاحيات المشرفين", "صلاحيات المشرفين 🔑", 
        "الرجوع للقائمة الرئيسية 🔙", "🔙 الرجوع لقائمة المشرف الرئيسية", "🔙 الرجوع لقائمة المشرف الفرعية",
        "سجل العمليات 📝", "📝 سجل العمليات", "وضع الطوارئ 🚨", "🚨 وضع الطوارئ",
        "النسخ الاحتياطي اليدوي 💾", "💾 النسخ الاحتياطي اليدوي", "إدارة الأرشفة 🏷️", "🏷️ إدارة الأرشفة",
        "التقييمات ⭐️", "⭐️ التقييمات", "إحصائيات المقررات 📊", "📊 إحصائيات المقررات",
        "حظر مستخدم 🚫", "🚫 حظر مستخدم", "إضافة مجلد بالرئيسية 📂", "📂 إضافة مجلد بالرئيسية",
        "تعديل نصوص البوت ✏️", "✏️ تعديل نصوص البوت", "إدارة الإعلانات 📢", "📢 إدارة الإعلانات",
        "👤 عرض كمستخدم", "🛑 إنهاء العرض كمستخدم"
    ] + list(struct_instant.keys())

    # حماية الأوضاع: إذا كان الزر المكتوب هو زر تنقل ثابت، قم بإلغاء وضع التعديل (لكيلا يسمي الملف "رجوع")
    if mode and mode not in ["navigate_to_assign", "move_file_dest"]:
        if text in nav_buttons or text.startswith("📁 ") or text.startswith("📄 ") or text.startswith("📌 ") or text.startswith("🖼️ "):
            reset_modes(chat_id)
            mode = None

    # 2. الأوضاع الإدارية قيد التنفيذ (Rename, add admin, etc)
    if mode == "rename_file" and text:
        files_col.update_one({"_id": ObjectId(action_payload.get(chat_id))}, {"$set": {"name": text.strip()}})
        bot.send_message(chat_id, "✅ تم تغيير اسم الملف بنجاح."); reset_modes(chat_id); show_menu(chat_id); return

    if mode == "replace_file":
        doc = build_file_doc(message, path_str)
        update_data = {"type": doc['type'], "file_id": doc['file_id'], "name": doc['name'], "caption": doc['caption']} if doc['file_id'] else {"type": "text", "content": text, "name": text[:30], "file_id": None}
        files_col.update_one({"_id": ObjectId(action_payload.get(chat_id))}, {"$set": update_data})
        bot.send_message(chat_id, "✅ تم الاستبدال بنجاح."); reset_modes(chat_id); show_menu(chat_id); return

    if mode == "rn_fld" and text:
        old_name = user_path[chat_id][-1]
        parent_p = path_str.rsplit(' > ', 1)[0] if ' > ' in path_str else ""
        new_name = text.strip()
        if rename_in_structure(struct_instant, old_name, new_name):
            settings_col.update_one({"_id": "academic_structure"}, {"$set": {"data": struct_instant}})
        folders_col.update_one({"parent_path": parent_p, "folder_name": old_name}, {"$set": {"folder_name": new_name}})
        old_f = f"{parent_p} > {old_name}" if parent_p else old_name
        new_f = f"{parent_p} > {new_name}" if parent_p else new_name
        for f in files_col.find({"menu_path": {"$regex": f"^{re.escape(old_f)}" }}):
            files_col.update_one({"_id": f["_id"]}, {"$set": {"menu_path": f['menu_path'].replace(old_f, new_f, 1)}})
        for d in folders_col.find({"parent_path": {"$regex": f"^{re.escape(old_f)}" }}):
            folders_col.update_one({"_id": d["_id"]}, {"$set": {"parent_path": d['parent_path'].replace(old_f, new_f, 1)}})
        user_path[chat_id][-1] = new_name
        log_action(chat_id, "RENAME_FOLDER", f"{old_name} to {new_name}")
        bot.send_message(chat_id, "✅ تم التعديل وتحديث المسارات."); reset_modes(chat_id); show_menu(chat_id); return

    if mode == "ai_chat" and text:
        bot.send_message(chat_id, "⏳ جاري التفكير...")
        ans = get_ai_response(text, chat_id)
        ai_memory.setdefault(chat_id, []).append({"prompt": text, "response": ans})
        if len(ai_memory[chat_id]) > 4: ai_memory[chat_id].pop(0)
        bot.send_message(chat_id, ans, parse_mode="Markdown"); return

    if mode == "search_exec" and text:
        query = {"$text": {"$search": text}}
        results = list(files_col.find(query, {"score": {"$meta": "textScore"}}).sort([("score", {"$meta": "textScore"})]).limit(10))
        if not results:
            results = list(files_col.find({"$or": [{"name": {"$regex": text, "$options": "i"}}, {"caption": {"$regex": text, "$options": "i"}}],}).limit(15))
        if results:
            bot.send_message(chat_id, f"🔍 تم العثور على {len(results)} نتائج مطابقة لمقررك:")
            for item in results: send_file_to_user(chat_id, item, is_moderator(chat_id, item['menu_path']))
        else: bot.send_message(chat_id, "❌ لم نجد أي ملفات مطابقة.")
        reset_modes(chat_id); show_menu(chat_id); return

    if mode == "add_glb" and text and is_owner(chat_id):
        try:
            tid = int(text.strip())
            admins_col.update_one({"id": tid}, {"$set": {"id": tid, "type": "global", "permissions": ["all"], "active": True}}, upsert=True)
            log_action(chat_id, "ADD_ADMIN", f"ID: {tid}"); bot.send_message(chat_id, "✅ تمت الإضافة بنجاح."); reset_modes(chat_id); show_menu(chat_id)
        except: bot.send_message(chat_id, "❌ يرجى إرسال أرقام فقط.")
        return

    if mode == "ask_path_admin_id" and text and is_owner(chat_id):
        try:
            tid = int(text.strip())
            admins_col.update_one({"id": tid}, {"$set": {"id": tid, "type": "path", "active": True}, "$addToSet": {"allowed_paths": path_str}}, upsert=True)
            log_action(chat_id, "ASSIGN_PATH_ADMIN", f"ID: {tid} Path: {path_str}"); bot.send_message(chat_id, "✅ تم تعيين المشرف.")
            reset_modes(chat_id); show_menu(chat_id)
        except: bot.send_message(chat_id, "❌ يرجى إرسال أرقام فقط.")
        return

    if mode == "rm_adm" and text and is_owner(chat_id):
        try:
            tid = int(text.strip())
            if tid != SUPER_ADMIN_ID:
                admins_col.delete_one({"id": tid}); log_action(chat_id, "RM_ADMIN", f"ID: {tid}")
                bot.send_message(chat_id, "✅ تم حذف المشرف نهائياً.")
            reset_modes(chat_id); show_menu(chat_id)
        except: bot.send_message(chat_id, "❌ يرجى إرسال أرقام فقط.")
        return

    if mode == "deac_adm" and text and is_owner(chat_id):
        try:
            tid = int(text.strip())
            if tid != SUPER_ADMIN_ID:
                admins_col.update_one({"id": tid}, {"$set": {"active": False}}); log_action(chat_id, "DISABLE_ADMIN", f"ID: {tid}")
                bot.send_message(chat_id, "✅ تم التعطيل.")
            reset_modes(chat_id); show_menu(chat_id)
        except: bot.send_message(chat_id, "❌ يرجى إرسال أرقام فقط.")
        return

    if mode == "ac_adm" and text and is_owner(chat_id):
        try:
            tid = int(text.strip())
            admins_col.update_one({"id": tid}, {"$set": {"active": True}}); log_action(chat_id, "ENABLE_ADMIN", f"ID: {tid}"); bot.send_message(chat_id, "✅ تم التفعيل.")
            reset_modes(chat_id); show_menu(chat_id)
        except: bot.send_message(chat_id, "❌ يرجى إرسال أرقام فقط.")
        return

    if mode == "srch_adm" and text and is_owner(chat_id):
        try:
            adm = admins_col.find_one({"id": int(text.strip())})
            bot.send_message(chat_id, f"👤 نوعه: {adm.get('type')}\nنشط: {adm.get('active', True)}\nصلاحيات: {adm.get('permissions', [])}" if adm else "❌ غير مسجل.")
            reset_modes(chat_id); show_menu(chat_id)
        except: bot.send_message(chat_id, "❌ يرجى إرسال أرقام فقط.")
        return

    if mode == "gnt_prm1" and text and is_owner(chat_id):
        try:
            action_payload[chat_id] = int(text.strip()); admin_action_mode[chat_id] = "gnt_prm2"
            m = ReplyKeyboardMarkup(resize_keyboard=True).add("إعلانات", "إحصائيات", "طوارئ", "تعديل نصوص", "أرشفة").add("إحصائيات المقررات", "إدارة المستخدمين").add("🛑 إلغاء الأمر")
            bot.send_message(chat_id, "اختر الصلاحية لمنحها إياها:", reply_markup=m)
        except: bot.send_message(chat_id, "❌ يرجى إرسال أرقام فقط.")
        return
    if mode == "gnt_prm2" and text and is_owner(chat_id):
        p_map = {"إعلانات":"broadcast", "إحصائيات":"stats", "طوارئ":"emergency", "تعديل نصوص":"texts", "أرشفة":"archives", "إحصائيات المقررات":"courses_stats", "إدارة المستخدمين":"users_mgt"}
        if text in p_map:
            admins_col.update_one({"id": action_payload.get(chat_id)}, {"$addToSet": {"permissions": p_map[text]}})
            bot.send_message(chat_id, "✅ تم منح الصلاحية بنجاح."); reset_modes(chat_id); show_menu(chat_id); return

    if mode == "rvk_prm1" and text and is_owner(chat_id):
        try:
            action_payload[chat_id] = int(text.strip()); admin_action_mode[chat_id] = "rvk_prm2"
            m = ReplyKeyboardMarkup(resize_keyboard=True).add("إعلانات", "إحصائيات", "طوارئ", "تعديل نصوص", "أرشفة").add("إحصائيات المقررات", "إدارة المستخدمين").add("🛑 إلغاء الأمر")
            bot.send_message(chat_id, "اختر الصلاحية لسحبها منه:", reply_markup=m)
        except: bot.send_message(chat_id, "❌ أرقام فقط.")
        return
    if mode == "rvk_prm2" and text and is_owner(chat_id):
        p_map = {"إعلانات":"broadcast", "إحصائيات":"stats", "طوارئ":"emergency", "تعديل نصوص":"texts", "أرشفة":"archives", "إحصائيات المقررات":"courses_stats", "إدارة المستخدمين":"users_mgt"}
        if text in p_map:
            admins_col.update_one({"id": action_payload.get(chat_id)}, {"$pull": {"permissions": p_map[text]}})
            bot.send_message(chat_id, "✅ تم سحب الصلاحية."); reset_modes(chat_id); show_menu(chat_id); return

    if mode == "vw_prms" and text and is_owner(chat_id):
        try:
            adm = admins_col.find_one({"id": int(text.strip())})
            bot.send_message(chat_id, f"🔑 الصلاحيات الممنوحة: {adm.get('permissions', [])}" if adm else "❌ غير موجود."); reset_modes(chat_id); show_menu(chat_id)
        except: bot.send_message(chat_id, "❌ أرقام فقط."); return

    if mode and mode.startswith("edit_txt_") and text:
        k = "start_text" if "Start" in mode else ("info_text" if "Info" in mode else ("sci_text" if "اللجنة" in mode else "dev_text"))
        settings_col.update_one({"_id": "bot_general_settings"}, {"$set": {k: text}}, upsert=True)
        bot.send_message(chat_id, "✅ تم حفظ التحديث بنجاح."); reset_modes(chat_id); show_menu(chat_id); return

    if mode == "set_rem_text" and text:
        action_payload[chat_id] = text; admin_action_mode[chat_id] = "set_rem_time"
        bot.send_message(chat_id, "بعد كم ساعة؟ (أرقام فقط):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return
    if mode == "set_rem_time" and text:
        try:
            reminders_col.insert_one({"chat_id": chat_id, "text": action_payload[chat_id], "notify_at": datetime.utcnow() + timedelta(hours=float(text.strip()))})
            bot.send_message(chat_id, "✅ تم الجدولة.")
        except: bot.send_message(chat_id, "❌ أرقام فقط."); reset_modes(chat_id); show_menu(chat_id); return

    if mode == "blk_usr" and text and is_owner(chat_id):
        try:
            tid = int(text.strip())
            if tid == SUPER_ADMIN_ID: bot.send_message(chat_id, "❌ لا يمكن حظر المطور.")
            else:
                u = users_col.find_one({"chat_id": tid})
                if u:
                    ns = not u.get("blocked", False)
                    users_col.update_one({"_id": u["_id"]}, {"$set": {"blocked": ns}})
                    bot.send_message(chat_id, f"✅ الحالة: {'محظور 🚫' if ns else 'نشط ✅'}")
                else: bot.send_message(chat_id, "❌ غير مسجل.")
        except: bot.send_message(chat_id, "❌ يرجى إرسال أرقام فقط.")
        reset_modes(chat_id); show_menu(chat_id); return

    if broadcast_mode.get(chat_id) and text:
        broadcast_mode[chat_id] = False
        settings_col.update_one({"_id": "bot_general_settings"}, {"$set": {"last_announcement": text}}, upsert=True)
        bot.send_message(chat_id, "⏳ جاري إرسال وبث الإعلان...")
        b_succ = 0
        for stu in list(users_col.find()):
            try: bot.copy_message(stu['chat_id'], chat_id, message.message_id); b_succ += 1
            except: pass
        bot.send_message(chat_id, f"✅ تم البث لـ {b_succ} طالب."); show_menu(chat_id); return

    # 3. معالجة أوامر التوجيه والملاحة العالمية 
    if text in main_nav:
        if text in ["🔝 القائمة الرئيسية", "🔙 الرجوع للقائمة الرئيسية", "الرجوع للقائمة الرئيسية 🔙"]: user_path[chat_id] = []
        elif text in ["🔙 الرجوع للقائمة السابقة", "🔙 الرجوع لقائمة المشرف الفرعية"] and user_path.get(chat_id): user_path[chat_id].pop()
        elif text == "🔙 الرجوع لقائمة المشرف الرئيسية": user_path[chat_id] = ["SUPER_ADMIN_PANEL"]
        elif text in struct_instant.keys(): user_path[chat_id] = [text]
        elif text == "🌟 ميزات الطالب": user_path[chat_id] = ["STUDENT_FEATURES"]
        elif text == "⭐ ملفاتي المفضلة": user_path[chat_id] = ["FAVORITES"]
        elif text == "🛡️ لوحة الإشراف": user_path[chat_id] = ["ADMIN_PANEL_ROOT"]
        elif text == "👑 لوحة المشرف الرئيسي" and is_owner(chat_id): user_path[chat_id] = ["SUPER_ADMIN_PANEL"]
        elif text == "🛡️ لوحة المشرف العام" and is_admin(chat_id): user_path[chat_id] = ["GLOBAL_ADMIN_PANEL"]
        elif (text == "👥 إدارة المشرفين" or text == "إدارة المشرفين 👥") and is_owner(chat_id): user_path[chat_id] = ["SUPER_ADMIN_PANEL", "MANAGE_ADMINS"]
        elif (text == "🔑 صلاحيات المشرفين" or text == "صلاحيات المشرفين 🔑") and is_owner(chat_id): user_path[chat_id] = ["SUPER_ADMIN_PANEL", "ADMIN_PERMISSIONS"]
        elif text == "📞 التواصل مع المشرف العام":
            dev_msg = settings.get("dev_text", DEFAULT_DEV_TEXT)
            markup = InlineKeyboardMarkup(row_width=1)
            markup.add(
                InlineKeyboardButton("❓ استفسار أكاديمي", url="https://t.me/AlwatheqAssag"),
                InlineKeyboardButton("📝 ملاحظات", url="https://t.me/AlwatheqAssag"),
                InlineKeyboardButton("⚠️ بلاغ عن مشكلة", url="https://t.me/AlwatheqAssag"),
                InlineKeyboardButton("📤 إرسال ملف", url="https://t.me/AlwatheqAssag"),
                InlineKeyboardButton("💬 فتح محادثة", url="https://t.me/AlwatheqAssag")
            )
            bot.send_message(chat_id, dev_msg, reply_markup=markup, parse_mode="Markdown")
            return
        
        elif (text == "سجل العمليات 📝" or text == "📝 سجل العمليات") and is_owner(chat_id):
            logs = list(action_logs_col.find().sort("timestamp", -1).limit(20))
            msg = "📝 *سجل الإجراءات والعمليات الإدارية:*\n\n"
            for lg in logs: msg += f"🔸 `{lg['timestamp'].strftime('%m-%d %H:%M')}`\n👤 {lg.get('admin_name','-')} | ⚙️ {lg['action']}\n\n"
            bot.send_message(chat_id, msg if logs else "السجل خالي من العمليات.", parse_mode="Markdown"); return
            
        elif (text == "وضع الطوارئ 🚨" or text == "🚨 وضع الطوارئ") and (is_owner(chat_id) or "emergency" in get_admin_permissions(chat_id)):
            flags = settings.get("emergency_flags", {})
            m = ReplyKeyboardMarkup(resize_keyboard=True)
            m.add(f"{'🟢' if not flags.get('ai') else '🔴'} الذكاء الاصطناعي", f"{'🟢' if not flags.get('upload') else '🔴'} الرفع")
            m.add(f"{'🟢' if not flags.get('search') else '🔴'} البحث", f"{'🟢' if not flags.get('ads') else '🔴'} الإعلانات")
            m.add("🟢 تشغيل البوت كلياً" if settings.get("status") == "inactive" else "🛑 إيقاف البوت كلياً", "🔙 الرجوع لقائمة المشرف الرئيسية")
            bot.send_message(chat_id, "🚨 *لوحة تحكم الطوارئ المركزية:*", reply_markup=m, parse_mode="Markdown"); return

        elif (text == "النسخ الاحتياطي اليدوي 💾" or text == "💾 النسخ الاحتياطي اليدوي") and is_owner(chat_id):
            bot.send_message(chat_id, "⏳ جاري تصدير قواعد البيانات حيوياً...")
            bkp = {"files": list(files_col.find({}, {"_id": 0})), "folders": list(folders_col.find({}, {"_id": 0}))}
            bio = io.BytesIO(json.dumps(bkp, default=json_util.default, ensure_ascii=False).encode('utf-8'))
            bio.name = "DB_Backup.json"
            bot.send_document(chat_id, bio, caption="💾 نسخة احتياطية آمنة (JSON)."); return

        elif (text == "إدارة الأرشفة 🏷️" or text == "🏷️ إدارة الأرشفة") and (is_owner(chat_id) or "archives" in get_admin_permissions(chat_id)):
            archive_markup = ReplyKeyboardMarkup(resize_keyboard=True).add("📋 عرض الهاشتاجات", "🗑️ حذف هاشتاج").add("🔙 الرجوع لقائمة المشرف الرئيسية")
            bot.send_message(chat_id, "🏷️ *إدارة منظومة الأرشفة التلقائية:*", reply_markup=archive_markup, parse_mode="Markdown"); return

        elif (text == "التقييمات ⭐️" or text == "⭐️ التقييمات") and is_admin(chat_id):
            top = list(ratings_col.aggregate([{"$group": {"_id": "$file_id", "avg": {"$avg": "$score"}, "cnt": {"$sum": 1}}}, {"$sort": {"avg": -1}}, {"$limit": 10}]))
            msg = "⭐️ *أعلى 10 ملفات تقييماً من قِبل الطلاب:*\n"
            for r in top:
                f = files_col.find_one({"_id": ObjectId(r["_id"])})
                if f: msg += f"• {f['name']} | متوسط: {r['avg']:.1f}/10 ({r['cnt']} أصوات)\n"
            bot.send_message(chat_id, msg if top else "لا توجد تقييمات مسجلة حالياً.", parse_mode="Markdown"); return

        elif (text == "إحصائيات المقررات 📊" or text == "📊 إحصائيات المقررات") and is_admin(chat_id):
            stats = list(files_col.aggregate([{"$match": {"menu_path": {"$regex": "^🌱|^🌿|^☘️|^🌳"}}}, {"$group": {"_id": "$menu_path", "count": {"$sum": 1}, "downloads": {"$sum": "$downloads"}}}, {"$sort": {"downloads": -1}}, {"$limit": 15}]))
            msg = "📊 *الإحصائيات التفصيلية للمقررات الدراسية:*\n\n"
            for s in stats: msg += f"📁 `{s['_id']}`\n📄 ملفات: {s['count']} | 🔻 تحميلات: {s['downloads']}\n\n"
            bot.send_message(chat_id, msg if stats else "لا توجد إحصائيات للمقررات بعد.", parse_mode="Markdown"); return

        elif (text == "حظر مستخدم 🚫" or text == "🚫 حظر مستخدم") and is_owner(chat_id):
            reset_modes(chat_id); admin_action_mode[chat_id] = "blk_usr"
            bot.send_message(chat_id, "🚫 أرسل المعرف الرقمي (ID) للطالب المراد حظره:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

        elif (text == "إضافة مجلد بالرئيسية 📂" or text == "📂 إضافة مجلد بالرئيسية") and is_owner(chat_id):
            reset_modes(chat_id); add_folder_mode[chat_id] = True; user_path[chat_id] = []
            bot.send_message(chat_id, "📂 اكتب اسم المجلد الجديد للمجلد المراد زرعه بالصفحة الرئيسية:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

        elif (text == "تعديل نصوص البوت ✏️" or text == "✏️ تعديل نصوص البوت") and (is_owner(chat_id) or "texts" in get_admin_permissions(chat_id)):
            reset_modes(chat_id)
            m = ReplyKeyboardMarkup(resize_keyboard=True).add("✏️ تعديل Start", "✏️ تعديل Info").add("✏️ تعديل المطور", "✏️ تعديل اللجنة").add("🛑 إلغاء الأمر")
            bot.send_message(chat_id, "يرجى اختيار النص المراد تعديله:", reply_markup=m); return

        elif (text == "إدارة الإعلانات 📢" or text == "📢 إدارة الإعلانات") and (is_owner(chat_id) or "broadcast" in get_admin_permissions(chat_id)):
            reset_modes(chat_id); broadcast_mode[chat_id] = True
            bot.send_message(chat_id, "📢 الرجاء إرسال الإعلان الموجه للدفعة البث فوري ولحظي لحسابات الطلاب:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

        elif text == "👤 عرض كمستخدم" and (is_admin(chat_id) or is_moderator(chat_id)):
            testing_mode[chat_id] = True; user_path[chat_id] = []
            bot.send_message(chat_id, "👀 وضع الطالب مفعل: تتصفح المنصة كطالب عادي الآن.")
        elif text == "🛑 إنهاء العرض كمستخدم" and testing_mode.get(chat_id):
            testing_mode[chat_id] = False; user_path[chat_id] = []
            bot.send_message(chat_id, "💼 تم إنهاء وضع الطالب، عدت للإدارة.")
            
        show_menu(chat_id); return

    if text == "اللجنة العلمية" and path_str == "🌱 مستوى أول":
        bot.send_message(chat_id, settings.get("sci_text", DEFAULT_SCI_TEXT)); return

    if text == "⭐ إضافة هذا القسم للمفضلة":
        if path_str:
            users_col.update_one({"chat_id": chat_id}, {"$addToSet": {"favorites": "path:" + path_str}})
            bot.send_message(chat_id, "✅ تم إضافة القسم للمفضلة بنجاح.")
        return

    # 4. فتح المجلدات والدخول للمسارات (حل مشكلة المجلدات الميتة)
    if text not in main_nav and isinstance(current_menu, dict) and text in current_menu.keys():
        user_path[chat_id].append(text)
        show_menu(chat_id)
        return

    if text.startswith("📁 "):
        folder_name = text[2:].strip()
        user_path[chat_id].append(folder_name)
        show_menu(chat_id)
        return

    # 5. استدعاء الملفات الآمن والبحث المرن في قاعدة البيانات
    if text and (text.startswith("📄 ") or text.startswith("📌 ") or text.startswith("🖼️ ")):
        ex_name = text[2:].strip()
        f_doc = files_col.find_one({"menu_path": path_str, "name": {"$regex": f"^{re.escape(ex_name)}$", "$options": "i"}})
        if f_doc:
            files_col.update_one({"_id": f_doc["_id"]}, {"$inc": {"downloads": 1}})
            send_file_to_user(chat_id, f_doc, is_mod)
        return

    # 6. الأوامر المتبقية المستقلة
    if text == "➕ إضافة مشرف عام" and is_owner(chat_id):
        reset_modes(chat_id); admin_action_mode[chat_id] = "add_glb"
        bot.send_message(chat_id, "أرسل المعرف الرقمي (ID) للمشرف العام الجديد:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

    if text == "➕ إضافة مشرف مخصص لمسار" and is_owner(chat_id):
        reset_modes(chat_id); admin_action_mode[chat_id] = "navigate_to_assign"; user_path[chat_id] = []
        bot.send_message(chat_id, "📍 يرجى تصفح الأقسام للوصول للمقرر المطلوب، ثم اضغط (✅ تعيين مشرف لهذا القسم)."); show_menu(chat_id); return

    if text == "✅ تعيين مشرف لهذا القسم" and mode == "navigate_to_assign" and is_owner(chat_id):
        admin_action_mode[chat_id] = "ask_path_admin_id"
        bot.send_message(chat_id, f"👤 المسار المختار: `{path_str}`\nأرسل الآيدي (ID) للمشرف المخصص:", parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

    if text == "➖ حذف مشرف" and is_owner(chat_id):
        reset_modes(chat_id); admin_action_mode[chat_id] = "rm_adm"
        bot.send_message(chat_id, "أرسل الآيدي لحذفه نهائياً من النظام:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

    if text == "🚫 تعطيل مشرف" and is_owner(chat_id):
        reset_modes(chat_id); admin_action_mode[chat_id] = "deac_adm"
        bot.send_message(chat_id, "أرسل الآيدي لإيقاف صلاحياته مؤقتاً:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

    if text == "✅ تفعيل مشرف" and is_owner(chat_id):
        reset_modes(chat_id); admin_action_mode[chat_id] = "ac_adm"
        bot.send_message(chat_id, "أرسل الآيدي لتفعيله مجدداً:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

    if text == "🔍 البحث عن مشرف" and is_owner(chat_id):
        reset_modes(chat_id); admin_action_mode[chat_id] = "srch_adm"
        bot.send_message(chat_id, "أرسل الآيدي المراد فحصه:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

    if text == "🟢 منح صلاحية محددة" and is_owner(chat_id):
        reset_modes(chat_id); admin_action_mode[chat_id] = "gnt_prm1"
        bot.send_message(chat_id, "أرسل آيدي المشرف الممنوح له الصلاحية:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

    if text == "🔴 سحب صلاحية محددة" and is_owner(chat_id):
        reset_modes(chat_id); admin_action_mode[chat_id] = "rvk_prm1"
        bot.send_message(chat_id, "أرسل آيدي المشرف لسحب الصلاحية منه:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

    if text == "📋 عرض صلاحيات المشرف" and is_owner(chat_id):
        reset_modes(chat_id); admin_action_mode[chat_id] = "vw_prms"
        bot.send_message(chat_id, "أرسل الآيدي لاستجواب صلاحياته:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

    if text == "🤖 المساعد الذكي (AI)":
        if settings.get("emergency_flags", {}).get("ai", False) and not is_owner(chat_id):
            bot.send_message(chat_id, "🚧 المساعد الذكي معطل مؤقتاً للصيانة."); return
        if not check_ai_quota(chat_id):
            bot.send_message(chat_id, "⚠️ لقد استنفدت محاولاتك اليومية (7/7). سيتم تجديدها تلقائياً غداً."); return
        reset_modes(chat_id); admin_action_mode[chat_id] = "ai_chat"
        if chat_id not in ai_memory: ai_memory[chat_id] = []
        bot.send_message(chat_id, "🤖 أهلاً بك، تفضل بطرح سؤالك أو استفسارك الأكاديمي:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

    if text == "🔍 بحث عن ملف":
        if settings.get("emergency_flags", {}).get("search", False) and not is_owner(chat_id):
            bot.send_message(chat_id, "🚧 محرك البحث معطل حالياً."); return
        reset_modes(chat_id); admin_action_mode[chat_id] = "search_exec"
        bot.send_message(chat_id, "🔍 الرجاء إرسال الكلمة المفتاحية للبحث:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

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

    if text == "📋 عرض الهاشتاجات" and is_admin(chat_id):
        active_tags = list(hashtags_col.find())
        h_msg = "🏷️ *الروابط والهاشتاجات الفعالة حالياً بالمنصة:*\n\n" + "".join([f"🔸 {t['tag']} ⇦ {t['path'].split(' > ')[-1]}\n" for t in active_tags])
        bot.send_message(chat_id, h_msg if active_tags else "لا توجد هاشتاجات أرشفة مسجلة حالياً.", parse_mode="Markdown"); return
        
    if text == "🗑️ حذف هاشتاج" and is_admin(chat_id):
        reset_modes(chat_id); admin_action_mode[chat_id] = "del_hashtag"
        bot.send_message(chat_id, "أرسل الهاشتاج المراد حذفه وإلغاء أتمتته:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return
        
    if mode == "del_hashtag" and text:
        final_tag = text.strip() if text.strip().startswith("#") else "#" + text.strip()
        hashtags_col.delete_one({"tag": final_tag})
        bot.send_message(chat_id, f"✅ تم حذف وإبطال مفعول الهاشتاج {final_tag} بنجاح."); reset_modes(chat_id); show_menu(chat_id); return

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

    # 7. الإداريات المباشرة داخل الأقسام الأكاديمية (إضافة، مجلد، تعديل، حذف)
    if path_str and path_str not in ["SUPER_ADMIN_PANEL", "GLOBAL_ADMIN_PANEL", "STUDENT_FEATURES", "FAVORITES", "MANAGE_ADMINS", "ADMIN_PERMISSIONS", "ADMIN_PANEL_ROOT"]:
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

    # 8. الاستقبال الدفعي
    if message.content_type in ['document', 'photo', 'video', 'audio'] and upload_mode.get(chat_id):
        if settings.get("emergency_flags", {}).get("upload", False) and not is_owner(chat_id):
            bot.send_message(chat_id, "🚧 عذراً، استقبال الملفات معطل حالياً للصيانة."); return
        
        if chat_id not in upload_batches: upload_batches[chat_id] = []
        upload_batches[chat_id].append(message)
        if chat_id in upload_timers: upload_timers[chat_id].cancel()
        upload_timers[chat_id] = threading.Timer(4.0, process_user_batch, args=[chat_id, path_str, is_mod])
        upload_timers[chat_id].start()
        return


# ==========================================
# 12. أزرار التحكم الجانبية (الحل الجذري لمشكلة الأزرار المعلقة)
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith(('rn_', 'rp_', 'dl_', 'mv_', 'up_', 'dn_', 'pn_', 'fv_', 'rt_', 'str_', 'rl_')))
def handle_inline_callbacks(call):
    chat_id = call.message.chat.id
    try: action, obj_id = call.data.split('_', 1)
    except: return

    # [مهم جداً: هذا السطر يمنع الدوران الوهمي (التعليق) لجميع الأزرار الشفافة]
    bot.answer_callback_query(call.id) 

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
        bot.send_message(chat_id, "🔄 الرجاء إرسال الملف البديل الآن ليعوض الملف الحالي:")
    elif action == 'mv':
        reset_modes(chat_id); admin_action_mode[chat_id] = "move_file_dest"; action_payload[chat_id] = obj_id
        bot.send_message(chat_id, "📦 يرجى تصفح الأقسام للوصول لموقع النقل واضغط زر التأكيد.")
        user_path[chat_id] = []; show_menu(chat_id)
    elif action in ['up', 'dn', 'pn']:
        if action == 'pn': files_col.update_one({"_id": ObjectId(obj_id)}, {"$set": {"sort_order": -999}})
        else: files_col.update_one({"_id": ObjectId(obj_id)}, {"$inc": {"sort_order": -1 if action == 'up' else 1}})
        bot.answer_callback_query(call.id, "✅ تم تحديث الترتيب بنجاح.", show_alert=False); show_menu(chat_id)

# ==========================================
# 13. تشغيل السيرفر (Webhook Setup)
# ==========================================

@app.route('/webhook', methods=['POST'])
def webhook_listen_route():
    if request.headers.get('content-type') == 'application/json':
        bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
        return "!", 200
    return "Invalid", 403

@app.route("/")
def index_home_route(): return "Bot V5.9.1 LMS Master Active & Running 🚀", 200

from flask import redirect

@app.route('/f/<folder_id>')
def redirect_to_folder(folder_id):
    return redirect(f"https://t.me/{BOT_USERNAME}?start=folder_{folder_id}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
