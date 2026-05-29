import telebot
from pymongo import MongoClient
from flask import Flask, request
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import sys
import io
import threading
import time
from datetime import datetime, timedelta
from bson.objectid import ObjectId
import re

# حل مشكلة الترميز لاستقبال النصوص العربية
if sys.version_info >= (3, 0):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_TOKEN = '7524289470:AAGkeX96s1s6saxGP3uy14MN9it19nKn10A'
SUPER_ADMIN_ID = 6842543527  # الواثق (المدير الأعلى)

MONGO_URI = "mongodb+srv://Alwatheq:alwatheq73@cluster0.ft0mdkt.mongodb.net/?appName=Cluster0"

try:
    client = MongoClient(MONGO_URI)
    db = client['academic_bot_db']
    files_col = db['uploaded_files']
    folders_col = db['dynamic_folders']
    users_col = db['bot_users']
    admins_col = db['admins_list']
    settings_col = db['bot_settings']
    alerts_col = db['scheduled_alerts']
    reports_col = db['error_reports'] # التبليغات
    requests_col = db['file_requests'] # الطلبات
    print("Connected to MongoDB Atlas successfully! 🎉")
except Exception as e:
    print(f"MongoDB connection error: {e}")

if admins_col.count_documents({}) == 0:
    admins_col.insert_one({"id": SUPER_ADMIN_ID, "type": "super", "allowed_paths": []})

if settings_col.count_documents({}) == 0:
    settings_col.insert_one({"status": "active"})

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)
bot_info = bot.get_me()
BOT_USERNAME = bot_info.username

# الهيكل الأكاديمي
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
    "🌳 مستوى رابع": {"📅 ترم أول": {}, "📅 ترم ثاني": {}}
}

# قاموس الهاشتاجات للأرشفة التلقائية من المجموعات
HASHTAG_MAP = {
    "#ثقافة_محاضرات": "🌱 مستوى أول > 📅 ترم ثاني > 🕋 الثقافة الإسلامية > 📁 محاضرات وملخصات",
    "#بيانات_عملي": "🌱 مستوى أول > 📅 ترم ثاني > 📊 مقدمة في علوم البيانات > ⚙️ محاضرات العملي",
    "#برمجة_نظري": "🌱 مستوى أول > 📅 ترم ثاني > 💻 برمجة حاسوب > 📂 محاضرات نظري",
    # يمكنك إضافة المزيد هنا مستقبلاً...
}

# المتغيرات المؤقتة
user_path, upload_mode, add_folder_mode, broadcast_mode = {}, {}, {}, {}
testing_mode, admin_action_mode, action_payload = {}, {}, {}
temp_data = {}

# --- دوال التحقق من الصلاحيات الذكية (RBAC) ---
def is_super_admin(chat_id):
    return chat_id == SUPER_ADMIN_ID

def has_permission(chat_id, current_path_str):
    if is_super_admin(chat_id) or testing_mode.get(chat_id):
        return True
    admin = admins_col.find_one({"id": chat_id})
    if not admin: return False
    if admin.get("type") == "global": return True
    # التحقق مما إذا كان مسار المشرف يطابق المسار الحالي
    allowed_paths = admin.get("allowed_paths", [])
    for p in allowed_paths:
        if current_path_str.startswith(p):
            return True
    return False

def is_bot_active():
    setting = settings_col.find_one()
    return setting.get("status") == "active" if setting else True

def get_menu_by_path(path):
    menu = ACADEMIC_STRUCTURE
    for p in path:
        if isinstance(menu, dict) and p in menu: menu = menu[p]
        else: return None
    return menu

def get_path_string(chat_id):
    return " > ".join(user_path.get(chat_id, []))

def reset_modes(chat_id):
    upload_mode[chat_id] = False
    add_folder_mode[chat_id] = False
    broadcast_mode[chat_id] = False
    admin_action_mode[chat_id] = None
    action_payload.pop(chat_id, None)

# --- محرك المهام الخلفية (المنبهات وحالة الطوارئ) ---
def background_tasks_thread():
    while True:
        try:
            now_yemen = datetime.utcnow() + timedelta(hours=3)
            current_time_str = now_yemen.strftime("%Y-%m-%d %H:%M")
            due_alerts = list(alerts_col.find({"status": "pending", "send_time": current_time_str}))
            
            for alert in due_alerts:
                users = list(users_col.find())
                success = 0
                for u in users:
                    try:
                        bot.send_message(u['chat_id'], f"🔔 *تنبيه أكاديمي:*\n\n{alert['message']}", parse_mode="Markdown")
                        success += 1
                    except: pass
                alerts_col.update_one({"_id": alert['_id']}, {"$set": {"status": "sent", "reached": success}})
        except Exception as e:
            pass
        time.sleep(45)

