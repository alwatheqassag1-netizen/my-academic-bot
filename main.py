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
system_stats = {"ai_queries_today": 0, "cache_hits_today": 0, "requests_24h": 0}

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
    "• الملاحظات الدراسية.\n"
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
    
    files_col.create_index([("name", "text"), ("caption", "text")])
    logging.info("Database Connected Flawlessly! 🎉")
except Exception as db_err:
    logging.error(f"MongoDB Connection Error: {db_err}")

if admins_col.count_documents({"id": SUPER_ADMIN_ID}) == 0:
    admins_col.insert_one({"id": SUPER_ADMIN_ID, "type": "super", "allowed_paths": []})
if settings_col.count_documents({}) == 0:
    settings_col.insert_one({"status": "active"})

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
        "📅 ترم ثاني": {
            "🕋 الثقافة الإسلامية": {"📁 محاضرات وملخصات": {}, "📝 نماذج اختبارات": {}},
            "📚 لغة عربية 2": {"📁 محاضرات وملخصات": {}, "📝 نماذج اختبارات": {}},
            "🇬🇧 لغة إنجليزية 2": {"📁 محاضرات وملخصات": {}, "📝 نماذج اختبارات": {}},
            "📈 تفاضل وتكامل 2": {"📂 محاضرات نظري": {}, "📐 محاضرات تمارين": {}, "📝 نماذج اختبارات نظري": {}, "✍️ نماذج تمارين": {}, "📚 مراجع خارجية": {}},
            "📊 مقدمة في علوم البيانات": {"👨‍🏫 محاضرات المهندس": {}, "📜 ملخص محاضرات": {}, "⚙️ محاضرات العملي": {}, "📝 نماذج اختبارات نظري": {}},
            "💻 برمجة حاسوب": {"📂 محاضرات نظري": {}, "🖥️ محاضرات العملي": {}, "📝 نماذج اختبارات": {}, "🚀 التمارين والمشاريع العملية": {}},
            "🗂️ رياضيات متقطعة": {"📂 محاضرات نظري": {}, "✏️ محاضرات تمارين": {}, "📝 نماذج اختبارات": {}, "📚 مراجع خارجية": {}}
        }
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
def is_global_admin(chat_id): return admins_col.find_one({"id": chat_id, "type": "global"}) is not None
def is_any_admin(chat_id): return chat_id == SUPER_ADMIN_ID or admins_col.find_one({"id": chat_id}) is not None

def has_permission(chat_id, current_path_str):
    if testing_mode.get(chat_id): return False
    if is_super_admin(chat_id): return True
    admin = admins_col.find_one({"id": chat_id})
    if not admin: return False
    if admin.get("type") == "global": return True
    for allowed_p in admin.get("allowed_paths", []):
        if current_path_str.startswith(allowed_p) or current_path_str == allowed_p: return True
    return False

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
    context = ""
    if chat_id in ai_memory and ai_memory[chat_id]:
        context = "السياق السابق: " + " | ".join(ai_memory[chat_id][-2:]) + "\nالسؤال الحالي: "
        
    clean_prompt = f"أنت مساعد أكاديمي لجامعة تعز (الذكاء الاصطناعي وعلوم البيانات). أجب باختصار ودقة: {context}{prompt}"
    
    if GEMINI_API_KEY and not GEMINI_API_KEY.startswith("AIzaSy"):
        for model_name in ["gemini-2.0-flash-lite-preview-02-05", "gemini-2.0-flash", "gemini-1.5-flash"]:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
                payload = {"contents": [{"parts": [{"text": clean_prompt}]}], "generationConfig": {"temperature": 0.4, "maxOutputTokens": 600}}
                res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=7)
                if res.status_code == 200:
                    return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
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
            
            thirty_days_ago = now - timedelta(days=30)
            kb_col.delete_many({"last_used": {"$lt": thirty_days_ago}, "hits": {"$lt": 3}})
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
        bot.send_message(chat_id, f"✅ تم استقبال الدفعة!\n📦 إجمالي الملفات المحفوظة: {succ} ملفات جديدة.\n📁 في المسار: {path_str}\n(يمكنك إرسال المزيد أو إرسال 🛑 إلغاء الأمر للإنهاء)")
        if succ > 0: notify_subscribers(f"باقة ملفات (منها: {first_name})", path_str, chat_id)
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
        resume_at = settings.get("resume_at")
        if resume_at and datetime.utcnow() >= resume_at: settings_col.update_one({}, {"$set": {"status": "active", "resume_at": None}})
        else:
            bot.send_message(chat_id, "🚧 البوت حالياً في وضع الصيانة والتحديث. يرجى المحاولة لاحقاً.")
            return

    first_name = message.from_user.first_name or "أيها الطالب الطموح"
    users_col.update_one({"chat_id": chat_id}, {"$set": {"first_name": first_name, "username": f"@{message.from_user.username}", "last_interaction": datetime.utcnow()}, "$setOnInsert": {"smart_notifications": True}}, upsert=True)
    
    command_args = message.text.split()
    if len(command_args) > 1:
        param = command_args[1]
        if param.startswith("folder_"):
            try:
                f_obj = files_col.find_one({"_id": ObjectId(param.replace("folder_", ""))})
                if f_obj and f_obj.get('menu_path'):
                    user_path[chat_id] = f_obj['menu_path'].split(' > ')
                    bot.send_message(chat_id, f"📂 تم توجيهك تلقائياً وتحديد المسار إلى:\n`{f_obj['menu_path']}`\nيمكنك الآن تصفح جميع مرفقات ونماذج هذا المقرر.", parse_mode="Markdown")
                    show_menu(chat_id)
                    return
            except: pass
        else:
            try:
                f_obj = files_col.find_one({"_id": ObjectId(param)})
                if f_obj:
                    files_col.update_one({"_id": f_obj["_id"]}, {"$inc": {"downloads": 1}})
                    bot.send_message(chat_id, "📥 جاري سحب وإحضار الملف الأكاديمي المطلوب من قاعدة البيانات...")
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
    user_data = users_col.find_one({"chat_id": chat_id})
    if user_data and user_data.get("blocked"): return

    settings = settings_col.find_one({}) or {}
    if settings.get("status") == "inactive" and not is_any_admin(chat_id): return

    info_msg = settings.get("info_text", DEFAULT_INFO_TEXT)
    bot.send_message(chat_id, info_msg)

