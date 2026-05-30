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

# ==========================================
# 2. النصوص الافتراضية للرسائل (قابلة للتعديل)
# ==========================================
DEFAULT_START_TEXT = (
    "🌟 أهلاً وسهلاً بك يا {first_name} في المنصة الأكاديمية الرسمية لقسم الذكاء الاصطناعي وعلوم البيانات (AI & DS) 🎓\n\n"
    "مرحباً بك في بوابتك التعليمية الرقمية، حيث يمكنك الوصول بسهولة إلى المحاضرات، الملخصات، نماذج الاختبارات، والمواد الأكاديمية المنظمة لجميع المستويات والمقررات الدراسية.\n\n"
    "✨ توفر لك المنصة:\n\n"
    "📚 أرشيف أكاديمي منظم للمحاضرات والملخصات.\n"
    "📝 نماذج اختبارات وتجميعات سابقة.\n"
    "🤖 مساعد ذكي للإجابة على الاستفسارات الأكاديمية والبرمجية.\n"
    "🔍 محرك بحث سريع للوصول إلى الملفات.\n"
    "🔔 تنبيهات وإشعارات أكاديمية مهمة.\n"
    "⏰ أدوات مساعدة لتنظيم الدراسة والمتابعة.\n\n"
    "💡 هدفنا هو توفير بيئة تعليمية منظمة تسهّل الوصول إلى المعرفة وتدعم رحلتك الأكاديمية نحو التميز.\n\n"
    "👇 اختر القسم أو الخدمة التي ترغب بالوصول إليها من القائمة التالية:"
)

DEFAULT_INFO_TEXT = (
    "🤖 المنصة الأكاديمية الذكية لقسم الذكاء الاصطناعي وعلوم البيانات (AI & DS)\n\n"
    "تم إنشاء هذه المنصة لتكون مركزاً أكاديمياً رقمياً موحداً يساعد طلاب القسم على الوصول إلى الموارد التعليمية بسهولة وسرعة ومن أي مكان.\n\n"
    "━━━━━━━━━━━━━━\n"
    "📚 الأرشيف الأكاديمي\n"
    "━━━━━━━━━━━━━━\n\n"
    "يوفر البوت وصولاً منظماً إلى:\n\n"
    "• المحاضرات النظرية والعملية.\n"
    "• الملخصات والمراجع الدراسية.\n"
    "• نماذج الاختبارات السابقة.\n"
    "• المشاريع والتمارين الأكاديمية.\n"
    "• المواد التعليمية المضافة من الطلاب والمشرفين.\n\n"
    "━━━━━━━━━━━━━━\n"
    "🤖 المساعد الذكي\n"
    "━━━━━━━━━━━━━━\n\n"
    "يمكنك طرح الأسئلة المتعلقة بـ:\n\n"
    "• البرمجة وعلوم الحاسب.\n"
    "• الذكاء الاصطناعي وعلوم البيانات.\n"
    "• الرياضيات والإحصاء.\n"
    "• المفاهيم الأكاديمية العامة.\n\n"
    "وسيحاول المساعد تقديم أفضل إجابة ممكنة اعتماداً على مصادره وقاعدة المعرفة المتاحة.\n\n"
    "━━━━━━━━━━━━━━\n"
    "🌟 الأدوات الطلابية\n"
    "━━━━━━━━━━━━━━\n\n"
    "• البحث السريع عن الملفات.\n"
    "• التذكيرات الشخصية.\n"
    "• التنبيهات الأكاديمية.\n"
    "• متابعة النشاط والملفات الحديثة.\n\n"
    "━━━━━━━━━━━━━━\n"
    "🎯 رؤيتنا\n"
    "━━━━━━━━━━━━━━\n\n"
    "بناء منصة تعليمية رقمية متكاملة تسهّل مشاركة المعرفة وتنظيم المحتوى الأكاديمي وتدعم طلاب قسم الذكاء الاصطناعي وعلوم البيانات في مسيرتهم العلمية.\n\n"
    "نتمنى لكم التوفيق والنجاح والتميز في رحلتكم الجامعية. 🚀📚"
)

DEFAULT_DEV_TEXT = (
    "✉️ *التواصل مع إدارة المنصة*\n\n"
    "البوت تحت تطوير وتحديث متواصل، وجاهزين لاستقبال الاستفسارات والملفات الإثرائية.\n\n"
    "للتواصل والاستفسار:\n"
    "المشرف العام : (@AlwatheqAssag)"
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
    reminders_col = db['personal_reminders']
    action_logs_col = db['action_logs']
    ratings_col = db['file_ratings']
    
    files_col.create_index([("name", "text"), ("caption", "text")])
    logging.info("Database Connected Flawlessly! 🎉")
except Exception as db_err:
    logging.error(f"MongoDB Connection Error: {db_err}")

if admins_col.count_documents({"id": SUPER_ADMIN_ID}) == 0:
    admins_col.insert_one({"id": SUPER_ADMIN_ID, "type": "super", "allowed_paths": [], "permissions": ["all"]})
if settings_col.count_documents({}) == 0:
    settings_col.insert_one({
        "status": "active",
        "emergency_flags": {"ai": False, "upload": False, "search": False, "announcements": False}
    })

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)
BOT_USERNAME = bot.get_me().username
media_groups = {}  

# ==========================================
# 4. الهيكل الأكاديمي الصارم
# ==========================================
ACADEMIC_STRUCTURE = {
    "🌱 مستوى أول": {
        "📅 ترم أول": {},
        "📅 ترم ثاني": {},
        "اللجنة العلمية": {}
    },
    "🌿 مستوى ثاني": {"📅 ترم أول": {}, "📅 ترم ثاني": {}},
    "☘️ مستوى ثالث": {"📅 ترم أول": {}, "📅 ترم ثاني": {}},
    "🌳 مستوى رابع": {"📅 ترم أول": {}, "📅 ترم ثاني": {}},
    "📚 معلومات أكاديمية عن التخصص": {},
    "🌟 ميزات مساعدة للطالب": {}  
}

user_path, upload_mode, add_folder_mode = {}, {}, {}
admin_action_mode, testing_mode, action_payload = {}, {}, {}
broadcast_mode, ai_memory, RATE_LIMIT_DICT = {}, {}, {}

# ==========================================
# 5. دوال التحكم والصلاحيات
# ==========================================
def is_super_admin(chat_id): return chat_id == SUPER_ADMIN_ID

def is_global_admin(chat_id):
    admin = admins_col.find_one({"id": chat_id})
    return admin is not None and admin.get("type") in ["global", "super"]

