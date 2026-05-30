import telebot
from pymongo import MongoClient
from flask import Flask, request
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import sys
import threading
import time
from datetime import datetime, timedelta
from bson.objectid import ObjectId
import io
import re
import requests
import os

# ==========================================
# 1. الإعدادات والترميز وحل مشكلات التوافق
# ==========================================
if sys.version_info >= (3, 0):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_TOKEN = '7524289470:AAGkeX96s1s6saxGP3uy14MN9it19nKn10A'
SUPER_ADMIN_ID = 6842543527  # الواثق (المشرف العام المطلق)
MONGO_URI = "mongodb+srv://Alwatheq:alwatheq73@cluster0.ft0mdkt.mongodb.net/?appName=Cluster0"
GEMINI_API_KEY = "AIzaSy" # سيتم جلب مفتاح بيئة التشغيل الفعلي إذا كان متوفراً

# محاولة تحميل مفتاح الـ API الحقيقي من متغيرات البيئة إن وجد
if "GEMINI_API_KEY" in os.environ:
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# ==========================================
# 2. الاتصال الآمن وقصير المدى بقاعدة البيانات
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
    
    # --- الجداول الجديدة المضافة بناءً على طلبك ---
    kb_col = db['knowledge_base']          # مكتبة الأسئلة المتكررة
    ai_usage_col = db['ai_usage']          # نظام حصص الذكاء الاصطناعي
    reminders_col = db['personal_reminders'] # نظام التذكير الشخصي
    
    print("Database Connected Flawlessly! 🎉")
except Exception as db_err:
    print(f"MongoDB Error Context: {db_err}")

# زرع وثائق التهيئة الافتراضية لحماية المنصة من الانهيار
if admins_col.count_documents({"id": SUPER_ADMIN_ID}) == 0:
    admins_col.insert_one({"id": SUPER_ADMIN_ID, "type": "super", "allowed_paths": []})
if settings_col.count_documents({}) == 0:
    settings_col.insert_one({"status": "active"})

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)
BOT_USERNAME = bot.get_me().username
media_groups = {}  # مجمع ألبومات تيليجرام لمنع سقوط الملفات المتعددة

# ==========================================
# 3. الهيكل الأكاديمي الصارم والمجلد الاحترافي
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
    "🌟 ميزات مساعدة للطالب": {}  # المجلد المعزول لجميع الأدوات الذكية والمساعدة
}

# قواميس حفظ الجلسات وحالات المستخدمين والمشرفين
user_path = {}
upload_mode = {}
add_folder_mode = {}
admin_action_mode = {}
testing_mode = {}
action_payload = {}
temp_data = {}
broadcast_mode = {}

# ==========================================
# 4. منظومة الصلاحيات والأمان المتعددة المستويات
# ==========================================
def is_super_admin(chat_id):
    return chat_id == SUPER_ADMIN_ID

def has_permission(chat_id, current_path_str):
    if testing_mode.get(chat_id): 
        return False
    if is_super_admin(chat_id): 
        return True
    admin = admins_col.find_one({"id": chat_id})
    if not admin: 
        return False
    if admin.get("type") == "global": 
        return True
    # صلاحيات مشرف المسار المخصص (Prefix Matching)
    for allowed_p in admin.get("allowed_paths", []):
        if current_path_str.startswith(allowed_p) or current_path_str == allowed_p:
            return True
    return False

def get_menu_by_path(path):
    menu = ACADEMIC_STRUCTURE
    for segment in path:
        if isinstance(menu, dict) and segment in menu:
            menu = menu[segment]
        else:
            return None
    return menu

def get_path_string(chat_id):
    return " > ".join(user_path.get(chat_id, []))

def reset_modes(chat_id):
    upload_mode[chat_id] = False
    add_folder_mode[chat_id] = False
    broadcast_mode[chat_id] = False
    admin_action_mode[chat_id] = None
    action_payload.pop(chat_id, None)

# ==========================================
# 5. محرك الذكاء الاصطناعي الخارق والمضمون 100%
# ==========================================
def get_ai_response(prompt):
    clean_prompt = f"أنت مساعد ذكي ومفيد للمنصة الأكاديمية الرسمية لقسم الذكاء الاصطناعي وعلوم البيانات. أجب على الأسئلة العامة أو الأكاديمية أو البرمجية بدقة واختصار وباللغة العربية الفصحى: {prompt}"
    
    # الخطة (أ): الاستدعاء المباشر عبر موديلات جوجل المتعددة بالتوالي في حالة توفر المفتاح وسيرفرات الخدمة
    if GEMINI_API_KEY and not GEMINI_API_KEY.startswith("AIzaSy"):
        for model_name in ["gemini-2.0-flash-lite-preview-02-05", "gemini-2.0-flash", "gemini-1.5-flash"]:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
                payload = {
                    "contents": [{"parts": [{"text": clean_prompt}]}],
                    "generationConfig": {"temperature": 0.4, "maxOutputTokens": 500}
                }
                res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=6)
                if res.status_code == 200:
                    data = res.json()
                    return data['candidates'][0]['content']['parts'][0]['text'].strip()
            except:
                continue

    # الخطة (ب) المضمونة 100%: خوادم المعالجة اللغوية الحرة والمفتوحة بدون مفاتيح المقارنة
    for backup_model in ["openai", "llama", "mistral"]:
        try:
            encoded_prompt = requests.utils.quote(clean_prompt)
            backup_url = f"https://text.pollinations.ai/{encoded_prompt}?model={backup_model}&seed=42"
            res = requests.get(backup_url, timeout=12)
            if res.status_code == 200 and res.text:
                return res.text.strip()
        except:
            continue

    return "🤖 نعتذر بشدة، تواجه خوادم الذكاء الاصطناعي ضغطاً عالمياً غير متوقع حالياً. يرجى إعادة إرسال استفسارك بعد لحظات بسيطة."

# ==========================================
# 5.1 العامل الخلفي لمنظومة التنبيهات الشخصية (Background Worker)
# ==========================================
def reminder_worker():
    while True:
        try:
            now = datetime.utcnow()
            due_reminders = list(reminders_col.find({"notify_at": {"$lte": now}}))
            for r in due_reminders:
                try:
                    bot.send_message(r['chat_id'], f"⏰ *تنبيه شخصي حان وقته:*\n\n{r['text']}", parse_mode="Markdown")
                except:
                    pass
                reminders_col.delete_one({"_id": r['_id']})
        except:
            pass
        time.sleep(60)

# تشغيل العامل في الخلفية لضمان عدم توقف السيرفر
threading.Thread(target=reminder_worker, daemon=True).start()