threading.Thread(target=background_tasks_thread, daemon=True).start()

# التحقق من وجود اختبار خلال 24 ساعة (وضع الطوارئ)
def get_emergency_exam():
    now = datetime.utcnow() + timedelta(hours=3)
    upcoming_alerts = alerts_col.find({"status": "pending"})
    for alert in upcoming_alerts:
        if "اختبار" in alert['message'] or "امتحان" in alert['message']:
            alert_time = datetime.strptime(alert['send_time'], "%Y-%m-%d %H:%M")
            if timedelta(hours=0) <= (alert_time - now) <= timedelta(hours=24):
                return alert['message']
    return None

# --- الأرشفة التلقائية للمجموعات والقنوات ---
@bot.message_handler(content_types=['document', 'photo'], func=lambda m: m.chat.type in ['group', 'supergroup', 'channel'])
def auto_archive_handler(message):
    caption = message.caption or ""
    for tag, path in HASHTAG_MAP.items():
        if tag in caption:
            name = caption.replace(tag, "").strip() or ("مستند أرشيف" if message.content_type == 'document' else "صورة أرشيف")
            if message.content_type == 'document':
                files_col.insert_one({"menu_path": path, "name": name, "type": "document", "file_id": message.document.file_id, "caption": caption})
            elif message.content_type == 'photo':
                files_col.insert_one({"menu_path": path, "name": name, "type": "photo", "file_id": message.photo[-1].file_id, "caption": caption})
            
            try:
                bot.reply_to(message, f"✅ تم الأرشفة تلقائياً في: {path.split('>')[-1]}")
            except: pass
            break

# --- القوائم والتنقل ---
@bot.message_handler(func=lambda m: not is_bot_active() and m.chat.id != SUPER_ADMIN_ID)
def system_offline(message):
    bot.send_message(message.chat.id, "⛔ المنصة مغلقة حالياً للصيانة بقرار من الإدارة العليا.")

def show_menu(chat_id):
    path = user_path.get(chat_id, [])
    current_menu = get_menu_by_path(path)
    path_str = get_path_string(chat_id)
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    if not path:
        # الشاشة الرئيسية للمنصة
        emergency = get_emergency_exam()
        if emergency:
            markup.add(KeyboardButton("🚨 طوارئ الاختبارات (مراجعة سريعة)"))

        for key in ACADEMIC_STRUCTURE.keys():
            markup.add(KeyboardButton(key))
            
        markup.add("🧠 معلومات تخصص الذكاء الاصطناعي", "🔍 بحث عن ملف")
        markup.add("👨‍💻 أدوات المبرمج", "🆘 طلب ملف مفقود")
        
        if is_super_admin(chat_id) and not testing_mode.get(chat_id):
            markup.add("📊 تقرير الإنجاز الأكاديمي", "📢 رسالة جماعية")
            markup.add("⏰ التنبيهات المجدولة", "🛠️ إدارة المشرفين")
            markup.add("⚠️ التبليغات والطلبات", "⚙️ زر الأمان (إغلاق البوت)")
            
        bot.send_message(chat_id, "مرحباً بك في المنصة الأكاديمية (الدفعة الثانية) 🎓\nاختر من القائمة:", reply_markup=markup)
        return

    # داخل الأقسام
    if isinstance(current_menu, dict):
        for key in current_menu.keys():
            markup.add(KeyboardButton(key))
            
    dynamic_folders = list(folders_col.find({"parent_path": path_str}))
    for df in dynamic_folders: markup.add(KeyboardButton(f"📁 {df['folder_name']}"))

    db_files = list(files_col.find({"menu_path": path_str}))
    for f in db_files:
        icon = "📌" if f.get("type") == "text" else "🖼️" if f.get("type") == "photo" else "📄"
        markup.add(KeyboardButton(f"{icon} {f['name']}"))

    markup.add("🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية")
    
    if testing_mode.get(chat_id):
        markup.add("🛑 إنهاء التجربة")
    elif has_permission(chat_id, path_str):
        markup.add("👤 تجربة كمستخدم", "➕ إضافة ملف/نص", "📂 إضافة مجلد", "🗑️ تفريغ القسم")

    bot.send_message(chat_id, f"📂 القسم: {path_str}", reply_markup=markup)