def is_any_admin(chat_id): return chat_id == SUPER_ADMIN_ID or admins_col.find_one({"id": chat_id}) is not None

def get_admin_permissions(chat_id):
    if is_super_admin(chat_id): return ["all"]
    admin = admins_col.find_one({"id": chat_id})
    return admin.get("permissions", []) if admin else []

def has_permission(chat_id, current_path_str):
    if testing_mode.get(chat_id): return False
    if is_super_admin(chat_id): return True
    admin = admins_col.find_one({"id": chat_id})
    if not admin: return False
    if admin.get("type") in ["global", "super"]: return True
    for allowed_p in admin.get("allowed_paths", []):
        if current_path_str.startswith(allowed_p) or current_path_str == allowed_p: return True
    return False

def log_action(admin_id, action_type, details):
    action_logs_col.insert_one({"admin_id": admin_id, "action": action_type, "details": details, "timestamp": datetime.utcnow()})

def get_menu_by_path(path):
    menu = ACADEMIC_STRUCTURE
    for segment in path:
        if isinstance(menu, dict) and segment in menu: menu = menu[segment]
        else: return None
    return menu

def get_path_string(chat_id): return " > ".join(user_path.get(chat_id, []))

def reset_modes(chat_id, clear_upload=True):
    if clear_upload: upload_mode[chat_id] = False
    add_folder_mode[chat_id], broadcast_mode[chat_id] = False, False
    admin_action_mode[chat_id] = None
    action_payload.pop(chat_id, None)

def check_rate_limit(chat_id):
    now = time.time()
    if chat_id in RATE_LIMIT_DICT and now - RATE_LIMIT_DICT[chat_id] < 1.0:
        return False
    RATE_LIMIT_DICT[chat_id] = now
    return True

# ==========================================
# 6. محرك الذكاء الاصطناعي مع الكاش والذاكرة
# ==========================================
def get_ai_response(prompt, chat_id):
    settings = settings_col.find_one({})
    if settings.get("emergency_flags", {}).get("ai", False) and not is_any_admin(chat_id):
        return "🚧 المساعد الذكي معطل مؤقتاً لأغراض الصيانة بقرار من الإدارة."

    context = "السياق السابق: " + " | ".join(ai_memory[chat_id][-2:]) + "\nالسؤال الحالي: " if chat_id in ai_memory and ai_memory[chat_id] else ""
    clean_prompt = f"أنت مساعد أكاديمي لجامعة تعز (الذكاء الاصطناعي وعلوم البيانات). أجب باختصار ودقة: {context}{prompt}"
    
    if GEMINI_API_KEY and not GEMINI_API_KEY.startswith("AIzaSy"):
        for model_name in ["gemini-2.0-flash-lite-preview-02-05", "gemini-2.0-flash", "gemini-1.5-flash"]:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
                payload = {"contents": [{"parts": [{"text": clean_prompt}]}], "generationConfig": {"temperature": 0.4, "maxOutputTokens": 600}}
                res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=7)
                if res.status_code == 200: return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            except: continue

    for backup_model in ["openai", "llama", "mistral"]:
        try:
            encoded_prompt = requests.utils.quote(clean_prompt)
            backup_url = f"https://text.pollinations.ai/{encoded_prompt}?model={backup_model}&seed=42"
            res = requests.get(backup_url, timeout=12)
            if res.status_code == 200 and res.text: return res.text.strip()
        except: continue
    return "🤖 نعتذر، هناك ضغط شديد حالياً. يرجى إعادة إرسال استفسارك."

# ==========================================
# 7. المهام الخلفية الموفرة للطاقة
# ==========================================
def background_tasks_worker():
    while True:
        try:
            now = datetime.utcnow()
            for r in list(reminders_col.find({"notify_at": {"$lte": now}})):
                try: bot.send_message(r['chat_id'], f"⏰ *تنبيه شخصي حان وقته:*\n\n{r['text']}", parse_mode="Markdown")
                except: pass
                reminders_col.delete_one({"_id": r['_id']})
        except Exception as e: logging.error(f"Background Worker Error: {e}")
        time.sleep(60)

threading.Thread(target=background_tasks_worker, daemon=True).start()

# ==========================================
# 8. إدارة الملفات المتقدمة ومنع التكرار
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
        "menu_path": path_str,
        "name": clean_name[:80],
        "type": message.content_type,
        "caption": message.caption,
        "file_id": f_id,
        "downloads": 0,
        "sort_order": 0,  
        "upload_date": datetime.utcnow(),
        "uploader_id": message.chat.id,
        "uploader_name": message.from_user.first_name
    }

def notify_subscribers(file_name, path_str, uploader_id):
    subscribers = list(users_col.find({"smart_notifications": True}))
    for sub in subscribers:
        if sub['chat_id'] != uploader_id:
            try: bot.send_message(sub['chat_id'], f"🔔 *وصول ملف أكاديمي جديد!*\nتمت إضافة: `{file_name}`\n📁 القسم: {path_str}", parse_mode="Markdown")
            except: pass

def process_media_group(chat_id, media_group_id, path_str):
    time.sleep(3.5)
    if media_group_id not in media_groups: return
    messages_batch = media_groups.pop(media_group_id)
    succ, first_name = 0, ""
    
    for msg in messages_batch:
        doc = build_file_doc(msg, path_str)
        if doc['file_id']:
            if not files_col.find_one({"menu_path": path_str, "file_id": doc['file_id']}):
                files_col.insert_one(doc)
                succ += 1
                if not first_name: first_name = doc['name']
            
    try:
        bot.send_message(chat_id, f"✅ تم استقبال الدفعة!\n📦 عدد الملفات المحفوظة: {succ}\n📁 في المسار: {path_str}")
    except: pass

def auto_archive_handler_logic(message):
    if not auth_groups_col.find_one({"chat_id": message.chat.id}): return 
    caption = message.caption or ""
    for tag_data in list(hashtags_col.find()):
        if tag_data['tag'] in caption:
            doc = build_file_doc(message, tag_data['path'])
            doc['name'] = doc['name'].replace(tag_data['tag'], "").strip() or "مؤرشف تلقائياً"
            if doc['file_id'] and not files_col.find_one({"menu_path": doc['menu_path'], "file_id": doc['file_id']}):
                files_col.insert_one(doc)
                try: bot.reply_to(message, f"🎯 تمت الأرشفة الفورية والتخزين التلقائي للمستند في مادة:\n🛡️ *{tag_data['path'].split(' > ')[-1]}*", parse_mode="Markdown")
                except: pass
            break