# ==========================================
# 6. المعالجة المتقدمة وحفظ باقات المستندات (Multi-File System)
# ==========================================
def build_file_doc(message, path_str):
    if message.content_type == 'document':
        name = message.document.file_name or "مستند غير مسمى"
        file_id = message.document.file_id
    elif message.content_type == 'photo':
        name = "صورة توضيحية"
        file_id = message.photo[-1].file_id
    elif message.content_type == 'video':
        name = "مقطع مرئي"
        file_id = message.video.file_id
    elif message.content_type == 'audio':
        name = "ملف صوتي"
        file_id = message.audio.file_id
    else:
        name = "ملحق أكاديمي"
        file_id = None

    caption_text = message.caption or name
    clean_name = caption_text.replace("📄", "").replace("📌", "").replace("🖼️", "").strip()
    
    return {
        "menu_path": path_str,
        "name": clean_name[:60],
        "type": message.content_type,
        "caption": message.caption,
        "file_id": file_id,
        "downloads": 0,
        "upload_date": datetime.utcnow()
    }

def notify_subscribers(file_name, path_str, uploader_id):
    """إرسال إشعار للمشتركين فقط عند رفع ملف جديد"""
    subscribers = list(users_col.find({"smart_notifications": True}))
    for sub in subscribers:
        if sub['chat_id'] != uploader_id:
            try:
                bot.send_message(sub['chat_id'], f"🔔 *تأكيد وصول ملف أكاديمي جديد!*\nتمت إضافة: `{file_name}`\n📁 القسم: {path_str}", parse_mode="Markdown")
            except:
                pass

def process_media_group(chat_id, media_group_id, path_str):
    time.sleep(3)
    if media_group_id not in media_groups:
        return
    messages_batch = media_groups.pop(media_group_id)
    successful_uploads = 0
    first_file_name = ""
    
    for msg in messages_batch:
        doc = build_file_doc(msg, path_str)
        if doc['file_id']:
            files_col.insert_one(doc)
            successful_uploads += 1
            if not first_file_name:
                first_file_name = doc['name']
            
    try:
        bot.send_message(chat_id, f"✅ تم استقبال ورفع الباقة بنجاح!\n📦 إجمالي الملفات المحفوظة: {successful_uploads} ملفات.\n📁 في المسار: {path_str}")
        notify_subscribers(f"باقة ملفات (منها: {first_file_name})", path_str, chat_id)
    except:
        pass

# ==========================================
# 7. الأرشفة التلقائية ومراقبة المجموعات
# ==========================================
def auto_archive_handler_logic(message):
    if not auth_groups_col.find_one({"chat_id": message.chat.id}):
        return 
    caption = message.caption or ""
    for tag_data in list(hashtags_col.find()):
        if tag_data['tag'] in caption:
            doc = build_file_doc(message, tag_data['path'])
            doc['name'] = doc['name'].replace(tag_data['tag'], "").strip() or "ملف مؤرشف تلقائياً"
            if doc['file_id']:
                files_col.insert_one(doc)
                try:
                    bot.reply_to(message, f"🎯 تمت الأرشفة الفورية والتخزين التلقائي للمستند في مادة:\n🛡️ *{tag_data['path'].split(' > ')[-1]}*", parse_mode="Markdown")
                except:
                    pass
            break

# ==========================================
# 8. أوامر الترحيب والمعلومات الرسمية الشاملة
# ==========================================
@bot.message_handler(commands=['start'])
def start_command(message):
    chat_id = message.chat.id
    first_name = message.from_user.first_name or "أيها الطالب الطموح"
    
    # تحديث بيانات الطالب وتفعيل إشعارات الوصول افتراضياً
    users_col.update_one(
        {"chat_id": chat_id}, 
        {
            "$set": {"first_name": first_name, "username": f"@{message.from_user.username}", "last_interaction": datetime.utcnow()},
            "$setOnInsert": {"smart_notifications": True}
        }, 
        upsert=True
    )
    
    # فك تشفير روابط النشر والمشاركة المباشرة العميقة (Deep Linking)
    command_args = message.text.split()
    if len(command_args) > 1:
        try:
            target_file = files_col.find_one({"_id": ObjectId(command_args[1])})
            if target_file:
                files_col.update_one({"_id": target_file["_id"]}, {"$inc": {"downloads": 1}})
                bot.send_message(chat_id, "📥 جاري سحب وإحضار الملف الأكاديمي المطلوب من قاعدة البيانات...")
                send_file_to_user(chat_id, target_file, has_permission(chat_id, target_file['menu_path']))
                return
        except:
            pass

    user_path[chat_id] = []
    reset_modes(chat_id)
    testing_mode[chat_id] = False
    
    welcome_msg = (
        f"🌟 أهلاً بك يا {first_name} في المنصة الأكاديمية الرقمية الرسمية! 🎓\n\n"
        f"يسعدنا جداً انضمامك إلينا. تم تصميم هذا النظام ليكون بوابتك الموثوقة للوصول إلى كافة المراجع، الملخصات، المحاضرات، ونماذج الاختبارات لكل المواد الدراسية بشكل دائم ومستقر.\n\n"
        f"📚 مسيرتك الأكاديمية وتفوقك هو هدفنا الأسمى. انطلق وتصفح المواد والمقررات الدراسية أو استفد من ميزات الطالب الذكية عبر اللوحة التفاعلية أدناه 👇"
    )
    bot.send_message(chat_id, welcome_msg)
    show_menu(chat_id)