def send_file_to_user(chat_id, res, has_perm):
    markup = InlineKeyboardMarkup(row_width=2)
    file_id_str = str(res['_id'])
    share_url = f"https://t.me/{BOT_USERNAME}?start={file_id_str}"
    
    if has_perm and not testing_mode.get(chat_id):
        markup.add(InlineKeyboardButton("✏️ تعديل الاسم", callback_data=f"rn_{file_id_str}"), InlineKeyboardButton("🔄 استبدال", callback_data=f"rp_{file_id_str}"))
        markup.add(InlineKeyboardButton("🗑️ حذف", callback_data=f"dl_{file_id_str}"), InlineKeyboardButton("🔗 رابط مشاركة", url=f"https://t.me/share/url?url={share_url}"))
    else:
        markup.add(InlineKeyboardButton("🔗 شارك الملف", url=f"https://t.me/share/url?url={share_url}"))
        markup.add(InlineKeyboardButton("⚠️ أبلغ عن خطأ في الملف", callback_data=f"err_{file_id_str}"))

    if res['type'] == 'text': bot.send_message(chat_id, res['content'], reply_markup=markup)
    elif res['type'] == 'photo': bot.send_photo(chat_id, res['file_id'], caption=res.get('caption', res['name']), reply_markup=markup)
    else: bot.send_document(chat_id, res['file_id'], caption=res.get('caption', res['name']), reply_markup=markup)

# --- الأوامر الأساسية ---
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    name = message.from_user.first_name
    
    parts = message.text.split()
    if len(parts) > 1:
        try:
            res = files_col.find_one({"_id": ObjectId(parts[1])})
            if res:
                bot.send_message(chat_id, "📥 جاري إحضار الملف...")
                send_file_to_user(chat_id, res, has_permission(chat_id, res['menu_path']))
                return
        except: pass

    users_col.update_one({"chat_id": chat_id}, {"$set": {"first_name": name, "username": f"@{message.from_user.username}"}}, upsert=True)
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📚 تصفح بوت الدفعة")
    if is_super_admin(chat_id): markup.add("⚙️ لوحة الإدارة")
        
    welcome_text = (f"أهلاً بك يا {name} في منصة الذكاء الاصطناعي وعلوم البيانات 🎓\n\n"
                    f"هذه المنصة تتيح لك الوصول للمحاضرات، تتبع التنبيهات، البحث المتقدم، واستخدام أدوات التخصص البرمجية.\n"
                    f"اضغط على الزر بالأسفل للبدء.")
    bot.send_message(chat_id, welcome_text, reply_markup=markup)

@bot.message_handler(commands=['info'])
def info_cmd(message):
    info = ("🎓 *منصة الذكاء الاصطناعي وعلوم البيانات*\n➖➖➖➖➖➖➖➖\n"
            "المرجع الرقمي الشامل لطلاب الدفعة الثانية.\n\n"
            "🔹 المميزات:\n• أرشفة ذكية.\n• نماذج وتدريبات.\n• تنبيهات آلية.\n• أدوات مبرمجين.\n\n"
            "نسخة النظام: 4.0 - LMS Edition")
    bot.send_message(message.chat.id, info, parse_mode="Markdown")

# --- الميزات الذكية للطلاب ---
@bot.message_handler(func=lambda m: m.text == "🧠 معلومات تخصص الذكاء الاصطناعي")
def ai_info(message):
    msg = ("🤖 *تخصص الذكاء الاصطناعي وعلوم البيانات*\n\n"
           "تخصص المستقبل الذي يدمج بين علوم الحاسوب، الرياضيات، والتحليل الإحصائي لبرمجة أنظمة تحاكي الذكاء البشري.\n"
           "💡 *مجالات العمل:* مهندس تعلم آلة، محلل بيانات ضخمة، مطور أنظمة خبيرة، وباحث في الذكاء الاصطناعي.")
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🔍 بحث عن ملف")
def search_file_init(message):
    reset_modes(message.chat.id)
    admin_action_mode[message.chat.id] = "search"
    bot.send_message(message.chat.id, "🔍 أرسل كلمة للبحث عنها (مثال: تفاضل، برمجة، المحاضرة 3):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء"))

@bot.message_handler(func=lambda m: m.text == "👨‍💻 أدوات المبرمج")
def dev_tools(message):
    reset_modes(message.chat.id)
    admin_action_mode[message.chat.id] = "format_code"
    bot.send_message(message.chat.id, "👨‍💻 أرسل كود Python الخاص بك هنا وسأقوم بتنسيقه ووضعه في صندوق برمجي:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء"))

@bot.message_handler(func=lambda m: m.text == "🆘 طلب ملف مفقود")
def request_file(message):
    reset_modes(message.chat.id)
    admin_action_mode[message.chat.id] = "req_file"
    bot.send_message(message.chat.id, "أرسل اسم الملف والمادة التي تبحث عنها، وسنقوم بإشعار المشرفين لتوفيره:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء"))