# ==========================================
# 9. التوجيه وأوامر البداية
# ==========================================
@bot.message_handler(commands=['start'])
def start_command(message):
    chat_id = message.chat.id
    user_data = users_col.find_one({"chat_id": chat_id})
    if user_data and user_data.get("blocked"):
        bot.send_message(chat_id, "🚫 عذراً، تم حظرك وتقييد وصولك للأرشيف.")
        return

    settings = settings_col.find_one({}) or {}
    if settings.get("status") == "inactive" and not is_any_admin(chat_id):
        bot.send_message(chat_id, "🚧 البوت حالياً في وضع الصيانة والتحديث.")
        return

    first_name = message.from_user.first_name or "أيها الطالب الطموح"
    users_col.update_one({"chat_id": chat_id}, {"$set": {"first_name": first_name, "username": f"@{message.from_user.username}", "last_interaction": datetime.utcnow()}, "$setOnInsert": {"smart_notifications": True, "favorites": []}}, upsert=True)
    
    command_args = message.text.split()
    if len(command_args) > 1:
        param = command_args[1]
        if param.startswith("folder_"):
            try:
                f_obj = files_col.find_one({"_id": ObjectId(param.replace("folder_", ""))})
                if f_obj and f_obj.get('menu_path'):
                    user_path[chat_id] = f_obj['menu_path'].split(' > ')
                    bot.send_message(chat_id, f"📂 تم توجيهك للمسار:\n`{f_obj['menu_path']}`", parse_mode="Markdown")
                    show_menu(chat_id); return
            except: pass
        else:
            try:
                f_obj = files_col.find_one({"_id": ObjectId(param)})
                if f_obj:
                    files_col.update_one({"_id": f_obj["_id"]}, {"$inc": {"downloads": 1}})
                    bot.send_message(chat_id, "📥 جاري سحب الملف المطلوب...")
                    send_file_to_user(chat_id, f_obj, has_permission(chat_id, f_obj['menu_path']))
                    return
            except: pass

    user_path[chat_id] = []
    reset_modes(chat_id)
    testing_mode[chat_id] = False
    
    start_txt = settings.get("start_text", DEFAULT_START_TEXT)
    welcome_msg = start_txt.format(first_name=first_name)
    bot.send_message(chat_id, welcome_msg)
    show_menu(chat_id)

@bot.message_handler(commands=['info'])
def info_command_handler(message):
    chat_id = message.chat.id
    settings = settings_col.find_one({}) or {}
    info_msg = settings.get("info_text", DEFAULT_INFO_TEXT)
    bot.send_message(chat_id, info_msg)

# ==========================================
# 10. ديناميكية القوائم (Dynamic Menus)
# ==========================================
def show_menu(chat_id):
    path, path_str = user_path.get(chat_id, []), get_path_string(chat_id)
    current_menu = get_menu_by_path(path)
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mode = admin_action_mode.get(chat_id)
    
    if mode == "move_file_dest":
        markup.add(KeyboardButton("📦 أنقل الملف إلى هذا القسم"), KeyboardButton("🛑 إلغاء الأمر"))
        bot.send_message(chat_id, f"📦 تصفح الأقسام للوصول لموقع النقل الجديد واضغط التأكيد.\n📌 المسار الحالي: {path_str or 'الرئيسية'}", reply_markup=markup)
        return

    if mode == "navigate_to_assign": markup.add(KeyboardButton("✅ تعيين مشرف لهذا القسم"), KeyboardButton("🛑 إلغاء الأمر"))

    # [1] الصفحة الرئيسية
    if not path:
        for key in ACADEMIC_STRUCTURE.keys(): markup.add(KeyboardButton(key))
        markup.add(KeyboardButton("⭐ ملفاتي المفضلة"), KeyboardButton("📞 التواصل مع المشرف العام"))
        
        if is_super_admin(chat_id) and not testing_mode.get(chat_id):
            markup.add(KeyboardButton("👑 لوحة المشرف الرئيسي"), KeyboardButton("👤 عرض كمستخدم"))
        elif is_global_admin(chat_id) and not testing_mode.get(chat_id):
            markup.add(KeyboardButton("🛡️ لوحة المشرف العام"), KeyboardButton("👤 عرض كمستخدم"))
        elif is_any_admin(chat_id) and testing_mode.get(chat_id):
            markup.add("🛑 إنهاء العرض كمستخدم")
            
        bot.send_message(chat_id, "⚙️ القائمة الرئيسية:", reply_markup=markup)
        return

    # [2] اللوحات الخاصة
    if path_str == "SUPER_ADMIN_PANEL":
        markup.add("👥 إدارة المشرفين", "🔑 صلاحيات المشرفين")
        markup.add("📈 إحصائيات النظام", "📊 حالة النظام")
        markup.add("🚨 وضع الطوارئ", "📝 سجل العمليات")
        markup.add("💾 النسخ الاحتياطي اليدوي", "✏️ تعديل نصوص البوت")
        markup.add("📢 إدارة الإعلانات", "🏷️ إدارة الأرشفة")
        markup.add("⭐️ التقييمات", "📊 إحصائيات المقررات")
        markup.add("🔙 الرجوع للقائمة الرئيسية")
        bot.send_message(chat_id, "👑 *لوحة المشرف الرئيسي (Super Admin):*", reply_markup=markup, parse_mode="Markdown")
        return

    if path_str == "GLOBAL_ADMIN_PANEL":
        perms = get_admin_permissions(chat_id)
        if "stats" in perms: markup.add("📈 إحصائيات النظام", "📊 حالة النظام")
        if "broadcast" in perms: markup.add("📢 إدارة الإعلانات")
        if "archives" in perms: markup.add("🏷️ إدارة الأرشفة")
        if "courses_stats" in perms: markup.add("📊 إحصائيات المقررات")
        markup.add("🔙 الرجوع للقائمة الرئيسية")
        bot.send_message(chat_id, "🛡️ *لوحة المشرف العام:*\nصلاحياتك الحالية تظهر أدناه:", reply_markup=markup, parse_mode="Markdown")
        return

    if path_str == "🌟 ميزات مساعدة للطالب":
        user_data = users_col.find_one({"chat_id": chat_id})
        notif_btn = "🔕 إلغاء الإشعارات" if user_data and user_data.get("smart_notifications") else "🔔 تفعيل الإشعارات"
        
        markup.add(KeyboardButton("🤖 المساعد الذكي (AI)"), KeyboardButton("🔍 بحث عن ملف"))
        markup.add(KeyboardButton("🔥 الملفات الأكثر شعبية"), KeyboardButton("🆕 تحديثات اليوم"))
        markup.add(KeyboardButton("📢 إعلانات الدفعة"), KeyboardButton("⏰ تذكير شخصي (خاص بي)"))
        markup.add(KeyboardButton("🔔 تنبيهات المقررات"), KeyboardButton(notif_btn))
        markup.add("🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية")
        bot.send_message(chat_id, "🌟 *ميزات الطالب:*", reply_markup=markup, parse_mode="Markdown")
        return

    if path_str == "FAVORITES":
        u_data = users_col.find_one({"chat_id": chat_id})
        favs = u_data.get("favorites", []) if u_data else []
        markup.add("🔙 الرجوع للقائمة الرئيسية")
        bot.send_message(chat_id, "⭐ *ملفاتك المفضلة:*", reply_markup=markup, parse_mode="Markdown")
        for fav_id in favs:
            try:
                f_doc = files_col.find_one({"_id": ObjectId(fav_id)})
                if f_doc: send_file_to_user(chat_id, f_doc, False)
            except: pass
        if not favs: bot.send_message(chat_id, "لا توجد ملفات في المفضلة.")
        return

    # [3] الأقسام الدراسية الحقيقية
    if isinstance(current_menu, dict):
        for key in current_menu.keys(): markup.add(KeyboardButton(key))
            
    for db_folder in folders_col.find({"parent_path": path_str}).sort([("sort_order", -1), ("folder_name", 1)]):
        markup.add(KeyboardButton(f"📁 {db_folder['folder_name']}"))
    
    for db_file in files_col.find({"menu_path": path_str}).sort([("sort_order", -1), ("name", 1)]).limit(50):
        icon = "📌" if db_file.get("type") == "text" else "🖼️" if db_file.get("type") == "photo" else "📄"
        markup.add(KeyboardButton(f"{icon} {db_file['name']}"))

    markup.add("🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية")
    
    if has_permission(chat_id, path_str):
        markup.add("➕ إضافة ملف/نص", "📂 إضافة مجلد")
        markup.add("✏️ إعادة تسمية هذا القسم", "🗑️ حذف هذا القسم")
        markup.add("🔼 رفع ترتيب القسم", "🔽 خفض ترتيب القسم")
        if is_super_admin(chat_id): markup.add("🔗 ربط هاشتاج بالقسم")

    bot.send_message(chat_id, f"📂 المسار الحالي:\n`{path_str}`", reply_markup=markup, parse_mode="Markdown")