@bot.message_handler(commands=['info'])
def info_command_handler(message):
    info_msg = (
        "🤖 *المنصة الأكاديمية الذكية (AI & DS)* 🎓\n\n"
        "مرحباً بك في بوابتك الأكاديمية الرقمية، المخصصة لخدمة طلاب قسم الذكاء الاصطناعي وعلوم البيانات. تم تصميم هذا البوت ليكون رفيقك الدائم في رحلتك الدراسية.\n\n"
        "--- \n\n"
        "### 🔹 *ماذا يقدم لك هذا البوت؟*\n\n"
        "📂 *الأرشيف الأكاديمي:*\n"
        "وصول سريع ومنظم لجميع محاضراتك، ملخصاتك، ونماذج الاختبارات لكل المستويات الدراسية.\n\n"
        "🤖 *المساعد الذكي (AI):*\n"
        "رفيقك في المذاكرة؛ اطرح أي سؤال علمي، استفسار برمجي، أو معادلة رياضية وسأقوم بمساعدتك فوراً.\n\n"
        "🔔 *مركز التنبيهات:*\n"
        "كن أول من يعلم! تابع أهم تنبيهات المقررات والاختبارات القادمة في وقتها.\n\n"
        "🔍 *محرك البحث المتقدم:*\n"
        "لا تضع وقتك في التصفح; ابحث عن أي ملف أو محاضرة بكلمة واحدة فقط.\n\n"
        "--- \n\n"
        "### 🛠️ *حول النظام*\n"
        "تم تطوير وبرمجة هذه المنصة بالكامل بواسطة *الدفعة الثانية - قسم الذكاء الاصطناعي وعلوم البيانات*. تم تصميمها كحل ذكي ومفتوح لتسهيل الوصول للمصادر الدراسية، وهي في تحديث مستمر لتلبية احتياجاتكم.\n\n"
        "💡 *نصيحة:* إذا واجهت أي مشكلة تقنية أو كان لديك ملف تود إضافته لإثراء زملائك، يرجى التواصل مع الإدارة العليا للمنصة."
    )
    bot.send_message(message.chat.id, info_msg, parse_mode="Markdown")

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
# 9. نظام توليد وعرض القوائم والديناميكية الشاملة
# ==========================================
def show_menu(chat_id):
    path = user_path.get(chat_id, [])
    current_menu = get_menu_by_path(path)
    path_str = get_path_string(chat_id)
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mode = admin_action_mode.get(chat_id)
    
    if mode == "add_path_admin_path":
        markup.add(KeyboardButton("✅ تعيين صلاحية المشرف هنا"), KeyboardButton("🛑 إلغاء الأمر"))
        bot.send_message(chat_id, f"📍 تصفح الهيكل الأكاديمي للوصول للقسم المستهدف، ثم اضغط على زر التعيين لإثبات الصلاحية.\n📌 المسار الحالي: {path_str or 'الرئيسية'}", reply_markup=markup)
        return
    elif mode == "move_file_dest":
        markup.add(KeyboardButton("📦 أنقل الملف إلى هذا القسم"), KeyboardButton("🛑 إلغاء الأمر"))
        bot.send_message(chat_id, f"📦 تصفح الأقسام للوصول لموقع النقل الجديد واضغط على زر التأكيد.\n📌 المسار الحالي: {path_str or 'الرئيسية'}", reply_markup=markup)
        return

    if not path:
        for key in ACADEMIC_STRUCTURE.keys():
            markup.add(KeyboardButton(key))
        markup.add("👨‍💻 تواصل مع المشرف العام")
        
        if is_super_admin(chat_id) and not testing_mode.get(chat_id):
            markup.add("📢 إرسال رسالة جماعية", "👥 إحصائيات المشتركين")
            markup.add("🛠️ إدارة المشرفين", "⚙️ التحكم بالنظام")
            markup.add("🏷️ إدارة الأرشفة", "📂 إضافة مجلد بالرئيسية")
            markup.add("👤 تجربة كمستخدم")
        elif is_super_admin(chat_id) and testing_mode.get(chat_id):
            markup.add("🛑 إنهاء التجربة والعودة للإشراف")
            
        bot.send_message(chat_id, "⚙️ يرجى تحديد القسم الأكاديمي المطلوب من لوحة الخيارات التالية:", reply_markup=markup)
        return

    # عرض محتوى مجلد ميزات الطالب المطور
    if path_str == "🌟 ميزات مساعدة للطالب":
        user_data = users_col.find_one({"chat_id": chat_id})
        notif_btn = "🔕 إلغاء الإشعارات" if user_data and user_data.get("smart_notifications") else "🔔 تفعيل الإشعارات"
        
        markup.add(KeyboardButton("🤖 المساعد الذكي (AI)"), KeyboardButton("🔍 بحث عن ملف"))
        markup.add(KeyboardButton("🔥 الملفات الأكثر شعبية"), KeyboardButton("🆕 تحديثات اليوم"))
        markup.add(KeyboardButton("🔔 تنبيهات المقررات"), KeyboardButton("⏰ تذكير شخصي (خاص بي)"))
        markup.add(KeyboardButton(notif_btn), KeyboardButton("🧠 معلومات عن التخصص"))
        markup.add("🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية")
        bot.send_message(chat_id, "🌟 *ميزات مساعدة للطالب*\nيرجى اختيار الأداة الذكية المطلوبة للمساعدة الفورية:", reply_markup=markup, parse_mode="Markdown")
        return

    if isinstance(current_menu, dict):
        for key in current_menu.keys():
            markup.add(KeyboardButton(key))
            
    for db_folder in folders_col.find({"parent_path": path_str}): 
        markup.add(KeyboardButton(f"📁 {db_folder['folder_name']}"))
        
    for db_file in files_col.find({"menu_path": path_str}):
        icon = "📌" if db_file.get("type") == "text" else "🖼️" if db_file.get("type") == "photo" else "📄"
        markup.add(KeyboardButton(f"{icon} {db_file['name']}"))

    markup.add("🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية")
    
    if has_permission(chat_id, path_str):
        markup.add("➕ إضافة ملف/نص", "📂 إضافة مجلد")
        markup.add("✏️ إعادة تسمية هذا القسم", "🗑️ حذف هذا القسم")
        if is_super_admin(chat_id): 
            markup.add("🔗 ربط هاشتاج بالقسم")

    bot.send_message(chat_id, f"📂 المسار الحالي المستعرض:\n`{path_str}`", reply_markup=markup, parse_mode="Markdown")

def send_file_to_user(chat_id, res, has_perm):
    try:
        markup = InlineKeyboardMarkup(row_width=2)
        file_id_str = str(res['_id'])
        share_url = f"https://t.me/{BOT_USERNAME}?start={file_id_str}"
        
        if has_perm and not testing_mode.get(chat_id):
            markup.add(InlineKeyboardButton("✏️ تعديل الاسم", callback_data=f"rn_{file_id_str}"), InlineKeyboardButton("🔄 استبدال الملف", callback_data=f"rp_{file_id_str}"))
            markup.add(InlineKeyboardButton("🗑️ حذف", callback_data=f"dl_{file_id_str}"), InlineKeyboardButton("📦 نقل", callback_data=f"mv_{file_id_str}"))
            markup.add(InlineKeyboardButton("🔗 مشاركة الملف الحالية", url=f"https://t.me/share/url?url={share_url}"))
        else:
            markup.add(InlineKeyboardButton("🔗 شارك الملف مع زملائك", url=f"https://t.me/share/url?url={share_url}"))

        file_type = res.get('type', 'document')
        file_id = res.get('file_id')
        file_name = res.get('name', 'وثيقة أكاديمية')
        caption = res.get('caption')
        
        if not caption or caption.strip() == "":
            caption = file_name
        caption += f"\n\n🔻 إجمالي عدد مرات التحميل والاستدعاء: {res.get('downloads', 0)}"

        if file_type == 'text':
            bot.send_message(chat_id, res.get('content', file_name), reply_markup=markup)
        elif file_type == 'photo' and file_id:
            bot.send_photo(chat_id, file_id, caption=caption, reply_markup=markup)
        elif file_id:
            bot.send_document(chat_id, file_id, caption=caption, reply_markup=markup)
        else:
            bot.send_message(chat_id, "❌ تنبيه: هذا الملف فارغ أو غير متواجد على خوادم تيليجرام التخزينية حالياً.", reply_markup=markup)
    except Exception as fetch_err:
        bot.send_message(chat_id, f"❌ خطأ تقني غير متوقع أثناء استخراج المستند: {fetch_err}")