@bot.message_handler(commands=['auth'])
def auth_command(message):
    if message.chat.type in ['group', 'supergroup'] and message.from_user.id == SUPER_ADMIN_ID:
        auth_groups_col.update_one({"chat_id": message.chat.id}, {"$set": {"title": message.chat.title, "authenticated_at": datetime.utcnow()}}, upsert=True)
        bot.reply_to(message, "✅ تم اعتماد وتوثيق هذه المجموعة رسمياً. المنصة تراقب الهاشتاجات النشطة لعمليات الأرشفة التلقائية الآن.")

@bot.message_handler(commands=['unauth'])
def unauth_command(message):
    if message.chat.type in ['group', 'supergroup'] and message.from_user.id == SUPER_ADMIN_ID:
        auth_groups_col.delete_one({"chat_id": message.chat.id})
        bot.reply_to(message, "⛔ تم سحب الاعتماد وتجريد المجموعة من صلاحيات الأرشفة التلقائية.")

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
        bot.send_message(chat_id, f"📦 تصفح الأقسام للوصول لموقع النقل الجديد واضغط على زر التأكيد.\n📌 المسار الحالي: {path_str or 'الرئيسية'}", reply_markup=markup)
        return

    # الحل الشامل لمشكلة ضياع الزر أثناء تصفح إضافة مشرف: إجبار الزر على الظهور في أعلى القائمة
    if mode == "navigate_to_assign":
        markup.add(KeyboardButton("✅ تعيين مشرف لهذا القسم"), KeyboardButton("🛑 إلغاء الأمر"))

    if not path:
        for key in ACADEMIC_STRUCTURE.keys(): markup.add(KeyboardButton(key))
        markup.add("👨‍💻 تواصل مع المشرف العام")
        
        if (is_super_admin(chat_id) or is_global_admin(chat_id)) and not testing_mode.get(chat_id):
            if is_super_admin(chat_id):
                markup.add("📢 إرسال رسالة جماعية", "👥 إحصائيات المشتركين")
                markup.add("🛠️ إدارة المشرفين", "⚙️ التحكم بالنظام")
                markup.add("📊 حالة النظام", "💾 تصدير نسخة احتياطية")
                markup.add("🏷️ إدارة الأرشفة", "📂 إضافة مجلد بالرئيسية")
                markup.add("🚫 حظر مستخدم", "🧹 أرشفة الملفات القديمة")
                markup.add("📝 تعديل نصوص البوت")
            markup.add("👤 تجربة كمستخدم")
        elif (is_super_admin(chat_id) or is_global_admin(chat_id)) and testing_mode.get(chat_id):
            markup.add("🛑 إنهاء التجربة والعودة للإشراف")
            
        bot.send_message(chat_id, "⚙️ يرجى تحديد القسم الأكاديمي المطلوب من لوحة الخيارات التالية:", reply_markup=markup)
        return

    if path_str == "🌟 ميزات مساعدة للطالب":
        user_data = users_col.find_one({"chat_id": chat_id})
        notif_btn = "🔕 إلغاء الإشعارات" if user_data and user_data.get("smart_notifications") else "🔔 تفعيل الإشعارات"
        
        markup.add(KeyboardButton("🤖 المساعد الذكي (AI)"), KeyboardButton("🔍 بحث عن ملف"))
        markup.add(KeyboardButton("🔥 الملفات الأكثر شعبية"), KeyboardButton("🆕 تحديثات اليوم"))
        markup.add(KeyboardButton("🔔 تنبيهات المقررات"), KeyboardButton("⏰ تذكير شخصي (خاص بي)"))
        markup.add(KeyboardButton("📝 مذكراتي الدراسية"), KeyboardButton(notif_btn))
        markup.add("🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية")
        bot.send_message(chat_id, "🌟 *ميزات مساعدة للطالب*\nأدوات متكاملة مصممة خصيصاً لتعزيز تجربتك وتنظيم وقتك:", reply_markup=markup, parse_mode="Markdown")
        return

    if isinstance(current_menu, dict):
        for key in current_menu.keys(): markup.add(KeyboardButton(key))
            
    for db_folder in folders_col.find({"parent_path": path_str}): markup.add(KeyboardButton(f"📁 {db_folder['folder_name']}"))
    
    for db_file in files_col.find({"menu_path": path_str}).sort("upload_date", -1).limit(50):
        icon = "📌" if db_file.get("type") == "text" else "🖼️" if db_file.get("type") == "photo" else "📄"
        markup.add(KeyboardButton(f"{icon} {db_file['name']}"))

    markup.add("🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية")
    
    if has_permission(chat_id, path_str):
        markup.add("➕ إضافة ملف/نص", "📂 إضافة مجلد")
        markup.add("✏️ إعادة تسمية هذا القسم", "🗑️ حذف هذا القسم")
        if is_super_admin(chat_id): markup.add("🔗 ربط هاشتاج بالقسم")

    bot.send_message(chat_id, f"📂 المسار الحالي:\n`{path_str}`", reply_markup=markup, parse_mode="Markdown")