def send_file_to_user(chat_id, res, has_perm):
    try:
        markup = InlineKeyboardMarkup(row_width=2)
        file_id_str = str(res['_id'])
        share_url = f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}?start={file_id_str}"
        deep_folder_url = f"https://t.me/{BOT_USERNAME}?start=folder_{file_id_str}"
        
        if has_perm and not testing_mode.get(chat_id):
            markup.add(InlineKeyboardButton("✏️ تعديل", callback_data=f"rn_{file_id_str}"), InlineKeyboardButton("🔄 استبدال", callback_data=f"rp_{file_id_str}"))
            markup.add(InlineKeyboardButton("🗑️ حذف", callback_data=f"dl_{file_id_str}"), InlineKeyboardButton("📦 نقل", callback_data=f"mv_{file_id_str}"))
            markup.add(InlineKeyboardButton("🔼 رفع", callback_data=f"up_{file_id_str}"), InlineKeyboardButton("🔽 خفض", callback_data=f"dn_{file_id_str}"))
            markup.add(InlineKeyboardButton("📌 تثبيت بالأعلى", callback_data=f"pn_{file_id_str}"))
            
        markup.add(InlineKeyboardButton("🔗 مشاركة الملف", url=share_url), InlineKeyboardButton("📂 عرض مجلد المقرر", url=deep_folder_url))
        markup.add(InlineKeyboardButton("💡 مقترحات", callback_data=f"rl_{file_id_str}"), InlineKeyboardButton("⭐ تقييم", callback_data=f"rt_{file_id_str}"))
        markup.add(InlineKeyboardButton("❤️ أضف للمفضلة", callback_data=f"fv_{file_id_str}"))

        file_type, file_id, file_name, caption = res.get('type', 'document'), res.get('file_id'), res.get('name', 'وثيقة أكاديمية'), res.get('caption')
        if not caption or caption.strip() == "": caption = file_name
        
        up_date = res.get('upload_date', datetime.utcnow()).strftime('%Y-%m-%d')
        up_name = res.get('uploader_name', 'المنصة')
        
        ratings = list(ratings_col.find({"file_id": file_id_str}))
        avg_rt = sum(r['score'] for r in ratings)/len(ratings) if ratings else 0.0
        
        caption += f"\n\n📅 التاريخ: {up_date} | 👤: {up_name}\n🔻 استدعاء: {res.get('downloads', 0)} | ⭐️ التقييم: {avg_rt:.1f}/10"

        if file_type == 'text': bot.send_message(chat_id, res.get('content', file_name), reply_markup=markup)
        elif file_type == 'photo' and file_id: bot.send_photo(chat_id, file_id, caption=caption, reply_markup=markup)
        elif file_id: bot.send_document(chat_id, file_id, caption=caption, reply_markup=markup)
        else: bot.send_message(chat_id, "❌ تنبيه: هذا الملف غير متواجد بخوادم تيليجرام.", reply_markup=markup)
    except Exception as e: logging.error(f"Send File Error: {e}")