@bot.message_handler(func=lambda m: m.text == "🚨 طوارئ الاختبارات (مراجعة سريعة)")
def emergency_mode(message):
    exam = get_emergency_exam()
    if exam:
        bot.send_message(message.chat.id, f"🚨 وضع الطوارئ مفعل بسبب:\n*{exam}*\n\n(يتم تجميع الملفات الهامة لهذه المادة قريباً...)", parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "لا توجد اختبارات خلال 24 ساعة.")

# --- أوامر المشرف العام والتقارير ---
@bot.message_handler(func=lambda m: is_super_admin(m.chat.id) and m.text in ["📊 تقرير الإنجاز الأكاديمي", "🛠️ إدارة المشرفين", "⚠️ التبليغات والطلبات"])
def super_admin_features(message):
    chat_id = message.chat.id
    if message.text == "📊 تقرير الإنجاز الأكاديمي":
        total_users = users_col.count_documents({})
        total_files = files_col.count_documents({})
        report = f"📊 *تقرير النظام الأكاديمي*\n👥 الطلاب: {total_users}\n📁 الملفات: {total_files}\n\n"
        bot.send_message(chat_id, report, parse_mode="Markdown")
        
    elif message.text == "⚠️ التبليغات والطلبات":
        reqs = list(requests_col.find({"status": "pending"}))
        errs = list(reports_col.find({"status": "pending"}))
        msg = f"📩 *طلبات الملفات:* {len(reqs)}\n⚠️ *أخطاء مبلّغ عنها:* {len(errs)}\n(يمكنك عرضها في التحديثات القادمة للوحة الويب)"
        bot.send_message(chat_id, msg, parse_mode="Markdown")
        
    elif message.text == "🛠️ إدارة المشرفين":
        markup = ReplyKeyboardMarkup(resize_keyboard=True).add("➕ مشرف عام", "➕ مشرف مسار مخصص", "➖ إزالة مشرف", "🔝 القائمة الرئيسية")
        bot.send_message(chat_id, "اختر نوع المشرف:", reply_markup=markup)

@bot.message_handler(func=lambda m: is_super_admin(m.chat.id) and m.text in ["➕ مشرف عام", "➕ مشرف مسار مخصص", "➖ إزالة مشرف"])
def manage_admins(message):
    chat_id = message.chat.id
    reset_modes(chat_id)
    if message.text == "➕ مشرف عام":
        admin_action_mode[chat_id] = "add_global_admin"
        bot.send_message(chat_id, "أرسل ID المشرف العام:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء"))
    elif message.text == "➕ مشرف مسار مخصص":
        admin_action_mode[chat_id] = "add_path_admin_id"
        bot.send_message(chat_id, "1. أرسل ID المشرف الخاص:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء"))

# --- معالجة الإدخالات النصية (بحث، أكواد، صلاحيات) ---
@bot.message_handler(content_types=['text', 'document', 'photo'], func=lambda m: admin_action_mode.get(m.chat.id) or upload_mode.get(m.chat.id) or add_folder_mode.get(m.chat.id))
def handle_action_modes(message):
    chat_id = message.chat.id
    mode = admin_action_mode.get(chat_id)
    text = message.text

    if text == "🛑 إلغاء":
        reset_modes(chat_id)
        show_menu(chat_id)
        return

    if mode == "search":
        results = files_col.find({"name": {"$regex": text, "$options": "i"}}).limit(10)
        found = False
        for r in results:
            found = True
            bot.send_message(chat_id, f"🔍 وجدنا:\n{r['name']}\nفي: {r['menu_path']}")
            send_file_to_user(chat_id, r, has_permission(chat_id, r['menu_path']))
        if not found: bot.send_message(chat_id, "❌ لم يتم العثور على ملفات تطابق بحثك.")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if mode == "format_code":
        formatted = f"```python\n{text}\n```"
        bot.send_message(chat_id, formatted, parse_mode="Markdown")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if mode == "req_file":
        requests_col.insert_one({"user_id": chat_id, "name": message.from_user.first_name, "req": text, "status": "pending"})
        bot.send_message(chat_id, "✅ تم إرسال طلبك للمشرفين وسيتم توفير الملف قريباً.")
        # تنبيه المدير
        bot.send_message(SUPER_ADMIN_ID, f"🔔 طلب ملف جديد من {message.from_user.first_name}:\n{text}")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if mode == "add_global_admin" and is_super_admin(chat_id):
        admins_col.insert_one({"id": int(text), "type": "global"})
        bot.send_message(chat_id, "✅ تمت إضافة مشرف عام.")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if mode == "add_path_admin_id" and is_super_admin(chat_id):
        temp_data[chat_id] = int(text)
        admin_action_mode[chat_id] = "add_path_admin_path"
        bot.send_message(chat_id, "2. الآن تصفح البوت وادخل للقسم الذي تريده، ثم أرسل كلمة 'تثبيت الصلاحية هنا'.")
        return

    if mode == "add_path_admin_path" and text == "تثبيت الصلاحية هنا":
        admins_col.insert_one({"id": temp_data[chat_id], "type": "path", "allowed_paths": [get_path_string(chat_id)]})
        bot.send_message(chat_id, f"✅ تم تثبيت صلاحية المشرف على:\n{get_path_string(chat_id)}")
        reset_modes(chat_id); show_menu(chat_id)
        return

    # معالجة رفع الملفات للمشرفين المسموح لهم
    if upload_mode.get(chat_id) and has_permission(chat_id, get_path_string(chat_id)):
        path_str = get_path_string(chat_id)
        name = text[:25]+"..." if message.content_type == 'text' else (message.caption or (message.document.file_name if message.content_type == 'document' else "صورة توضيحية"))
        
        doc = {"menu_path": path_str, "name": name, "type": message.content_type, "caption": message.caption}
        if message.content_type == 'text': doc['content'] = text
        else: doc['file_id'] = message.document.file_id if message.content_type == 'document' else message.photo[-1].file_id
            
        files_col.insert_one(doc)
        bot.send_message(chat_id, f"✅ تم الحفظ: {name}")