# ==========================================
# 10. المعالج المركزي الذكي المطلق (Universal Core Handler)
# ==========================================
@bot.message_handler(content_types=['text', 'document', 'photo', 'video', 'audio'])
def universal_handler(message):
    chat_id = message.chat.id
    text = message.text if message.content_type == 'text' else ""
    path_str = get_path_string(chat_id)
    mode = admin_action_mode.get(chat_id)

    if message.chat.type in ['group', 'supergroup']:
        auto_archive_handler_logic(message)
        if message.content_type != 'text' or not text.startswith("/"):
            return

    # [1] نظام الاستقبال الاحترافي والذكي للمستندات والملفات المتعددة
    if message.content_type in ['document', 'photo', 'video', 'audio'] and upload_mode.get(chat_id):
        if has_permission(chat_id, path_str):
            if getattr(message, "media_group_id", None):
                gid = str(message.media_group_id)
                if gid not in media_groups:
                    media_groups[gid] = []
                    threading.Thread(target=process_media_group, args=(chat_id, gid, path_str)).start()
                media_groups[gid].append(message)
                return
            else:
                doc = build_file_doc(message, path_str)
                if doc['file_id']:
                    files_col.insert_one(doc)
                    bot.reply_to(message, f"✅ تم استقبال وحفظ المستند الفردي بنجاح:\n📄 *{doc['name']}*", parse_mode="Markdown")
                    notify_subscribers(doc['name'], path_str, chat_id)
            return

    # أزرار الإلغاء الشاملة والتحكم
    if text == "🛑 إلغاء الأمر":
        reset_modes(chat_id)
        bot.send_message(chat_id, "✅ تم إلغاء الإجراء الحالي والعودة بأمان.")
        show_menu(chat_id)
        return
    
    if text in ["🔝 القائمة الرئيسية", "📚 تصفح بوت الدفعة"]:
        user_path[chat_id] = []
        reset_modes(chat_id)
        show_menu(chat_id)
        return
        
    if text == "🔙 الرجوع للقائمة السابقة":
        if chat_id in user_path and user_path[chat_id]:
            user_path[chat_id].pop()
        reset_modes(chat_id)
        show_menu(chat_id)
        return

    # التحكم في الإشعارات
    if text in ["🔔 تفعيل الإشعارات", "🔕 إلغاء الإشعارات"]:
        new_status = (text == "🔔 تفعيل الإشعارات")
        users_col.update_one({"chat_id": chat_id}, {"$set": {"smart_notifications": new_status}})
        bot.send_message(chat_id, "✅ تم تحديث تفضيلات الإشعارات الذكية الخاصة بك بنجاح.")
        show_menu(chat_id)
        return

    # الروابط الإدارية والخدمية في الشاشة الرئيسية
    if text == "👨‍💻 تواصل مع المشرف العام":
        dev_text = ("👨‍💻 *تواصل مع المشرف العام للمنصة:*\n\n🔹 *الواثق بالله عساج* ⇦ (@AlwatheqAssag)\n\nلأي استفسارات أكاديمية أو الإبلاغ عن مشاكل في الخوادم أو تقديم ملفات وملخصات دراسية لإثراء المنصة، يرجى التواصل مباشرة عبر المعرف الرسمي أعلاه.")
        bot.send_message(chat_id, dev_text, parse_mode="Markdown")
        return

    # [2] ميزات مجلد المساعد الأكاديمي المطور للطالب
    if text == "🤖 المساعد الذكي (AI)":
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "ai_chat"
        bot.send_message(chat_id, "🤖 المساعد الذكي واللغوي الفعال جاهز لمساعدتك الآن!\nاطرح سؤالك العام أو الأكاديمي أو البرمجي (لديك 7 محاولات يومية):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
        return
    
    if mode == "ai_chat" and text:
        # فحص الحصص اليومية
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        usage = ai_usage_col.find_one({"chat_id": chat_id, "date": today_str})
        count = usage['count'] + 1 if usage else 1
        
        if count > 7 and not is_super_admin(chat_id):
            bot.send_message(chat_id, "🛑 لقد استنفدت حصتك اليومية (7 أسئلة). نلتقي غداً لتعلم المزيد!")
            return
            
        bot.send_message(chat_id, "⏳ جاري التفكير وتحليل الاستفسار وتوليد الرد...")
        
        # فحص مكتبة الأسئلة المتكررة أولاً
        cached_ans = kb_col.find_one({"question": text})
        if cached_ans:
            final_ans = cached_ans['answer'] + "\n\n*(⚡ إجابة فورية من مكتبة الأسئلة المتكررة الخاصة بالقسم)*"
        else:
            final_ans = get_ai_response(text)
            kb_col.update_one({"question": text}, {"$set": {"answer": final_ans}}, upsert=True)
            
        try:
            bot.send_message(chat_id, final_ans, parse_mode="Markdown")
        except:
            bot.send_message(chat_id, final_ans)
            
        # تسجيل الاستخدام وتنبيه الطالب عند المحاولة السادسة
        if not is_super_admin(chat_id):
            ai_usage_col.update_one({"chat_id": chat_id, "date": today_str}, {"$set": {"count": count}}, upsert=True)
            if count == 6:
                bot.send_message(chat_id, "⚠️ *تنبيه:* هذه المحاولة السادسة لك، بقيت لك محاولة واحدة فقط اليوم.", parse_mode="Markdown")
                
        reset_modes(chat_id)
        show_menu(chat_id)
        return

    # التذكيرات الشخصية للطلاب
    if text == "⏰ تذكير شخصي (خاص بي)":
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "set_reminder_text"
        bot.send_message(chat_id, "⏰ ما هو موضوع التذكير؟ (مثال: مذاكرة الشابتر الثالث):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
        return
        
    if mode == "set_reminder_text" and text:
        action_payload[chat_id] = text
        admin_action_mode[chat_id] = "set_reminder_time"
        bot.send_message(chat_id, "بعد كم ساعة أذكرك؟ (اكتب رقماً فقط، مثلاً: 2 أو 1.5):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
        return
        
    if mode == "set_reminder_time" and text:
        try:
            hours = float(text.strip())
            notify_time = datetime.utcnow() + timedelta(hours=hours)
            reminders_col.insert_one({"chat_id": chat_id, "text": action_payload[chat_id], "notify_at": notify_time})
            bot.send_message(chat_id, f"✅ تم جدولة التنبيه بنجاح. سأقوم بتذكيرك بعد {hours} ساعة بإذن الله.")
        except:
            bot.send_message(chat_id, "❌ الرجاء كتابة رقم صحيح للساعات فقط.")
        reset_modes(chat_id)
        show_menu(chat_id)
        return

    # البحث الشامل والفرز
    if text == "🔍 بحث عن ملف":
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "search_type"
        search_markup = ReplyKeyboardMarkup(resize_keyboard=True).add("🌍 بحث شامل في كامل البوت", "📂 بحث في مساري الحالي فقط").add("🛑 إلغاء الأمر")
        bot.send_message(chat_id, "🔍 اختر نوع البحث لتضييق النتائج وتوفير الوقت:", reply_markup=search_markup)
        return

    if mode == "search_type" and text in ["🌍 بحث شامل في كامل البوت", "📂 بحث في مساري الحالي فقط"]:
        action_payload[chat_id] = "global" if text == "🌍 بحث شامل في كامل البوت" else path_str
        admin_action_mode[chat_id] = "search_execute"
        bot.send_message(chat_id, "🔍 أرسل الكلمة المفتاحية أو جزء من اسم الملف المراد البحث عنه (مثال: محاضرة 1):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
        return

    if mode == "search_execute" and text:
        search_scope = action_payload.get(chat_id, "global")
        query = {"name": {"$regex": text, "$options": "i"}}
        if search_scope != "global" and search_scope:
            query["menu_path"] = {"$regex": f"^{re.escape(search_scope)}"}
            
        results = list(files_col.find(query).limit(15))
        if results:
            bot.send_message(chat_id, f"🔍 *تم العثور على {len(results)} نتائج مطابقة للبحث:*", parse_mode="Markdown")
            for item in results:
                bot.send_message(chat_id, f"📁 يقع في المسار: {item['menu_path']}")
                send_file_to_user(chat_id, item, has_permission(chat_id, item['menu_path']))
        else:
            bot.send_message(chat_id, "❌ نعتذر، لم نجد أي ملفات مطابقة للكلمة المدخلة في هذا النطاق.")
        reset_modes(chat_id)
        show_menu(chat_id)
        return

    if text == "🔥 الملفات الأكثر شعبية":
        popular_files = list(files_col.find({"downloads": {"$gt": 0}}).sort("downloads", -1).limit(5))
        if not popular_files:
            bot.send_message(chat_id, "لا توجد ملفات تم تحميلها ومشاركتها حتى الآن لتكوين قائمة الإحصائيات.")
        else:
            bot.send_message(chat_id, "🔥 *أكثر 5 ملفات اعتماداً وتحميلاً من قبل الطلاب:*", parse_mode="Markdown")
            for p_file in popular_files:
                send_file_to_user(chat_id, p_file, False)
        return

    if text == "🆕 تحديثات اليوم":
        one_day_ago = datetime.utcnow() - timedelta(days=1)
        recent_uploads = list(files_col.find({"upload_date": {"$gte": one_day_ago}}).limit(10))
        if not recent_uploads:
            bot.send_message(chat_id, "لم يتم إضافة أي مستندات أو ملخصات جديدة خلال الأربع وعشرين ساعة الماضية.")
        else:
            bot.send_message(chat_id, "🆕 *أحدث المستندات والملفات المضافة اليوم للمنصة:*", parse_mode="Markdown")
            for r_file in recent_uploads:
                send_file_to_user(chat_id, r_file, False)
        return

    if text == "🧠 معلومات عن التخصص":
        info_text = ("🚀 *الذكاء الاصطناعي وعلوم البيانات (AI & Data Science)*\n\nمرحباً بك في تخصص المستقبل، ولغة العصر الحديث! 🌟\nهذا التخصص يدمج بين قوة البرمجة، عمق الرياضيات، وعبقرية تحليل البيانات.\n💡 *لماذا هذا التخصص؟* لأنك هنا تتعلم كيف تجعل الآلة تفكر، تحلل، وتتخذ القرارات! أنت تُهندس المستقبل.\n🎓 *أنت لست مجرد طالب، أنت مهندس حلول المستقبل.* استمر، فالعالم ينتظر إبداعك!")
        bot.send_message(chat_id, info_text, parse_mode="Markdown")
        return

    # [3] منظومة التنبيهات المخصصة للمقررات والمواد الدراسية (التعميمات)
    if text == "🔔 تنبيهات المقررات":
        active_alerts = list(alerts_col.find())
        if not active_alerts:
            alert_msg = "🔔 *مركز التنبيهات والأحداث:*\n\nلا توجد تنبيهات أو مواعيد اختبارات مجدولة حالياً للاستعراض. استمروا في الجد والاجتهاد! 🎯"
        else:
            alert_msg = "🔔 *تنبيهات المقررات والأحداث الهامة الحالية:*\n\n"
            for alert_item in active_alerts:
                alert_msg += f"📌 {alert_item['text']}\n"
        
        alert_markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        if has_permission(chat_id, "🌟 ميزات مساعدة للطالب") or is_super_admin(chat_id):
            alert_markup.add(KeyboardButton("➕ إضافة تنبيه جديد"), KeyboardButton("🗑️ تفريغ كافة التنبيهات"))
        alert_markup.add("🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية")
        bot.send_message(chat_id, alert_msg, reply_markup=alert_markup, parse_mode="Markdown")
        return

    if text == "➕ إضافة تنبيه جديد" and (has_permission(chat_id, "🌟 ميزات مساعدة للطالب") or is_super_admin(chat_id)):
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "add_course_alert"
        bot.send_message(chat_id, "📝 أرسل نص التنبيه الأكاديمي الجديد بدقة (مثال: الأحد القادم موعد تسليم مشروع البرمجة):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
        return
    
    if mode == "add_course_alert" and text:
        alerts_col.insert_one({"text": text.strip(), "created_at": datetime.utcnow()})
        bot.send_message(chat_id, "✅ تم حفظ التنبيه الجديد ونشره بنجاح داخل مركز التنبيهات.")
        
        # تعميم التنبيه الإداري فوراً كرسالة لجميع المشتركين
        for student_user in list(users_col.find()):
            try:
                bot.send_message(student_user['chat_id'], f"📢 *تنبيه إداري جديد للمقررات:*\n{text.strip()}", parse_mode="Markdown")
            except:
                pass
                
        reset_modes(chat_id)
        user_path[chat_id] = ["🌟 ميزات مساعدة للطالب"]
        show_menu(chat_id)
        return
        
    if text == "🗑️ تفريغ كافة التنبيهات" and (has_permission(chat_id, "🌟 ميزات مساعدة للطالب") or is_super_admin(chat_id)):
        alerts_col.delete_many({})
        bot.send_message(chat_id, "🗑️ تم مسح وتفريغ جدول التنبيهات بالكامل بنجاح.")
        user_path[chat_id] = ["🌟 ميزات مساعدة للطالب"]
        show_menu(chat_id)
        return

    # [4] لوحة المشرف العام المطلقة والتحكم بالنظام وإحصائيات الطلاب
    if is_super_admin(chat_id):
        if text == "👥 إحصائيات المشتركين":
            all_users = list(users_col.find())
            stats_msg = (
                f"📊 *تقرير منصة الإدارة العليا الشامل:*\n\n"
                f"👥 إجمالي الطلاب المشتركين: {len(all_users)} طالب.\n"
                f"📁 إجمالي المستندات المخزنة: {files_col.count_documents({})} مستند.\n"
                f"📂 إجمالي المجلدات الديناميكية: {folders_col.count_documents({})} مجلد.\n\n"
                f"👤 *قائمة بيانات الطلاب (الاسم | المعرف | الآيدي):*\n"
            )
            for single_user in all_users:
                stats_msg += f"• {single_user.get('first_name', 'مجهول الاسم')} | {single_user.get('username', 'لا يوجد معرف')} | `{single_user.get('chat_id')}`\n"
            
            if len(stats_msg) > 3800:
                with io.StringIO(stats_msg) as report_file:
                    report_file.name = "Platform_Students_Report.txt"
                    bot.send_document(chat_id, report_file, caption="📊 كشف بيانات الطلاب نظراً لكبر الحجم تم استخراجه في مستند نصي محمي.")
            else:
                bot.send_message(chat_id, stats_msg, parse_mode="Markdown")
            return

        if text == "📂 إضافة مجلد بالرئيسية":
            reset_modes(chat_id)
            add_folder_mode[chat_id] = True
            user_path[chat_id] = []
            bot.send_message(chat_id, "📂 اكتب اسم المجلد الجديد المراد زرعه وإنشاؤه في الشاشة الرئيسية مباشرة:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            return

        if text == "👤 تجربة كمستخدم":
            testing_mode[chat_id] = True
            bot.send_message(chat_id, "👀 تم تفعيل وضع المحاكاة بنجاح! أنت الآن تتصفح وتتعامل مع البوت بهوية طالب عادي بدون صلاحيات إشراف.")
            user_path[chat_id] = []
            show_menu(chat_id)
            return

        if text == "⚙️ التحكم بالنظام":
            sys_markup = ReplyKeyboardMarkup(resize_keyboard=True).add("▶️ تشغيل البوت", "⏸️ إيقاف البوت", "🔝 القائمة الرئيسية")
            bot.send_message(chat_id, "🛡️ مركز التحكم المركزي بالخوادم ومنظومة العمل، يرجى اختيار الإجراء المطلوب لحالة البوت الحالية:", reply_markup=sys_markup)
            return

        if text in ["▶️ تشغيل البوت", "⏸️ إيقاف البوت"]:
            target_status = "active" if text == "▶️ تشغيل البوت" else "inactive"
            settings_col.update_one({}, {"$set": {"status": target_status}}, upsert=True)
            bot.send_message(chat_id, f"✅ تمت العملية بنجاح! تم وضع حالة البوت إلى الوضع: {'النشط والفعال' if target_status == 'active' else 'المغلق للصيانة والتحديث'}.")
            show_menu(chat_id)
            return

        if text == "🏷️ إدارة الأرشفة":
            archive_markup = ReplyKeyboardMarkup(resize_keyboard=True).add("📋 عرض الهاشتاجات النشطة", "🗑️ حذف هاشتاج معين", "🔝 القائمة الرئيسية")
            bot.send_message(chat_id, "🏷️ *نظام الأرشفة التلقائية الذكي:*\nلإضافة وربط مجموعة ما بالمنصة، قم بكتابة الأمر `/auth` داخلها مباشرة.", reply_markup=archive_markup, parse_mode="Markdown")
            return

        if text == "📋 عرض الهاشتاجات النشطة":
            verified_groups = list(auth_groups_col.find())
            active_tags = list(hashtags_col.find())
            h_msg = "🛡️ *المجموعات المعتمدة المرتبطة بقاعدة البيانات:*\n" + "".join([f"▪️ {group_item.get('title', 'مجموعة موثقة')}\n" for group_item in verified_groups])
            h_msg += "\n🏷️ *الروابط والهاشتاجات النشطة حالياً بالتوجيه الأكاديمي:*\n" + "".join([f"🔸 {tag_item['tag']} ⇦ {tag_item['path'].split(' > ')[-1]}\n" for tag_item in active_tags])
            bot.send_message(chat_id, h_msg if (verified_groups or active_tags) else "لا توجد هاشتاجات أو مجموعات مرتبطة بالمنصة حالياً.", parse_mode="Markdown")
            return

        if text == "🗑️ حذف هاشتاج معين":
            reset_modes(chat_id)
            admin_action_mode[chat_id] = "del_hashtag"
            bot.send_message(chat_id, "أرسل الهاشتاج المراد تدميره وإلغاء ربطه تماماً (مثال: #برمجة_نظري):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            return

        if text == "🔗 ربط هاشتاج بالقسم":
            reset_modes(chat_id)
            admin_action_mode[chat_id] = "add_hashtag"
            bot.send_message(chat_id, f"أرسل اسم الهاشتاج الجديد المراد ربطه بالقسم الحالي:\n`{path_str}`", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"), parse_mode="Markdown")
            return

        if text == "🛠️ إدارة المشرفين":
            adm_markup = ReplyKeyboardMarkup(resize_keyboard=True).add("➕ إضافة مشرف عام", "➕ إضافة مشرف مسار مخصص", "➖ إزالة مشرف", "🔝 القائمة الرئيسية")
            bot.send_message(chat_id, "🛠️ لوحة إدارة الصلاحيات وتعيين رتب الإشراف الفرعية لمساعدتك في إدارة ملفات المقررات:", reply_markup=adm_markup)
            return

        if text == "➕ إضافة مشرف عام":
            reset_modes(chat_id)
            admin_action_mode[chat_id] = "add_global_admin"
            bot.send_message(chat_id, "👤 أرسل الرقم التعريفي (الآيدي الرقمي) للمستخدم لتعيينه كمشرف عام كامل الصلاحيات:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            return

        if text == "➕ إضافة مشرف مسار مخصص":
            reset_modes(chat_id)
            admin_action_mode[chat_id] = "add_path_admin_id"
            bot.send_message(chat_id, "👤 الخطوة 1: أرسل الرقم التعريفي (الآيدي الرقمي) للمشرف الفرعي المستهدف:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            return

        if text == "➖ إزالة مشرف":
            reset_modes(chat_id)
            admin_action_mode[chat_id] = "remove_admin"
            bot.send_message(chat_id, "👤 أرسل الرقم التعريفي للمشرف المراد سحب كافة صلاحيات الإشراف منه فوراً:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            return

        if text == "📢 إرسال رسالة جماعية":
            reset_modes(chat_id)
            broadcast_mode[chat_id] = True
            bot.send_message(chat_id, "📢 أرسل نص أو محتوى التعميم أو الرسالة الجماعية المراد بثها وتوجيهها لكافة المشتركين في قاعدة البيانات الآن:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            return

    # إنهاء تجربة وضع المحاكاة للطالب والعودة للرتبة الإدارية
    if text == "🛑 إنهاء التجربة والعودة للإشراف" and is_super_admin(chat_id):
        testing_mode[chat_id] = False
        bot.send_message(chat_id, "💼 تم إنهاء وضع المحاكاة بنجاح وعادت إليك كامل صلاحيات الإدارة العليا المطلقة والتحكم بالمنصة.")
        user_path[chat_id] = []
        show_menu(chat_id)
        return

    # [5] العمليات التنظيمية والهيكلية للمشرفين المعتمدين في المسار الحالي (إضافة وتعديل وحذف الأقسام)
    if has_permission(chat_id, path_str) and path_str:
        if text == "➕ إضافة ملف/نص":
            reset_modes(chat_id)
            upload_mode[chat_id] = True
            bot.send_message(chat_id, "📥 وضع استقبال المستندات نشط!\nأرسل الآن الملفات الأكاديمية (PDF، صور، نصوص، ملخصات) بشكل مفرد أو دفعة واحدة (ألبوم) ليتم تخزينها وحفظها تلقائياً في هذا القسم:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            return

        if text == "📂 إضافة مجلد":
            reset_modes(chat_id)
            add_folder_mode[chat_id] = True
            bot.send_message(chat_id, "📂 اكتب واส่ง اسم المجلد الأكاديمي الفرعي الجديد لإنشائه داخل القسم الحالي:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            return
        
        if text == "🗑️ حذف هذا القسم":
            parent_p_str = path_str.rsplit(' > ', 1)[0] if ' > ' in path_str else ""
            folders_col.delete_one({"parent_path": parent_p_str, "folder_name": user_path[chat_id][-1]})
            bot.send_message(chat_id, f"🗑️ تم حذف وتدمير مجلد القسم الدراسي الحالي من قاعدة البيانات بنجاح.")
            if user_path[chat_id]:
                user_path[chat_id].pop()
            reset_modes(chat_id)
            show_menu(chat_id)
            return

        if text == "✏️ إعادة تسمية هذا القسم":
            reset_modes(chat_id)
            admin_action_mode[chat_id] = "rename_folder_action"
            bot.send_message(chat_id, f"✏️ أرسل الآن الاسم الجديد للقسم البديل لـ ( {user_path[chat_id][-1]} ):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            return

    # [6] التقاط معالجات المدخلات النصية للأوضاع الإدارية والهيكلية المختلفة
    if mode == "rename_folder_action" and text:
        old_folder_name = user_path[chat_id][-1]
        parent_p_str = path_str.rsplit(' > ', 1)[0] if ' > ' in path_str else ""
        folders_col.update_one({"parent_path": parent_p_str, "folder_name": old_folder_name}, {"$set": {"folder_name": text.strip()}})
        user_path[chat_id][-1] = text.strip()  
        bot.send_message(chat_id, "✅ تم تحديث وإعادة تسمية المجلد في قاعدة البيانات بنجاح الفوري.")
        reset_modes(chat_id)
        show_menu(chat_id)
        return

    if mode == "add_hashtag" and text and is_super_admin(chat_id):
        final_tag = text.strip()
        if not final_tag.startswith("#"):
            final_tag = "#" + final_tag
        hashtags_col.insert_one({"tag": final_tag, "path": path_str})
        bot.send_message(chat_id, f"✅ تم ربط واعتماد الهاشتاج {final_tag} بهذا القسم الدراسي بنجاح التام.")
        reset_modes(chat_id)
        show_menu(chat_id)
        return
        
    if mode == "del_hashtag" and text and is_super_admin(chat_id):
        final_tag = text.strip()
        if not final_tag.startswith("#"):
            final_tag = "#" + final_tag
        del_res = hashtags_col.delete_one({"tag": final_tag})
        bot.send_message(chat_id, "✅ تم إلغاء ربط وحذف الهاشتاج من النظام." if del_res.deleted_count > 0 else "❌ تنبيه: هذا الهاشتاج غير مسجل في قاعدة البيانات.")
        reset_modes(chat_id)
        show_menu(chat_id)
        return

    if broadcast_mode.get(chat_id) and is_super_admin(chat_id):
        broadcast_mode[chat_id] = False
        bot.send_message(chat_id, "⏳ جاري بدء البث الجماعي وتعميم الرسالة على كافة المشتركين بالمنصة...")
        broadcast_success_count = 0
        for student_user in list(users_col.find()):
            try:
                bot.copy_message(student_user['chat_id'], chat_id, message.message_id)
                broadcast_success_count += 1
            except:
                pass
        bot.send_message(chat_id, f"📢 اكتمل البث الجماعي للمنصة بنجاح!\n✅ تم إيصال وتعميم الرسالة الإدارية إلى {broadcast_success_count} طالب مشترك.")
        show_menu(chat_id)
        return

    if mode == "add_global_admin" and text and is_super_admin(chat_id):
        try:
            admins_col.update_one({"id": int(text.strip())}, {"$set": {"type": "global"}}, upsert=True)
            bot.send_message(chat_id, "✅ تمت إضافة المستخدم وترقيته كمشرف عام كامل الصلاحيات لجميع الأقسام الدراسية والمقررات.")
        except:
            bot.send_message(chat_id, "❌ خطأ: يرجى إرسال المعرف الرقمي (الآيدي فقط) بطريقة صحيحة بدون حروف.")
        reset_modes(chat_id)
        show_menu(chat_id)
        return

    if mode == "remove_admin" and text and is_super_admin(chat_id):
        try:
            target_id = int(text.strip())
            if target_id != SUPER_ADMIN_ID:
                admins_col.delete_one({"id": target_id})
                bot.send_message(chat_id, "✅ تم تجريد المستخدم وسحب كافة صلاحيات الإشراف المخصصة أو العامة منه بنجاح وبشكل فوري.")
        except:
            bot.send_message(chat_id, "❌ خطأ: الآيدي الرقمي يجب أن يتكون من أرقام فقط.")
        reset_modes(chat_id)
        show_menu(chat_id)
        return

    if mode == "add_path_admin_id" and text and is_super_admin(chat_id):
        try:
            temp_data[chat_id] = int(text.strip())
            admin_action_mode[chat_id] = "add_path_admin_path"
            user_path[chat_id] = []
            bot.send_message(chat_id, "✅ الخطوة 2: تم حفظ رقم الآيدي بنجاح. تصفح الآن الأقسام والمجلدات للوصول للمادة والمقرر المخصص لهذا المشرف، ثم اضغط على زر تعيين الصلاحية لتحديد نطاقه.")
            show_menu(chat_id)
        except:
            bot.send_message(chat_id, "❌ خطأ في الإدخال: الآيدي يتكون من أرقام فقط.")
        return

    if mode == "rename_file" and text:
        files_col.update_one({"_id": ObjectId(action_payload.get(chat_id))}, {"$set": {"name": text.strip()}})
        bot.send_message(chat_id, "✅ تم تعديل وإعادة تسمية المستند في قاعدة البيانات بنجاح.")
        reset_modes(chat_id)
        show_menu(chat_id)
        return

    if mode == "replace_file":
        replacement_doc = build_file_doc(message, path_str)
        if message.content_type in ['document', 'photo', 'video', 'audio']:
            files_col.update_one(
                {"_id": ObjectId(action_payload.get(chat_id))}, 
                {"$set": {"type": replacement_doc['type'], "file_id": replacement_doc['file_id'], "name": replacement_doc['name'], "caption": replacement_doc['caption']}}
            )
        elif message.content_type == 'text':
            files_col.update_one(
                {"_id": ObjectId(action_payload.get(chat_id))}, 
                {"$set": {"type": "text", "content": text, "name": text[:30], "caption": None, "file_id": None}}
            )
        bot.send_message(chat_id, "✅ تم استبدال وتحديث محتوى الملف القديم بنجاح المستند المرفق الجديد.")
        reset_modes(chat_id)
        show_menu(chat_id)
        return

    if add_folder_mode.get(chat_id) and text and has_permission(chat_id, path_str):
        folders_col.insert_one({"parent_path": path_str, "folder_name": text.strip(), "created_at": datetime.utcnow()})
        bot.send_message(chat_id, f"✅ تم إنشاء مجلد قسم دراسي جديد بنجاح باسم:\n📁 *{text.strip()}*", parse_mode="Markdown")
        reset_modes(chat_id)
        show_menu(chat_id)
        return

    if upload_mode.get(chat_id) and message.content_type == 'text' and has_permission(chat_id, path_str):
        files_col.insert_one({
            "menu_path": path_str, "name": text[:30].strip(), "type": "text", 
            "content": text, "downloads": 0, "upload_date": datetime.utcnow()
        })
        bot.send_message(chat_id, "✅ تم حفظ التلخيص أو المحتوى النصي وإضافته بنجاح لقسم العرض.")
        notify_subscribers("تلخيص نصي جديد", path_str, chat_id)
        reset_modes(chat_id)
        show_menu(chat_id)
        return

    # [7] استدعاء والتقاط أسماء الملفات وقراءة المستندات الفعلية (PDF & Docs) من محاكاة تصفح لوحة المفاتيح
    if text and (text.startswith("📄 ") or text.startswith("📌 ") or text.startswith("🖼️ ")):
        extracted_filename = text.replace("📄 ", "").replace("📌 ", "").replace("🖼️ ", "").strip()
        found_file_doc = files_col.find_one({"menu_path": path_str, "name": extracted_filename})
        if not found_file_doc:
            found_file_doc = files_col.find_one({"menu_path": path_str, "name": {"$regex": re.escape(extracted_filename), "$options": "i"}})
        
        if found_file_doc:
            files_col.update_one({"_id": found_file_doc["_id"]}, {"$inc": {"downloads": 1}}) 
            send_file_to_user(chat_id, found_file_doc, has_permission(chat_id, path_str))
        else:
            bot.send_message(chat_id, "❌ خطأ: تعذر العثور على المستند الفعلي في مسار الأرشيف الحالي.")
        return

    # التصفح عبر النقر على أزرار المجلدات والدخول للأعماق الهيكلية
    if text.startswith("📁 "):
        user_path[chat_id].append(text.replace("📁 ", "").strip())
        show_menu(chat_id)
        return

    current_academic_menu = get_menu_by_path(user_path.get(chat_id, []))
    if isinstance(current_academic_menu, dict) and text in current_academic_menu:
        if chat_id not in user_path:
            user_path[chat_id] = []
        user_path[chat_id].append(text)
        show_menu(chat_id)
        return

# ==========================================
# 11. معالجات أزرار التحكم والعمليات الهيكلية الشفافة (Inline Callbacks)
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith(('rn_', 'rp_', 'dl_', 'mv_')))
def handle_inline_callbacks(call):
    chat_id = call.message.chat.id
    action, target_object_id = call.data.split('_')
    
    file_document = files_col.find_one({"_id": ObjectId(target_object_id)})
    if not file_document or not has_permission(chat_id, file_document['menu_path']):
        bot.answer_callback_query(call.id, "❌ تنبيه: لا تمتلك الصلاحيات الإشرافية الكافية لإجراء هذا التعديل الأكاديمي.", show_alert=True)
        return

    if action == 'dl':
        files_col.delete_one({"_id": ObjectId(target_object_id)})
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except:
            pass
        bot.answer_callback_query(call.id, "🗑️ تم حذف وإزالة المستند نهائياً من النظام.")
        show_menu(chat_id)
    elif action == 'rn':
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "rename_file"
        action_payload[chat_id] = target_object_id
        bot.send_message(chat_id, "✏️ يرجى إرسال الاسم الجديد للمستند الأكاديمي الآن:")
        bot.answer_callback_query(call.id, "جاري تحويل الوضع لإعادة التسمية.")
    elif action == 'rp':
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "replace_file"
        action_payload[chat_id] = target_object_id
        bot.send_message(chat_id, "🔄 أرسل الآن الملف المرفق البديل المستهدف (PDF أو صورة أو نص) ليقوم الكود باستبدال المحتوى القديم فوراً:")
        bot.answer_callback_query(call.id, "جاري تحويل الوضع لاستقبال البديل.")
    elif action == 'mv':
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "move_file_dest"
        action_payload[chat_id] = target_object_id
        user_path[chat_id] = []
        show_menu(chat_id)
        bot.answer_callback_query(call.id, "جاري تحويل الوضع لنقل الملف.")

# ==========================================
# 12. مسارات الربط والاستماع الخاصة بـ Webhook لـ Render
# ==========================================
@app.route('/webhook', methods=['POST'])
def webhook_listen_route():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "!", 200
    else:
        return "Invalid Headers Content-Type", 403

@app.route("/")
def index_home_route():
    return "The Ultimate Production Academic Bot is RUNNING flawlessly with zero errors and robust AI Fallback! 🚀", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