# ==========================================
# 11. المعالج المركزي الشامل
# ==========================================
@bot.message_handler(content_types=['text', 'document', 'photo', 'video', 'audio'])
def universal_handler(message):
    chat_id = message.chat.id
    if not check_rate_limit(chat_id): return

    user_data = users_col.find_one({"chat_id": chat_id})
    if user_data and user_data.get("blocked"): return

    settings = settings_col.find_one({}) or {}
    text = message.text if message.content_type == 'text' else ""
    path_str = get_path_string(chat_id)
    mode = admin_action_mode.get(chat_id)

    if message.chat.type in ['group', 'supergroup']:
        auto_archive_handler_logic(message)
        if message.content_type != 'text' or not text.startswith("/"): return

    nav_buttons = ["🔝 القائمة الرئيسية", "🔙 الرجوع للقائمة السابقة", "🔙 الرجوع للقائمة الرئيسية"] + list(ACADEMIC_STRUCTURE.keys())
    if text == "🛑 إلغاء الأمر":
        reset_modes(chat_id); bot.send_message(chat_id, "✅ تم إلغاء الإجراء بنجاح."); show_menu(chat_id); return

    if text in nav_buttons:
        if mode not in ["navigate_to_assign", "move_file_dest"]: reset_modes(chat_id)
        if text in ["🔝 القائمة الرئيسية", "🔙 الرجوع للقائمة الرئيسية"]: user_path[chat_id] = []
        elif text == "🔙 الرجوع للقائمة السابقة" and user_path.get(chat_id): user_path[chat_id].pop()
        elif text in ACADEMIC_STRUCTURE.keys(): user_path[chat_id] = [text]
        show_menu(chat_id); return

    if message.content_type in ['document', 'photo', 'video', 'audio'] and upload_mode.get(chat_id) and has_permission(chat_id, path_str):
        if getattr(message, "media_group_id", None):
            gid = str(message.media_group_id)
            if gid not in media_groups:
                media_groups[gid] = []
                threading.Thread(target=process_media_group, args=(chat_id, gid, path_str)).start()
            media_groups[gid].append(message)
        else:
            doc = build_file_doc(message, path_str)
            if not files_col.find_one({"menu_path": path_str, "file_id": doc['file_id']}):
                files_col.insert_one(doc)
                log_action(chat_id, "ADD_FILE", f"{doc['name']} in {path_str}")
                bot.reply_to(message, f"✅ تم حفظ المستند الفردي: *{doc['name']}*\n(مستمرون بوضع الرفع...)", parse_mode="Markdown")
                notify_subscribers(doc['name'], path_str, chat_id)
            else:
                bot.reply_to(message, "⚠️ هذا الملف موجود بالفعل.")
        return 

    if text == "👑 لوحة المشرف الرئيسي" and is_super_admin(chat_id):
        user_path[chat_id] = ["SUPER_ADMIN_PANEL"]; show_menu(chat_id); return
    if text == "🛡️ لوحة المشرف العام" and is_global_admin(chat_id):
        user_path[chat_id] = ["GLOBAL_ADMIN_PANEL"]; show_menu(chat_id); return
    if text == "🌟 ميزات مساعدة للطالب":
        user_path[chat_id] = ["🌟 ميزات مساعدة للطالب"]; show_menu(chat_id); return
    if text == "⭐ ملفاتي المفضلة":
        user_path[chat_id] = ["FAVORITES"]; show_menu(chat_id); return

    if text == "اللجنة العلمية" and path_str == "🌱 مستوى أول":
        sci_text = (
            "🎓 *اللجنة العلمية للدفعة الثانية - AI & DS*\n\n"
            "تتقدم إدارة الدفعة بخالص الشكر والتقدير لجهود اللجنة العلمية في ترتيب وتوفير المصادر الدراسية للطلاب.\n\n"
            "👤 *إدارة الدفعة:*\n"
            "• مندوب الدفعة: الواثق بالله عساج\n"
            "• مندوبة الدفعة: شهد المشهور\n"
            "• نائب الدفعة: ليث آل مرزوق\n"
            "• نائبة الدفعة: آية أمين\n\n"
            "🧠 *رئيس اللجنة العلمية:* عبد القوي أحمد\n\n"
            "📚 *أعضاء اللجنة حسب المقررات:*\n"
            "🔸 *التكامل:* أبرار عدنان، مجد محمود، البراء خسن\n"
            "🔸 *الإسلامية:* أحلام طلال\n"
            "🔸 *البرمجة:* جلال عبد الناصر، نهى رفيق، مرام نبيل\n"
            "🔸 *الإنجليزي:* عمرو خالد، مرام رأفت\n"
            "🔸 *مقدمة علوم البيانات:* مودة أسامة، محمد جميل\n"
            "🔸 *رياضيات متقطعة:* عمر عبد الحبيب، حنان عبده\n\n"
            "✨ *ختاماً:* شكراً لكل من ساهم بوقتِه وجهده لتسهيل طريق العلم للجميع. دمتم فخراً وسنداً لدفعتكم."
        )
        bot.send_message(chat_id, sci_text, parse_mode="Markdown"); return

    if text == "📞 التواصل مع المشرف العام":
        dev_msg = settings.get("dev_text", DEFAULT_DEV_TEXT)
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("❓ استفسار", url="https://t.me/AlwatheqAssag"),
            InlineKeyboardButton("📝 ملاحظات", url="https://t.me/AlwatheqAssag"),
            InlineKeyboardButton("⚠️ بلاغ عن مقرر", url="https://t.me/AlwatheqAssag"),
            InlineKeyboardButton("📤 إرسال ملف أو ملخص", url="https://t.me/AlwatheqAssag"),
            InlineKeyboardButton("💬 فتح المحادثة المباشرة", url="https://t.me/AlwatheqAssag")
        )
        bot.send_message(chat_id, dev_msg, reply_markup=markup, parse_mode="Markdown"); return

    if text == "📢 إعلانات الدفعة":
        ann = settings.get("last_announcement", "لا توجد إعلانات حالياً.")
        bot.send_message(chat_id, f"📢 *آخر إعلان للدفعة:*\n\n{ann}", parse_mode="Markdown"); return

    if text == "🤖 المساعد الذكي (AI)":
        if settings.get("emergency_flags", {}).get("ai", False) and not is_any_admin(chat_id):
            bot.send_message(chat_id, "🚧 الذكاء الاصطناعي معطل للصيانة."); return
        reset_modes(chat_id); admin_action_mode[chat_id] = "ai_chat"
        if chat_id not in ai_memory: ai_memory[chat_id] = []
        bot.send_message(chat_id, "🤖 المساعد الذكي جاهز. اسأل وسأجيبك:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return
    
    if mode == "ai_chat" and text:
        ans = get_ai_response(text, chat_id)
        ai_memory[chat_id].append(text)
        if len(ai_memory[chat_id]) > 3: ai_memory[chat_id].pop(0)
        bot.send_message(chat_id, ans, parse_mode="Markdown"); reset_modes(chat_id); show_menu(chat_id); return

    if text == "🔍 بحث عن ملف":
        if settings.get("emergency_flags", {}).get("search", False) and not is_any_admin(chat_id):
            bot.send_message(chat_id, "🚧 البحث معطل حالياً للصيانة."); return
        reset_modes(chat_id); admin_action_mode[chat_id] = "search_type"
        bot.send_message(chat_id, "🔍 اختر النطاق:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🌍 بحث شامل", "📂 بحث في مساري الحالي").add("🛑 إلغاء الأمر")); return
    
    if mode == "search_type" and text in ["🌍 بحث شامل", "📂 بحث في مساري الحالي"]:
        action_payload[chat_id] = "global" if text == "🌍 بحث شامل" else path_str
        admin_action_mode[chat_id] = "search_exec"
        bot.send_message(chat_id, "🔍 أرسل كلمة البحث:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return
        
    if mode == "search_exec" and text:
        scope = action_payload.get(chat_id, "global")
        query = {"$text": {"$search": text}}
        if scope != "global" and scope: query["menu_path"] = {"$regex": f"^{re.escape(scope)}"}
        results = list(files_col.find(query, {"score": {"$meta": "textScore"}}).sort([("score", {"$meta": "textScore"})]).limit(10))
        if not results:
            q_reg = {"$or": [{"name": {"$regex": text, "$options": "i"}}, {"caption": {"$regex": text, "$options": "i"}}, {"menu_path": {"$regex": text, "$options": "i"}}]}
            if scope != "global" and scope: q_reg = {"$and": [{"menu_path": {"$regex": f"^{re.escape(scope)}"}}, q_reg]}
            results = list(files_col.find(q_reg).limit(15))
        if results:
            bot.send_message(chat_id, f"🔍 وجدنا {len(results)} نتائج مطابقة:")
            for item in results: send_file_to_user(chat_id, item, has_permission(chat_id, item['menu_path']))
        else: bot.send_message(chat_id, "❌ لم نجد ملفات أو مقررات مطابقة للكلمة المدخلة.")
        reset_modes(chat_id); show_menu(chat_id); return

    if text in ["🔔 تفعيل الإشعارات", "🔕 إلغاء الإشعارات"]:
        users_col.update_one({"chat_id": chat_id}, {"$set": {"smart_notifications": (text == "🔔 تفعيل الإشعارات")}})
        bot.send_message(chat_id, "✅ تم التحديث بنجاح."); show_menu(chat_id); return

    if text == "⏰ تذكير شخصي (خاص بي)":
        reset_modes(chat_id); admin_action_mode[chat_id] = "set_rem_text"
        bot.send_message(chat_id, "⏰ ما هو موضوع التذكير؟", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return
    if mode == "set_rem_text" and text:
        action_payload[chat_id] = text; admin_action_mode[chat_id] = "set_rem_time"
        bot.send_message(chat_id, "بعد كم ساعة أذكرك؟ (أرقام فقط كـ 2 أو 1.5):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return
    if mode == "set_rem_time" and text:
        try:
            reminders_col.insert_one({"chat_id": chat_id, "text": action_payload[chat_id], "notify_at": datetime.utcnow() + timedelta(hours=float(text.strip()))})
            bot.send_message(chat_id, "✅ تم جدولة التنبيه بنجاح.")
        except: bot.send_message(chat_id, "❌ أرقام فقط يرجى.")
        reset_modes(chat_id); show_menu(chat_id); return

    # [ميزات الإدارة الفائقة والمسار المخصص]
    if is_super_admin(chat_id) and path_str == "SUPER_ADMIN_PANEL":
        if text == "📝 سجل العمليات":
            logs = list(action_logs_col.find().sort("timestamp", -1).limit(20))
            msg = "📝 *سجل العمليات الأخير:*\n"
            for lg in logs: msg += f"• {lg['timestamp'].strftime('%m-%d %H:%M')} | {lg['action']} | {lg['details'][:20]}\n"
            bot.send_message(chat_id, msg if logs else "السجل فارغ.", parse_mode="Markdown"); return

        if text == "🚨 وضع الطوارئ":
            flags = settings.get("emergency_flags", {})
            m = ReplyKeyboardMarkup(resize_keyboard=True)
            m.add(f"{'🟢' if not flags.get('ai') else '🔴'} AI", f"{'🟢' if not flags.get('upload') else '🔴'} الرفع")
            m.add(f"{'🟢' if not flags.get('search') else '🔴'} البحث", "🛑 إيقاف البوت كلياً")
            m.add("🔙 الرجوع للقائمة السابقة")
            bot.send_message(chat_id, "🚨 *تحكم الطوارئ (الأحمر = معطل):*", reply_markup=m, parse_mode="Markdown"); return

        if text in ["🟢 AI", "🔴 AI", "🟢 الرفع", "🔴 الرفع", "🟢 البحث", "🔴 البحث"]:
            key = "ai" if "AI" in text else ("upload" if "الرفع" in text else "search")
            cur = settings.get("emergency_flags", {}).get(key, False)
            settings_col.update_one({}, {"$set": {f"emergency_flags.{key}": not cur}})
            bot.send_message(chat_id, f"✅ تم تبديل حالة {key}."); show_menu(chat_id); return

        if text == "✏️ تعديل نصوص البوت":
            reset_modes(chat_id)
            markup = ReplyKeyboardMarkup(resize_keyboard=True).add("✏️ تعديل Start", "✏️ تعديل Info", "✏️ تعديل المطور").add("🛑 إلغاء الأمر")
            bot.send_message(chat_id, "اختر الرسالة:", reply_markup=markup); return

        if text in ["✏️ تعديل Start", "✏️ تعديل Info", "✏️ تعديل المطور"]:
            admin_action_mode[chat_id] = "edit_txt_" + text.split()[2]
            bot.send_message(chat_id, "أرسل النص الجديد:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

        if mode and mode.startswith("edit_txt_") and text:
            k = "start_text" if "Start" in mode else ("info_text" if "Info" in mode else "dev_text")
            settings_col.update_one({}, {"$set": {k: text}}, upsert=True)
            bot.send_message(chat_id, "✅ تم الحفظ."); reset_modes(chat_id); show_menu(chat_id); return

        if text == "👥 إدارة المشرفين":
            adm_docs = list(admins_col.find({"id": {"$ne": SUPER_ADMIN_ID}}))
            txt = "🛠️ *المشرفين:*\n"
            for adm in adm_docs:
                u_info = users_col.find_one({"chat_id": adm["id"]})
                n = u_info.get("first_name", "-") if u_info else "-"
                txt += f"👤 {n} | `{adm['id']}` | {adm.get('type')}\n"
            m = ReplyKeyboardMarkup(resize_keyboard=True).add("➕ إضافة مشرف عام", "➕ إضافة مشرف مسار مخصص", "➖ إزالة مشرف", "🔙 الرجوع للقائمة السابقة")
            bot.send_message(chat_id, txt, reply_markup=m, parse_mode="Markdown"); return

        if text in ["➕ إضافة مشرف عام", "➖ إزالة مشرف"]:
            reset_modes(chat_id); admin_action_mode[chat_id] = "add_glb" if "إضافة" in text else "rm_adm"
            bot.send_message(chat_id, "أرسل الآيدي الرقمي:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

        if mode == "add_glb" and text:
            try:
                tid = int(text.strip())
                admins_col.update_one({"id": tid}, {"$set": {"id": tid, "type": "global", "permissions": ["all"]}}, upsert=True)
                log_action(chat_id, "ADD_ADMIN", f"ID: {tid}")
                bot.send_message(chat_id, "✅ تمت الإضافة."); reset_modes(chat_id); show_menu(chat_id)
            except: bot.send_message(chat_id, "❌ أرقام فقط."); return

        if mode == "rm_adm" and text:
            try:
                tid = int(text.strip())
                if tid != SUPER_ADMIN_ID: admins_col.delete_one({"id": tid})
                log_action(chat_id, "RM_ADMIN", f"ID: {tid}")
                bot.send_message(chat_id, "✅ تمت الإزالة."); reset_modes(chat_id); show_menu(chat_id)
            except: bot.send_message(chat_id, "❌ أرقام فقط."); return

    if text == "➕ إضافة مشرف مسار مخصص" and is_super_admin(chat_id):
        reset_modes(chat_id); admin_action_mode[chat_id] = "navigate_to_assign"; user_path[chat_id] = []
        bot.send_message(chat_id, "📍 تصفح الأقسام للوصول للمقرر، ثم اضغط (✅ تعيين مشرف لهذا القسم)."); show_menu(chat_id); return

    if mode == "navigate_to_assign" and text == "✅ تعيين مشرف لهذا القسم" and is_super_admin(chat_id):
        admin_action_mode[chat_id] = "ask_path_admin_id"
        bot.send_message(chat_id, f"👤 المسار: `{path_str}`\nأرسل الآيدي:", parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

    if mode == "ask_path_admin_id" and text and is_super_admin(chat_id):
        try:
            tid = int(text.strip())
            admins_col.update_one({"id": tid}, {"$set": {"id": tid, "type": "path"}, "$addToSet": {"allowed_paths": path_str}}, upsert=True)
            log_action(chat_id, "ASSIGN_PATH_ADMIN", f"ID: {tid} Path: {path_str}")
            bot.send_message(chat_id, "✅ تم التقييد بنجاح."); reset_modes(chat_id); show_menu(chat_id)
        except ValueError: bot.send_message(chat_id, "❌ أرقام فقط.")
        return

    if text == "👤 تجربة كمستخدم" and is_any_admin(chat_id):
        testing_mode[chat_id] = True; user_path[chat_id] = []; bot.send_message(chat_id, "👀 أنت الآن كطالب."); show_menu(chat_id); return
    if text == "🛑 إنهاء العرض كمستخدم" and testing_mode.get(chat_id):
        testing_mode[chat_id] = False; user_path[chat_id] = []; bot.send_message(chat_id, "💼 عدت للإدارة."); show_menu(chat_id); return

    # [العمليات الإدارية الآمنة وإعادة التسمية التتابعية]
    if has_permission(chat_id, path_str) and path_str and path_str not in ["SUPER_ADMIN_PANEL", "GLOBAL_ADMIN_PANEL", "STUDENT_FEATURES", "FAVORITES"]:
        if text == "➕ إضافة ملف/نص":
            reset_modes(chat_id); upload_mode[chat_id] = True
            bot.send_message(chat_id, "📥 أرسل الملفات الآن:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return
        if text == "📂 إضافة مجلد":
            reset_modes(chat_id); add_folder_mode[chat_id] = True
            bot.send_message(chat_id, "📂 اكتب اسم المجلد الجديد:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return
        if text == "✏️ إعادة تسمية هذا القسم":
            reset_modes(chat_id); admin_action_mode[chat_id] = "rn_fld"
            bot.send_message(chat_id, "✏️ أرسل الاسم الجديد (سيتم تحديث المسار بذكاء):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return
        if text == "🗑️ حذف هذا القسم":
            parent = path_str.rsplit(' > ', 1)[0] if ' > ' in path_str else ""
            folders_col.delete_one({"parent_path": parent, "folder_name": user_path[chat_id][-1]})
            user_path[chat_id].pop(); bot.send_message(chat_id, "🗑️ تم الحذف."); show_menu(chat_id); return
        if text in ["🔼 رفع ترتيب القسم", "🔽 خفض ترتيب القسم"]:
            parent = path_str.rsplit(' > ', 1)[0] if ' > ' in path_str else ""
            fld = folders_col.find_one({"parent_path": parent, "folder_name": user_path[chat_id][-1]})
            if fld:
                inc = 1 if "رفع" in text else -1
                folders_col.update_one({"_id": fld["_id"]}, {"$inc": {"sort_order": inc}})
                bot.send_message(chat_id, "✅ تم تغيير الترتيب.")
            show_menu(chat_id); return

    if mode == "rn_fld" and text:
        old_folder_name = user_path[chat_id][-1]
        parent_p_str = path_str.rsplit(' > ', 1)[0] if ' > ' in path_str else ""
        new_folder_name = text.strip()
        
        folders_col.update_one({"parent_path": parent_p_str, "folder_name": old_folder_name}, {"$set": {"folder_name": new_folder_name}})
        old_full = f"{parent_p_str} > {old_folder_name}" if parent_p_str else old_folder_name
        new_full = f"{parent_p_str} > {new_folder_name}" if parent_p_str else new_folder_name
        
        for f in files_col.find({"menu_path": {"$regex": f"^{re.escape(old_full)}" }}):
            new_f_path = f['menu_path'].replace(old_full, new_full, 1)
            files_col.update_one({"_id": f["_id"]}, {"$set": {"menu_path": new_f_path}})
            
        for d in folders_col.find({"parent_path": {"$regex": f"^{re.escape(old_full)}" }}):
            new_d_path = d['parent_path'].replace(old_full, new_full, 1)
            folders_col.update_one({"_id": d["_id"]}, {"$set": {"parent_path": new_d_path}})
            
        user_path[chat_id][-1] = new_folder_name
        log_action(chat_id, "RENAME_FOLDER", f"{old_folder_name} to {new_folder_name}")
        bot.send_message(chat_id, "✅ تم التعديل وتحديث الروابط بأمان."); reset_modes(chat_id); show_menu(chat_id); return

    if mode == "rename_file" and text:
        files_col.update_one({"_id": ObjectId(action_payload.get(chat_id))}, {"$set": {"name": text.strip()}})
        log_action(chat_id, "RENAME_FILE", text[:20])
        bot.send_message(chat_id, "✅ تم التعديل."); reset_modes(chat_id); show_menu(chat_id); return

    if mode == "replace_file":
        doc = build_file_doc(message, path_str)
        update_data = {"type": doc['type'], "file_id": doc['file_id'], "name": doc['name'], "caption": doc['caption']} if doc['file_id'] else {"type": "text", "content": text, "name": text[:30], "file_id": None}
        files_col.update_one({"_id": ObjectId(action_payload.get(chat_id))}, {"$set": update_data})
        bot.send_message(chat_id, "✅ تم الاستبدال."); reset_modes(chat_id); show_menu(chat_id); return

    if add_folder_mode.get(chat_id) and text and has_permission(chat_id, path_str):
        folders_col.insert_one({"parent_path": path_str, "folder_name": text.strip(), "created_at": datetime.utcnow(), "sort_order": 0})
        bot.send_message(chat_id, f"✅ تم إنشاء: {text.strip()}"); reset_modes(chat_id); show_menu(chat_id); return

    if upload_mode.get(chat_id) and message.content_type == 'text' and has_permission(chat_id, path_str):
        files_col.insert_one({"menu_path": path_str, "name": text[:60].strip(), "type": "text", "content": text, "downloads": 0, "upload_date": datetime.utcnow(), "sort_order": 0})
        bot.send_message(chat_id, "✅ تم حفظ التلخيص."); return

    if text and (text.startswith("📄 ") or text.startswith("📌 ") or text.startswith("🖼️ ")):
        ex_name = text.replace("📄 ", "").replace("📌 ", "").replace("🖼️ ", "").strip()
        f_doc = files_col.find_one({"menu_path": path_str, "name": ex_name}) or files_col.find_one({"menu_path": path_str, "name": {"$regex": f"^{re.escape(ex_name)}$", "$options": "i"}})
        if f_doc:
            files_col.update_one({"_id": f_doc["_id"]}, {"$inc": {"downloads": 1}})
            send_file_to_user(chat_id, f_doc, has_permission(chat_id, path_str))
        return

    if text.startswith("📁 "):
        user_path[chat_id].append(text.replace("📁 ", "").strip()); show_menu(chat_id); return

    if isinstance(get_menu_by_path(user_path.get(chat_id, [])), dict) and text in get_menu_by_path(user_path.get(chat_id, [])):
        if chat_id not in user_path: user_path[chat_id] = []
        user_path[chat_id].append(text); show_menu(chat_id); return

# ==========================================
# 13. أزرار التحكم الجانبية (Inline Callbacks)
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith(('rn_', 'rp_', 'dl_', 'mv_', 'rl_', 'up_', 'dn_', 'pn_', 'fv_', 'rt_', 'str_')))
def handle_inline_callbacks(call):
    chat_id = call.message.chat.id
    try: action, obj_id = call.data.split('_', 1)
    except: return

    if action == 'fv':
        users_col.update_one({"chat_id": chat_id}, {"$addToSet": {"favorites": obj_id}})
        bot.answer_callback_query(call.id, "❤️ تمت إضافته لمفضلتك بنجاح!", show_alert=True); return
    
    if action == 'rt':
        m = InlineKeyboardMarkup(row_width=5)
        btns = [InlineKeyboardButton(str(i), callback_data=f"str_{i}_{obj_id}") for i in range(1, 11)]
        m.add(*btns)
        try: bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=m)
        except: pass
        return
        
    if action == 'str':
        score, f_id = obj_id.split('_')
        ratings_col.update_one({"file_id": f_id, "user_id": chat_id}, {"$set": {"score": int(score)}}, upsert=True)
        bot.answer_callback_query(call.id, f"⭐️ شكراً لك! تم حفظ تقييمك: {score}/10", show_alert=True)
        f_doc = files_col.find_one({"_id": ObjectId(f_id)})
        if f_doc: send_file_to_user(chat_id, f_doc, has_permission(chat_id, f_doc['menu_path']))
        try: bot.delete_message(chat_id, call.message.message_id)
        except: pass
        return

    if action == 'rl':
        f_doc = files_col.find_one({"_id": ObjectId(obj_id)})
        if f_doc:
            rel = list(files_col.find({"menu_path": f_doc['menu_path'], "_id": {"$ne": ObjectId(obj_id)}}).limit(2))
            if rel:
                bot.send_message(chat_id, "💡 *ملفات إضافية من نفس القسم:*", parse_mode="Markdown")
                for r in rel: send_file_to_user(chat_id, r, False)
            else: bot.answer_callback_query(call.id, "لا يوجد غيره حالياً.", show_alert=True)
        return

    f_doc = files_col.find_one({"_id": ObjectId(obj_id)})
    if not f_doc or not has_permission(chat_id, f_doc['menu_path']):
        bot.answer_callback_query(call.id, "❌ لا تمتلك الصلاحية.", show_alert=True); return

    if action == 'dl':
        files_col.delete_one({"_id": ObjectId(obj_id)})
        log_action(chat_id, "DELETE_FILE", f_doc['name'])
        try: bot.delete_message(chat_id, call.message.message_id)
        except: pass
        show_menu(chat_id)
    elif action == 'rn':
        reset_modes(chat_id); admin_action_mode[chat_id] = "rename_file"; action_payload[chat_id] = obj_id
        bot.send_message(chat_id, "✏️ أرسل الاسم الجديد:")
    elif action == 'rp':
        reset_modes(chat_id); admin_action_mode[chat_id] = "replace_file"; action_payload[chat_id] = obj_id
        bot.send_message(chat_id, "🔄 أرسل الملف البديل الآن:")
    elif action == 'mv':
        reset_modes(chat_id); admin_action_mode[chat_id] = "move_file_dest"; action_payload[chat_id] = obj_id
        user_path[chat_id] = []; show_menu(chat_id)
    elif action in ['up', 'dn', 'pn']:
        inc = 1 if action == 'up' else -1
        if action == 'pn': files_col.update_one({"_id": ObjectId(obj_id)}, {"$set": {"sort_order": 999}})
        else: files_col.update_one({"_id": ObjectId(obj_id)}, {"$inc": {"sort_order": inc}})
        bot.answer_callback_query(call.id, "✅ تم التحديث.", show_alert=False); show_menu(chat_id)

@app.route('/webhook', methods=['POST'])
def webhook_listen_route():
    if request.headers.get('content-type') == 'application/json':
        bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
        return "!", 200
    return "Invalid", 403

@app.route("/")
def index_home_route(): return "Bot V4 LMS is RUNNING 🚀", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