# --- معالجة الأزرار المدمجة (التبليغ، التعديل) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith(('rn_', 'rp_', 'dl_', 'err_')))
def handle_callbacks(call):
    chat_id = call.message.chat.id
    action, obj_id = call.data.split('_')
    
    if action == 'err':
        reports_col.insert_one({"file_id": obj_id, "reporter": chat_id, "status": "pending"})
        bot.answer_callback_query(call.id, "✅ تم إرسال البلاغ للإدارة للتحقق من الملف.", show_alert=True)
        bot.send_message(SUPER_ADMIN_ID, f"⚠️ إبلاغ عن مشكلة في ملف!\nID الملف: {obj_id}")
        return

    # تحقق من صلاحية التعديل/الحذف
    doc = files_col.find_one({"_id": ObjectId(obj_id)})
    if not doc or not has_permission(chat_id, doc['menu_path']):
        bot.answer_callback_query(call.id, "❌ غير مصرح لك.", show_alert=True)
        return

    if action == 'dl':
        files_col.delete_one({"_id": ObjectId(obj_id)})
        bot.delete_message(chat_id, call.message.message_id)
        bot.answer_callback_query(call.id, "✅ تم الحذف.")
        
    elif action == 'rn':
        admin_action_mode[chat_id] = "rename_file"
        action_payload[chat_id] = obj_id
        bot.send_message(chat_id, f"✏️ أرسل الاسم الجديد لـ:\n{doc['name']}")
        bot.answer_callback_query(call.id)

# --- التنقل العادي ---
@bot.message_handler(func=lambda message: True)
def handle_nav(message):
    chat_id = message.chat.id
    text = message.text
    path_str = get_path_string(chat_id)
    
    if text in ["📚 تصفح بوت الدفعة", "⚙️ لوحة الإدارة", "🔝 القائمة الرئيسية"]:
        user_path[chat_id] = []
        reset_modes(chat_id)
        show_menu(chat_id)
        return

    if text == "🔙 الرجوع للقائمة السابقة":
        if chat_id in user_path and user_path[chat_id]: user_path[chat_id].pop()
        show_menu(chat_id)
        return

    if text.startswith("📄 ") or text.startswith("📌 ") or text.startswith("🖼️ "):
        clean = text.replace("📄 ", "").replace("📌 ", "").replace("🖼️ ", "")
        res = files_col.find_one({"menu_path": path_str, "name": clean})
        if res: send_file_to_user(chat_id, res, has_permission(chat_id, path_str))
        return

    if text.startswith("📁 "):
        user_path[chat_id].append(text.replace("📁 ", ""))
        show_menu(chat_id)
        return

    menu = get_menu_by_path(user_path.get(chat_id, []))
    if isinstance(menu, dict) and text in menu:
        if chat_id not in user_path: user_path[chat_id] = []
        user_path[chat_id].append(text)
        show_menu(chat_id)

@app.route('/webhook', methods=['POST'])
def webhook_listen():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "!", 200

@app.route("/")
def home():
    return "LMS System 4.0 Active! 🚀", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