def send_file_to_user(chat_id, res, has_perm):
    try:
        markup = InlineKeyboardMarkup(row_width=2)
        file_id_str = str(res['_id'])
        share_url = f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}?start={file_id_str}"
        deep_folder_url = f"https://t.me/{BOT_USERNAME}?start=folder_{file_id_str}"
        
        if has_perm and not testing_mode.get(chat_id):
            markup.add(InlineKeyboardButton("✏️ تعديل الاسم", callback_data=f"rn_{file_id_str}"), InlineKeyboardButton("🔄 استبدال الملف", callback_data=f"rp_{file_id_str}"))
            markup.add(InlineKeyboardButton("🗑️ حذف", callback_data=f"dl_{file_id_str}"), InlineKeyboardButton("📦 نقل", callback_data=f"mv_{file_id_str}"))
        
        markup.add(InlineKeyboardButton("🔗 مشاركة الملف", url=share_url), InlineKeyboardButton("📂 عرض مجلد المقرر", url=deep_folder_url))
        markup.add(InlineKeyboardButton("💡 ملفات مقترحة من نفس المقرر", callback_data=f"rl_{file_id_str}"))

        file_type, file_id, file_name, caption = res.get('type', 'document'), res.get('file_id'), res.get('name', 'وثيقة أكاديمية'), res.get('caption')
        if not caption or caption.strip() == "": caption = file_name
        
        up_date = res.get('upload_date', datetime.utcnow()).strftime('%Y-%m-%d')
        up_name = res.get('uploader_name', 'المنصة')
        caption += f"\n\n📅 أُضيف: {up_date} | 👤 بواسطة: {up_name}\n🔻 مرات الاستدعاء: {res.get('downloads', 0)}"

        if file_type == 'text': bot.send_message(chat_id, res.get('content', file_name), reply_markup=markup)
        elif file_type == 'photo' and file_id: bot.send_photo(chat_id, file_id, caption=caption, reply_markup=markup)
        elif file_id: bot.send_document(chat_id, file_id, caption=caption, reply_markup=markup)
        else: bot.send_message(chat_id, "❌ تنبيه: هذا الملف غير متواجد بخوادم تيليجرام.", reply_markup=markup)
    except Exception as e: logging.error(f"Send File Error: {e}")

# ==========================================
# 11. المعالج المركزي الشامل (Universal Core Handler)
# ==========================================
@bot.message_handler(content_types=['text', 'document', 'photo', 'video', 'audio'])
def universal_handler(message):
    chat_id = message.chat.id
    if not check_rate_limit(chat_id): return
    system_stats["requests_24h"] += 1

    user_data = users_col.find_one({"chat_id": chat_id})
    if user_data and user_data.get("blocked"): return

    settings = settings_col.find_one({}) or {}
    if settings.get("status") == "inactive" and not is_any_admin(chat_id):
        if settings.get("resume_at") and datetime.utcnow() >= settings.get("resume_at"):
            settings_col.update_one({}, {"$set": {"status": "active", "resume_at": None}})
        else:
            bot.send_message(chat_id, "🚧 البوت حالياً في وضع الصيانة والتحديث.")
            return

    text = message.text if message.content_type == 'text' else ""
    path_str = get_path_string(chat_id)
    mode = admin_action_mode.get(chat_id)

    if message.chat.type in ['group', 'supergroup']:
        auto_archive_handler_logic(message)
        if message.content_type != 'text' or not text.startswith("/"): return

    # [منطق كسر الأوضاع المعلقة والتنقل الآمن]
    nav_buttons = ["🔝 القائمة الرئيسية", "🔙 الرجوع للقائمة السابقة"] + list(ACADEMIC_STRUCTURE.keys())
    if text == "🛑 إلغاء الأمر":
        reset_modes(chat_id)
        bot.send_message(chat_id, "✅ تم إلغاء الإجراء بنجاح.")
        show_menu(chat_id)
        return

    if text in nav_buttons:
        # لا تقم بمسح وضع التعيين أو النقل إذا كان يتنقل للوصول للهدف
        if mode not in ["navigate_to_assign", "move_file_dest"]:
            reset_modes(chat_id)
            
        if text == "🔝 القائمة الرئيسية": 
            user_path[chat_id] = []
        elif text == "🔙 الرجوع للقائمة السابقة" and user_path.get(chat_id): 
            user_path[chat_id].pop()
        elif text in ACADEMIC_STRUCTURE.keys(): 
            user_path[chat_id] = [text]
            
        show_menu(chat_id)
        return

    # [استقبال الملفات الذكي المتتابع]
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
                bot.reply_to(message, f"✅ تم حفظ المستند الفردي: *{doc['name']}*\n(يمكنك الاستمرار بإرسال المزيد أو إرسال 🛑 إلغاء الأمر للإنهاء)", parse_mode="Markdown")
                notify_subscribers(doc['name'], path_str, chat_id)
            else:
                bot.reply_to(message, "⚠️ هذا الملف موجود بالفعل في هذا القسم لتجنب التكرار.")
        return 

    if text and not mode and not upload_mode.get(chat_id):
        kw_map = {"تذكير": "⏰ تذكير شخصي (خاص بي)", "تنبيه": "🔔 تنبيهات المقررات", "ذكاء اصطناعي": "🤖 المساعد الذكي (AI)"}
        for kw, action in kw_map.items():
            if text == kw:
                bot.send_message(chat_id, f"💡 توجيه سريع للكلمة: {kw}")
                text = action; break

    if text in ["🔔 تفعيل الإشعارات", "🔕 إلغاء الإشعارات"]:
        users_col.update_one({"chat_id": chat_id}, {"$set": {"smart_notifications": (text == "🔔 تفعيل الإشعارات")}})
        bot.send_message(chat_id, "✅ تم التحديث بنجاح.")
        show_menu(chat_id)
        return

    # [تطوير رسالة المطور الرسمية والمستوردة من الإعدادات]
    if text == "👨‍💻 تواصل مع المشرف العام":
        dev_msg = settings.get("dev_text", DEFAULT_DEV_TEXT)
        bot.send_message(chat_id, dev_msg, parse_mode="Markdown")
        return

    # [تعديل النصوص ديناميكياً للمشرف العام]
    if text == "📝 تعديل نصوص البوت" and is_super_admin(chat_id):
        reset_modes(chat_id)
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("✏️ تعديل رسالة البدء (Start)", "✏️ تعديل رسالة المعلومات (Info)")
        markup.add("✏️ تعديل رسالة المطور", "🛑 إلغاء الأمر")
        bot.send_message(chat_id, "اختر الرسالة التي تريد تعديل نصوصها:", reply_markup=markup)
        return

    if text == "✏️ تعديل رسالة البدء (Start)" and is_super_admin(chat_id):
        admin_action_mode[chat_id] = "edit_start_text"
        bot.send_message(chat_id, "أرسل النص الجديد لرسالة البدء (يمكنك استخدام {first_name} ليتم استبدالها تلقائياً باسم الطالب):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
        return
        
    if mode == "edit_start_text" and text:
        settings_col.update_one({}, {"$set": {"start_text": text}}, upsert=True)
        bot.send_message(chat_id, "✅ تم تحديث رسالة البدء بنجاح.")
        reset_modes(chat_id); show_menu(chat_id); return
        
    if text == "✏️ تعديل رسالة المعلومات (Info)" and is_super_admin(chat_id):
        admin_action_mode[chat_id] = "edit_info_text"
        bot.send_message(chat_id, "أرسل النص الجديد لرسالة المعلومات (/info):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
        return
        
    if mode == "edit_info_text" and text:
        settings_col.update_one({}, {"$set": {"info_text": text}}, upsert=True)
        bot.send_message(chat_id, "✅ تم تحديث رسالة المعلومات بنجاح.")
        reset_modes(chat_id); show_menu(chat_id); return
        
    if text == "✏️ تعديل رسالة المطور" and is_super_admin(chat_id):
        admin_action_mode[chat_id] = "edit_dev_text"
        bot.send_message(chat_id, "أرسل النص الجديد لرسالة التواصل مع المطور:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
        return
        
    if mode == "edit_dev_text" and text:
        settings_col.update_one({}, {"$set": {"dev_text": text}}, upsert=True)
        bot.send_message(chat_id, "✅ تم تحديث رسالة المطور بنجاح.")
        reset_modes(chat_id); show_menu(chat_id); return

    # [ميزات الطالب المتقدمة]
    if text == "🤖 المساعد الذكي (AI)":
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "ai_chat"
        if chat_id not in ai_memory: ai_memory[chat_id] = []
        bot.send_message(chat_id, "🤖 المساعد الذكي جاهز. اسأل وسأجيبك (7 أسئلة يومياً):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
        return
    
    if mode == "ai_chat" and text:
        hr_str = datetime.utcnow().strftime("%Y-%m-%d-%H")
        hr_usage = ai_usage_col.find_one({"hour": hr_str})
        if hr_usage and hr_usage['count'] > 150 and not is_any_admin(chat_id):
            settings_col.update_one({}, {"$set": {"status": "inactive", "resume_at": datetime.utcnow() + timedelta(minutes=15)}}, upsert=True)
            bot.send_message(chat_id, "🚧 تم تفعيل الصيانة التلقائية للضغط العالي. سنعود بعد 15 دقيقة.")
            reset_modes(chat_id); return
            
        ai_usage_col.update_one({"hour": hr_str}, {"$inc": {"count": 1}}, upsert=True)

        day_str = datetime.utcnow().strftime("%Y-%m-%d")
        usage = ai_usage_col.find_one({"chat_id": chat_id, "date": day_str})
        count = usage['count'] + 1 if usage else 1
        
        if count > 7 and not is_any_admin(chat_id):
            bot.send_message(chat_id, "🛑 لقد استنفدت حصتك اليومية (7 أسئلة).")
            return
            
        bot.send_message(chat_id, "⏳ جاري البحث والتفكير...")
        
        cached_ans = kb_col.find_one({"question": text})
        if cached_ans:
            final_ans = cached_ans['answer'] + "\n\n*(⚡ إجابة فورية من الأرشيف السريع)*"
            kb_col.update_one({"_id": cached_ans["_id"]}, {"$inc": {"hits": 1}, "$set": {"last_used": datetime.utcnow()}})
            system_stats["cache_hits_today"] += 1
        else:
            final_ans = get_ai_response(text, chat_id)
            kb_col.insert_one({"question": text, "answer": final_ans, "hits": 1, "last_used": datetime.utcnow()})
            system_stats["ai_queries_today"] += 1
            
        ai_memory[chat_id].append(text)
        if len(ai_memory[chat_id]) > 3: ai_memory[chat_id].pop(0)

        try: bot.send_message(chat_id, final_ans, parse_mode="Markdown")
        except: bot.send_message(chat_id, final_ans)
            
        if not is_any_admin(chat_id):
            ai_usage_col.update_one({"chat_id": chat_id, "date": day_str}, {"$set": {"count": count}}, upsert=True)
            if count == 6: bot.send_message(chat_id, "⚠️ تبقت لك محاولة واحدة فقط اليوم.")
                
        reset_modes(chat_id); show_menu(chat_id)
        return

    if text == "⏰ تذكير شخصي (خاص بي)":
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "set_rem_text"
        bot.send_message(chat_id, "⏰ ما هو موضوع التذكير؟", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
        return
    if mode == "set_rem_text" and text:
        action_payload[chat_id] = text
        admin_action_mode[chat_id] = "set_rem_time"
        bot.send_message(chat_id, "بعد كم ساعة أذكرك؟ (أرقام فقط كـ 2 أو 1.5):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
        return
    if mode == "set_rem_time" and text:
        try:
            reminders_col.insert_one({"chat_id": chat_id, "text": action_payload[chat_id], "notify_at": datetime.utcnow() + timedelta(hours=float(text.strip()))})
            bot.send_message(chat_id, "✅ تم جدولة التنبيه بنجاح.")
        except: bot.send_message(chat_id, "❌ أرقام فقط يرجى.")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if text == "📝 مذكراتي الدراسية":
        reset_modes(chat_id)
        user_notes = users_col.find_one({"chat_id": chat_id}).get("notes", "فارغة.")
        bot.send_message(chat_id, f"📝 *مذكراتك:*\n{user_notes}", parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("➕ إضافة ملاحظة", "🗑️ مسح مذكراتي").add("🔙 الرجوع للقائمة السابقة"))
        return
    if text == "➕ إضافة ملاحظة":
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "add_note"
        bot.send_message(chat_id, "أرسل الملاحظة:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
        return
    if mode == "add_note" and text:
        curr = users_col.find_one({"chat_id": chat_id}).get("notes", "")
        if curr == "فارغة.": curr = ""
        users_col.update_one({"chat_id": chat_id}, {"$set": {"notes": curr + f"\n- {text}"}})
        bot.send_message(chat_id, "✅ تم حفظ الملاحظة.")
        reset_modes(chat_id); user_path[chat_id] = ["🌟 ميزات مساعدة للطالب"]; show_menu(chat_id)
        return
    if text == "🗑️ مسح مذكراتي":
        users_col.update_one({"chat_id": chat_id}, {"$set": {"notes": "فارغة."}})
        bot.send_message(chat_id, "🗑️ تم مسح المذكرات.")
        user_path[chat_id] = ["🌟 ميزات مساعدة للطالب"]; show_menu(chat_id)
        return

    # [البحث الهجين المطور: يشمل البحث عن المقررات والمسارات]
    if text == "🔍 بحث عن ملف":
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "search_type"
        bot.send_message(chat_id, "🔍 اختر النطاق:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🌍 بحث شامل", "📂 بحث في مساري الحالي").add("🛑 إلغاء الأمر"))
        return
    if mode == "search_type" and text in ["🌍 بحث شامل", "📂 بحث في مساري الحالي"]:
        action_payload[chat_id] = "global" if text == "🌍 بحث شامل" else path_str
        admin_action_mode[chat_id] = "search_exec"
        bot.send_message(chat_id, "🔍 أرسل كلمة البحث (اسم مقرر، ملف، أو تفاصيل):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
        return
    if mode == "search_exec" and text:
        scope = action_payload.get(chat_id, "global")
        
        query = {"$text": {"$search": text}}
        if scope != "global" and scope: query["menu_path"] = {"$regex": f"^{re.escape(scope)}"}
        results = list(files_col.find(query, {"score": {"$meta": "textScore"}}).sort([("score", {"$meta": "textScore"})]).limit(10))
        
        if not results:
            q_reg = {
                "$or": [
                    {"name": {"$regex": text, "$options": "i"}},
                    {"caption": {"$regex": text, "$options": "i"}},
                    {"menu_path": {"$regex": text, "$options": "i"}}
                ]
            }
            if scope != "global" and scope:
                q_reg = {"$and": [{"menu_path": {"$regex": f"^{re.escape(scope)}"}}, q_reg]}
            results = list(files_col.find(q_reg).limit(15))
            
        if results:
            bot.send_message(chat_id, f"🔍 وجدنا {len(results)} نتائج مطابقة:")
            for item in results: send_file_to_user(chat_id, item, has_permission(chat_id, item['menu_path']))
        else: bot.send_message(chat_id, "❌ لم نجد ملفات أو مقررات مطابقة للكلمة المدخلة.")
        reset_modes(chat_id); show_menu(chat_id)
        return

    # [القوائم السريعة]
    if text == "🔥 الملفات الأكثر شعبية":
        pop = list(files_col.find({"downloads": {"$gt": 0}}).sort("downloads", -1).limit(5))
        if pop:
            bot.send_message(chat_id, "🔥 *أشهر الملفات:*", parse_mode="Markdown")
            for p in pop: send_file_to_user(chat_id, p, False)
        else: bot.send_message(chat_id, "لا إحصائيات بعد.")
        return
    if text == "🆕 تحديثات اليوم":
        rec = list(files_col.find({"upload_date": {"$gte": datetime.utcnow() - timedelta(days=1)}}).limit(10))
        if rec:
            bot.send_message(chat_id, "🆕 *أحدث الملفات:*", parse_mode="Markdown")
            for r in rec: send_file_to_user(chat_id, r, False)
        else: bot.send_message(chat_id, "لا توجد ملفات جديدة اليوم.")
        return
    if text == "🔔 تنبيهات المقررات":
        active_alerts = list(alerts_col.find())
        alert_msg = "🔔 *مركز التنبيهات والأحداث:*\n\n" + ("لا توجد تنبيهات حالياً." if not active_alerts else "".join([f"📌 {a['text']}\n" for a in active_alerts]))
        alert_markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        if has_permission(chat_id, "🌟 ميزات مساعدة للطالب") or is_super_admin(chat_id):
            alert_markup.add(KeyboardButton("➕ إضافة تنبيه جديد"), KeyboardButton("🗑️ تفريغ كافة التنبيهات"))
        alert_markup.add("🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية")
        bot.send_message(chat_id, alert_msg, reply_markup=alert_markup, parse_mode="Markdown")
        return
    if text == "➕ إضافة تنبيه جديد" and (has_permission(chat_id, "🌟 ميزات مساعدة للطالب") or is_super_admin(chat_id)):
        reset_modes(chat_id); admin_action_mode[chat_id] = "add_course_alert"
        bot.send_message(chat_id, "📝 أرسل التنبيه:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
        return
    if mode == "add_course_alert" and text:
        alerts_col.insert_one({"text": text.strip(), "created_at": datetime.utcnow()})
        bot.send_message(chat_id, "✅ تم حفظ التنبيه.")
        for su in list(users_col.find()):
            try: bot.send_message(su['chat_id'], f"📢 *تنبيه إداري جديد:*\n{text.strip()}", parse_mode="Markdown")
            except: pass
        reset_modes(chat_id); user_path[chat_id] = ["🌟 ميزات مساعدة للطالب"]; show_menu(chat_id)
        return
    if text == "🗑️ تفريغ كافة التنبيهات" and (has_permission(chat_id, "🌟 ميزات مساعدة للطالب") or is_super_admin(chat_id)):
        alerts_col.delete_many({})
        bot.send_message(chat_id, "🗑️ تم المسح."); user_path[chat_id] = ["🌟 ميزات مساعدة للطالب"]; show_menu(chat_id)
        return

    # [لوحة المشرف العام والأدوات المتقدمة]
    if is_super_admin(chat_id) or is_global_admin(chat_id):
        
        if text == "📊 حالة النظام" and is_super_admin(chat_id):
            u_c = users_col.count_documents({})
            f_c = files_col.count_documents({})
            d_c = folders_col.count_documents({})
            db_size = db.command("dbstats").get("dataSize", 0) / (1024 * 1024)
            ai_ratio = (system_stats['cache_hits_today'] / (system_stats['ai_queries_today'] + system_stats['cache_hits_today'] + 0.001)) * 100
            
            try:
                with open('/proc/loadavg', 'r') as f: cpu = f.read().split()[0]
                with open('/proc/meminfo', 'r') as f: mem = f.read()
                m_tot = int(re.search(r'MemTotal:\s+(\d+)', mem).group(1))
                m_free = int(re.search(r'MemAvailable:\s+(\d+)', mem).group(1))
                ram = f"{(m_tot-m_free)/1024:.1f}/{m_tot/1024:.1f} MB"
            except: cpu, ram = "N/A", "N/A"
            
            st = f"""📊 *حالة النظام:*
👥 المستخدمين: {u_c} | 📁 الملفات: {f_c} | 📂 المجلدات: {d_c}
💾 حجم DB التقريبي: {db_size:.2f} MB
🤖 أسئلة AI: {system_stats['ai_queries_today']} | ⚡ كاش: {system_stats['cache_hits_today']} ({ai_ratio:.1f}% توفير)
🔄 طلبات 24 ساعة: {system_stats['requests_24h']}
⚙️ CPU: {cpu} | 🧠 RAM: {ram}
⏱️ وقت التشغيل: {str(datetime.utcnow() - START_TIME).split('.')[0]}"""
            bot.send_message(chat_id, st, parse_mode="Markdown")
            return

        if text == "💾 تصدير نسخة احتياطية" and is_super_admin(chat_id):
            bot.send_message(chat_id, "⏳ جاري ضغط وتصدير البيانات...")
            bkp = { "files": list(files_col.find({}, {"_id": 0})), "folders": list(folders_col.find({}, {"_id": 0})) }
            bio = io.BytesIO(json.dumps(bkp, default=json_util.default, ensure_ascii=False).encode('utf-8'))
            bio.name = f"DB_Backup_{datetime.utcnow().strftime('%Y%m%d')}.json"
            bot.send_document(chat_id, bio, caption="💾 نسخة JSON من بياناتك الحيوية.")
            return

        if text == "👥 إحصائيات المشتركين" and is_super_admin(chat_id):
            all_u = list(users_col.find())
            sm = f"📊 إجمالي المشتركين: {len(all_u)}\n"
            for u in all_u: sm += f"• {u.get('first_name', '-')} | `{u.get('chat_id')}`\n"
            if len(sm) > 3800:
                bio = io.BytesIO(sm.encode('utf-8')); bio.name = "Users.txt"
                bot.send_document(chat_id, bio, caption="📊 كشف الطلاب")
            else: bot.send_message(chat_id, sm, parse_mode="Markdown")
            return

        if text == "⚙️ التحكم بالنظام" and is_super_admin(chat_id):
            sys_markup = ReplyKeyboardMarkup(resize_keyboard=True).add("▶️ تشغيل البوت", "⏸️ إيقاف البوت", "🔝 القائمة الرئيسية")
            bot.send_message(chat_id, "🛡️ مركز التحكم المركزي بالخوادم ومنظومة العمل:", reply_markup=sys_markup)
            return

        if text in ["▶️ تشغيل البوت", "⏸️ إيقاف البوت"] and is_super_admin(chat_id):
            status = "active" if text == "▶️ تشغيل البوت" else "inactive"
            settings_col.update_one({}, {"$set": {"status": status, "resume_at": None}}, upsert=True)
            bot.send_message(chat_id, f"✅ تم وضع البوت في الحالة: {status} (الإدارة مستثناة).")
            show_menu(chat_id); return

        if text == "📂 إضافة مجلد بالرئيسية" and is_super_admin(chat_id):
            reset_modes(chat_id); add_folder_mode[chat_id] = True; user_path[chat_id] = []
            bot.send_message(chat_id, "📂 اكتب اسم المجلد الجديد المراد زرعه في الشاشة الرئيسية:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            return

        if text == "📢 إرسال رسالة جماعية" and is_super_admin(chat_id):
            reset_modes(chat_id); broadcast_mode[chat_id] = True
            bot.send_message(chat_id, "📢 أرسل نص التعميم أو الرسالة المراد بثها لكافة الطلاب:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            return
            
        if broadcast_mode.get(chat_id) and is_super_admin(chat_id):
            broadcast_mode[chat_id] = False
            bot.send_message(chat_id, "⏳ جاري بدء البث الجماعي وتعميم الرسالة...")
            b_succ = 0
            for stu in list(users_col.find()):
                try:
                    bot.copy_message(stu['chat_id'], chat_id, message.message_id)
                    b_succ += 1
                except: pass
            bot.send_message(chat_id, f"📢 اكتمل البث بنجاح!\n✅ تم إيصال الرسالة إلى {b_succ} طالب.")
            show_menu(chat_id); return

        if text == "👤 تجربة كمستخدم":
            testing_mode[chat_id] = True
            bot.send_message(chat_id, "👀 تم تفعيل وضع المحاكاة بنجاح! أنت الآن تتصفح كطالب عادي.")
            user_path[chat_id] = []; show_menu(chat_id); return

        if text == "🛑 إنهاء التجربة والعودة للإشراف":
            testing_mode[chat_id] = False
            bot.send_message(chat_id, "💼 تم إنهاء وضع المحاكاة وعادت إليك صلاحيات الإدارة.")
            user_path[chat_id] = []; show_menu(chat_id); return

        if text == "🛠️ إدارة المشرفين" and is_super_admin(chat_id):
            adm_docs = list(admins_col.find())
            txt = "🛠️ *المشرفين:*\n"
            for adm in adm_docs:
                u_info = users_col.find_one({"chat_id": adm["id"]})
                n = u_info.get("first_name", "-") if u_info else "-"
                t = "عام" if adm.get("type") == "global" else ("مطلق" if adm.get("type") == "super" else "مخصص")
                txt += f"👤 {n} | `{adm['id']}` | {t}\n"
            m = ReplyKeyboardMarkup(resize_keyboard=True).add("➕ إضافة مشرف عام", "➕ إضافة مشرف مسار مخصص", "➖ إزالة مشرف", "🔝 القائمة الرئيسية")
            bot.send_message(chat_id, txt, reply_markup=m, parse_mode="Markdown"); return

        if text in ["➕ إضافة مشرف عام", "➖ إزالة مشرف", "🚫 حظر مستخدم"] and is_super_admin(chat_id):
            reset_modes(chat_id)
            admin_action_mode[chat_id] = "add_glb" if text.startswith("➕") else ("rm_adm" if text.startswith("➖") else "blk_usr")
            bot.send_message(chat_id, "أرسل الآيدي الرقمي:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            return

        if text == "➕ إضافة مشرف مسار مخصص" and is_super_admin(chat_id):
            reset_modes(chat_id); admin_action_mode[chat_id] = "navigate_to_assign"; user_path[chat_id] = []
            bot.send_message(chat_id, "📍 تصفح الأقسام الآن بشكل طبيعي للوصول للقسم، ثم اضغط (✅ تعيين مشرف لهذا القسم).")
            show_menu(chat_id); return

        if mode == "navigate_to_assign" and text == "✅ تعيين مشرف لهذا القسم" and is_super_admin(chat_id):
            admin_action_mode[chat_id] = "ask_path_admin_id"
            bot.send_message(chat_id, f"👤 المسار المختار:\n`{path_str}`\n\nأرسل الآن الرقم التعريفي (الآيدي) للمشرف لربطه بهذا المسار حصرياً:", parse_mode="Markdown", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            return

        if mode == "ask_path_admin_id" and text and is_super_admin(chat_id):
            try:
                tid = int(text.strip())
                admins_col.update_one({"id": tid}, {"$set": {"id": tid, "type": "path"}, "$addToSet": {"allowed_paths": path_str}}, upsert=True)
                bot.send_message(chat_id, f"✅ تم تقييد صلاحيات المشرف حصرياً على هذا المسار.", parse_mode="Markdown")
                reset_modes(chat_id); show_menu(chat_id)
            except ValueError: bot.send_message(chat_id, "❌ خطأ: الآيدي يجب أن يكون أرقاماً فقط.")
            return

        if mode == "add_glb" and text and is_super_admin(chat_id):
            try:
                tid = int(text.strip())
                admins_col.update_one({"id": tid}, {"$set": {"id": tid, "type": "global"}}, upsert=True)
                bot.send_message(chat_id, "✅ تمت إضافة المشرف العام.")
            except: bot.send_message(chat_id, "❌ أرقام فقط.")
            reset_modes(chat_id); show_menu(chat_id); return

        if mode == "rm_adm" and text and is_super_admin(chat_id):
            try:
                tid = int(text.strip())
                if tid != SUPER_ADMIN_ID: admins_col.delete_one({"id": tid})
                bot.send_message(chat_id, "✅ تمت الإزالة.")
            except: bot.send_message(chat_id, "❌ أرقام فقط.")
            reset_modes(chat_id); show_menu(chat_id); return
            
        if mode == "blk_usr" and text and is_super_admin(chat_id):
            try:
                tid = int(text.strip())
                if tid == SUPER_ADMIN_ID: bot.send_message(chat_id, "❌ لا يمكن حظر المشرف المطلق.")
                else:
                    u = users_col.find_one({"chat_id": tid})
                    if u:
                        ns = not u.get("blocked", False)
                        users_col.update_one({"_id": u["_id"]}, {"$set": {"blocked": ns}})
                        bot.send_message(chat_id, f"✅ الحالة الجديدة: {'محظور 🚫' if ns else 'نشط ✅'}")
                    else: bot.send_message(chat_id, "❌ غير موجود.")
            except: bot.send_message(chat_id, "❌ أرقام فقط.")
            reset_modes(chat_id); show_menu(chat_id); return

        if text == "🧹 أرشفة الملفات القديمة" and is_super_admin(chat_id):
            old = list(files_col.find({"upload_date": {"$lt": datetime.utcnow() - timedelta(days=180)}}))
            for f in old: files_col.update_one({"_id": f["_id"]}, {"$set": {"menu_path": "🗄️ الأرشيف القديم > " + f['menu_path']}})
            if old: folders_col.update_one({"parent_path": "", "folder_name": "🗄️ الأرشيف القديم"}, {"$set": {"created_at": datetime.utcnow()}}, upsert=True)
            bot.send_message(chat_id, f"🧹 تم أرشفة {len(old)} ملف قديم بنجاح.")
            return

        if text == "🏷️ إدارة الأرشفة" and is_super_admin(chat_id):
            archive_markup = ReplyKeyboardMarkup(resize_keyboard=True).add("📋 عرض الهاشتاجات النشطة", "🗑️ حذف هاشتاج معين", "🔝 القائمة الرئيسية")
            bot.send_message(chat_id, "🏷️ *نظام الأرشفة التلقائية الذكي*", reply_markup=archive_markup, parse_mode="Markdown")
            return

        if text == "📋 عرض الهاشتاجات النشطة" and is_super_admin(chat_id):
            verified_groups = list(auth_groups_col.find())
            active_tags = list(hashtags_col.find())
            h_msg = "🛡️ *المجموعات المعتمدة المرتبطة بقاعدة البيانات:*\n" + "".join([f"▪️ {group_item.get('title', 'موثقة')}\n" for group_item in verified_groups])
            h_msg += "\n🏷️ *الروابط والهاشتاجات النشطة:*\n" + "".join([f"🔸 {tag_item['tag']} ⇦ {tag_item['path'].split(' > ')[-1]}\n" for tag_item in active_tags])
            bot.send_message(chat_id, h_msg if (verified_groups or active_tags) else "لا توجد هاشتاجات حالياً.", parse_mode="Markdown")
            return

        if text == "🗑️ حذف هاشتاج معين" and is_super_admin(chat_id):
            reset_modes(chat_id); admin_action_mode[chat_id] = "del_hashtag"
            bot.send_message(chat_id, "أرسل الهاشتاج المراد تدميره:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            return

        if text == "🔗 ربط هاشتاج بالقسم" and is_super_admin(chat_id):
            reset_modes(chat_id); admin_action_mode[chat_id] = "add_hashtag"
            bot.send_message(chat_id, f"أرسل اسم الهاشتاج الجديد لربطه بـ:\n`{path_str}`", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"), parse_mode="Markdown")
            return

        if mode == "add_hashtag" and text and is_super_admin(chat_id):
            final_tag = text.strip() if text.strip().startswith("#") else "#" + text.strip()
            hashtags_col.insert_one({"tag": final_tag, "path": path_str})
            bot.send_message(chat_id, f"✅ تم ربط الهاشتاج {final_tag} بنجاح."); reset_modes(chat_id); show_menu(chat_id); return
            
        if mode == "del_hashtag" and text and is_super_admin(chat_id):
            final_tag = text.strip() if text.strip().startswith("#") else "#" + text.strip()
            del_res = hashtags_col.delete_one({"tag": final_tag})
            bot.send_message(chat_id, "✅ تم الحذف." if del_res.deleted_count > 0 else "❌ غير مسجل."); reset_modes(chat_id); show_menu(chat_id); return

    # [العمليات الإدارية داخل الأقسام]
    if has_permission(chat_id, path_str) and path_str:
        if text == "➕ إضافة ملف/نص":
            reset_modes(chat_id); upload_mode[chat_id] = True
            bot.send_message(chat_id, "📥 أرسل الملفات الآن (مفرد أو ألبوم متصل):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            return
        if text == "📂 إضافة مجلد":
            reset_modes(chat_id); add_folder_mode[chat_id] = True
            bot.send_message(chat_id, "📂 اكتب اسم المجلد الأكاديمي الفرعي الجديد:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            return
        if text == "🗑️ حذف هذا القسم":
            parent = path_str.rsplit(' > ', 1)[0] if ' > ' in path_str else ""
            folders_col.delete_one({"parent_path": parent, "folder_name": user_path[chat_id][-1]})
            bot.send_message(chat_id, "🗑️ تم الحذف."); user_path[chat_id].pop(); reset_modes(chat_id); show_menu(chat_id); return
        if text == "✏️ إعادة تسمية هذا القسم":
            reset_modes(chat_id); admin_action_mode[chat_id] = "rn_fld"
            bot.send_message(chat_id, "✏️ أرسل الاسم الجديد:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            return

    if mode == "rn_fld" and text:
        parent = path_str.rsplit(' > ', 1)[0] if ' > ' in path_str else ""
        folders_col.update_one({"parent_path": parent, "folder_name": user_path[chat_id][-1]}, {"$set": {"folder_name": text.strip()}})
        user_path[chat_id][-1] = text.strip()
        bot.send_message(chat_id, "✅ تم التعديل."); reset_modes(chat_id); show_menu(chat_id); return

    if mode == "rename_file" and text:
        files_col.update_one({"_id": ObjectId(action_payload.get(chat_id))}, {"$set": {"name": text.strip()}})
        bot.send_message(chat_id, "✅ تم التعديل."); reset_modes(chat_id); show_menu(chat_id); return

    if mode == "replace_file":
        doc = build_file_doc(message, path_str)
        update_data = {"type": doc['type'], "file_id": doc['file_id'], "name": doc['name'], "caption": doc['caption']} if doc['file_id'] else {"type": "text", "content": text, "name": text[:30], "file_id": None}
        files_col.update_one({"_id": ObjectId(action_payload.get(chat_id))}, {"$set": update_data})
        bot.send_message(chat_id, "✅ تم الاستبدال."); reset_modes(chat_id); show_menu(chat_id); return

    if add_folder_mode.get(chat_id) and text and has_permission(chat_id, path_str):
        folders_col.insert_one({"parent_path": path_str, "folder_name": text.strip(), "created_at": datetime.utcnow()})
        bot.send_message(chat_id, f"✅ تم إنشاء: {text.strip()}"); reset_modes(chat_id); show_menu(chat_id); return

    if upload_mode.get(chat_id) and message.content_type == 'text' and has_permission(chat_id, path_str):
        files_col.insert_one({"menu_path": path_str, "name": text[:60].strip(), "type": "text", "content": text, "downloads": 0, "upload_date": datetime.utcnow()})
        bot.send_message(chat_id, "✅ تم حفظ التلخيص."); reset_modes(chat_id, clear_upload=False); notify_subscribers("ملخص نصي", path_str, chat_id); return

    # [فتح الملفات والتنقل العادي]
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
# 12. أزرار التحكم الجانبية (Inline Callbacks)
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith(('rn_', 'rp_', 'dl_', 'mv_', 'rl_')))
def handle_inline_callbacks(call):
    chat_id = call.message.chat.id
    
    try:
        action, obj_id = call.data.split('_')
    except ValueError:
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

@app.route('/webhook', methods=['POST'])
def webhook_listen_route():
    if request.headers.get('content-type') == 'application/json':
        bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
        return "!", 200
    return "Invalid", 403

@app.route("/")
def index_home_route(): return "Bot V4 is RUNNING 🚀", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
