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

# حل مشكلة الترميز بشكل كامل لاستقبال النصوص العربية
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
    reports_col = db['error_reports']
    requests_col = db['file_requests']
    logs_col = db['admin_logs'] # سجل العمليات الإدارية
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

HASHTAG_MAP = {
    "#ثقافة_محاضرات": "🌱 مستوى أول > 📅 ترم ثاني > 🕋 الثقافة الإسلامية > 📁 محاضرات وملخصات",
    "#بيانات_عملي": "🌱 مستوى أول > 📅 ترم ثاني > 📊 مقدمة في علوم البيانات > ⚙️ محاضرات العملي",
    "#برمجة_نظري": "🌱 مستوى أول > 📅 ترم ثاني > 💻 برمجة حاسوب > 📂 محاضرات نظري",
}

user_path, upload_mode, add_folder_mode, broadcast_mode = {}, {}, {}, {}
testing_mode, admin_action_mode, action_payload = {}, {}, {}
temp_data = {}

def is_super_admin(chat_id): return chat_id == SUPER_ADMIN_ID

def has_permission(chat_id, current_path_str):
    if is_super_admin(chat_id): return True
    if testing_mode.get(chat_id): return False  # وضع تجربة كمستخدم يسلب الصلاحيات الإدارية مؤقتاً
    admin = admins_col.find_one({"id": chat_id})
    if not admin: return False
    if admin.get("type") == "global": return True
    allowed_paths = admin.get("allowed_paths", [])
    for p in allowed_paths:
        if current_path_str.startswith(p) or current_path_str == p: return True
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

def get_path_string(chat_id): return " > ".join(user_path.get(chat_id, []))

def reset_modes(chat_id):
    upload_mode[chat_id] = False
    add_folder_mode[chat_id] = False
    broadcast_mode[chat_id] = False
    admin_action_mode[chat_id] = None
    action_payload.pop(chat_id, None)

def log_action(admin_id, action_desc):
    logs_col.insert_one({"admin_id": admin_id, "action": action_desc, "date": datetime.utcnow()})

# --- مهام الخلفية الآلية لجدولة التنبيهات وضبط الأوقات ---
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
        except: pass
        time.sleep(45)

threading.Thread(target=background_tasks_thread, daemon=True).start()

def get_emergency_exam():
    now = datetime.utcnow() + timedelta(hours=3)
    for alert in alerts_col.find({"status": "pending"}):
        if "اختبار" in alert['message'] or "امتحان" in alert['message']:
            try:
                alert_time = datetime.strptime(alert['send_time'], "%Y-%m-%d %H:%M")
                if timedelta(hours=0) <= (alert_time - now) <= timedelta(hours=24): return alert['message']
            except: pass
    return None

# --- الأرشفة التلقائية الصامتة من المجموعات والقنوات ---
@bot.message_handler(content_types=['document', 'photo'], func=lambda m: m.chat.type in ['group', 'supergroup', 'channel'])
def auto_archive_handler(message):
    caption = message.caption or ""
    for tag, path in HASHTAG_MAP.items():
        if tag in caption:
            name = caption.replace(tag, "").strip() or (message.document.file_name if message.content_type == 'document' else "صورة أرشيفية")
            doc = {"menu_path": path, "name": name, "type": message.content_type, "caption": caption, "downloads": 0, "upload_date": datetime.utcnow()}
            if message.content_type == 'document': doc['file_id'] = message.document.file_id
            else: doc['file_id'] = message.photo[-1].file_id
            files_col.insert_one(doc)
            try: bot.reply_to(message, f"✅ تمت الأرشفة في المجلد بشكل صامت.")
            except: pass
            break

# --- بناء نظام القوائم والتنقل وإصلاح الاستجابة للأزرار ---
@bot.message_handler(func=lambda m: not is_bot_active() and m.chat.id != SUPER_ADMIN_ID)
def system_offline(message):
    bot.send_message(message.chat.id, "⛔ المنصة مغلقة حالياً للصيانة بقرار من الإدارة العليا.")

def show_menu(chat_id):
    path = user_path.get(chat_id, [])
    current_menu = get_menu_by_path(path)
    path_str = get_path_string(chat_id)
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    mode = admin_action_mode.get(chat_id)
    
    # 📌 التعديل العبقري: واجهة المشرف أثناء التثبيت وصلاحية المسار المخصص
    if mode == "add_path_admin_path":
        markup.add(KeyboardButton("✅ تعيين صلاحية المشرف هنا"), KeyboardButton("🛑 إلغاء"))
        if isinstance(current_menu, dict):
            for key in current_menu.keys(): markup.add(KeyboardButton(key))
        for df in folders_col.find({"parent_path": path_str}): markup.add(KeyboardButton(f"📁 {df['folder_name']}"))
        if path: markup.add("🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية")
        bot.send_message(chat_id, f"📍 تصفح الأقسام واضغط لتثبيت المشرف.\nالموقع الحالي: {path_str or 'الرئيسية'}", reply_markup=markup)
        return

    # 📦 واجهة نقل الملف الذكي بين المجلدات والأقسام
    if mode == "move_file_dest":
        markup.add(KeyboardButton("📦 أنقل الملف إلى هذا القسم"), KeyboardButton("🛑 إلغاء"))
        if isinstance(current_menu, dict):
            for key in current_menu.keys(): markup.add(KeyboardButton(key))
        for df in folders_col.find({"parent_path": path_str}): markup.add(KeyboardButton(f"📁 {df['folder_name']}"))
        if path: markup.add("🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية")
        bot.send_message(chat_id, f"📦 تصفح الأقسام واضغط لنقل الملف هنا.\nالموقع الحالي: {path_str or 'الرئيسية'}", reply_markup=markup)
        return

    if not path:
        exam = get_emergency_exam()
        if emergency_mode := (exam is not None):
            markup.add(KeyboardButton("🚨 طوارئ الاختبارات (مراجعة سريعة)"))
            
        for key in ACADEMIC_STRUCTURE.keys(): markup.add(KeyboardButton(key))
        markup.add("🔥 الملفات الأكثر شعبية", "🆕 تحديثات اليوم")
        markup.add("🧠 معلومات الذكاء الاصطناعي", "🔍 بحث عن ملف")
        markup.add("👨‍💻 أدوات المبرمج", "🆘 طلب ملف مفقود")
        
        if is_super_admin(chat_id) and not testing_mode.get(chat_id):
            markup.add("📊 تقرير الإنجاز", "📢 رسالة جماعية")
            markup.add("⏰ التنبيهات المجدولة", "🛠️ إدارة المشرفين")
            markup.add("⚙️ زر الأمان (تشغيل/تعطيل)")
            
        bot.send_message(chat_id, "مرحباً بك في المنصة الأكاديمية لقسم الذكاء الاصطناعي وعلوم البيانات 🎓\n\nاختر من القائمة أدناه للبدء:", reply_markup=markup)
        return

    if isinstance(current_menu, dict):
        for key in current_menu.keys(): markup.add(KeyboardButton(key))
            
    for df in folders_col.find({"parent_path": path_str}): markup.add(KeyboardButton(f"📁 {df['folder_name']}"))
    for f in files_col.find({"menu_path": path_str}):
        icon = "📌" if f.get("type") == "text" else "🖼️" if f.get("type") == "photo" else "📄"
        markup.add(KeyboardButton(f"{icon} {f['name']}"))

    markup.add("🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية")
    
    # إصلاح ظهور وتفعيل الأزرار الإدارية للمشرف المسموح له في هذا المسار بالتحديد
    if testing_mode.get(chat_id):
        markup.add("🛑 إنهاء التجربة والعودة للإشراف")
    elif has_permission(chat_id, path_str):
        markup.add("👤 تجربة كمستخدم", "➕ إضافة ملف/نص")
        markup.add("📂 إضافة مجلد", "🗑️ تفريغ القسم")

    bot.send_message(chat_id, f"📂 القسم الحالي: {path_str}", reply_markup=markup)

def send_file_to_user(chat_id, res, has_perm):
    markup = InlineKeyboardMarkup(row_width=2)
    file_id_str = str(res['_id'])
    share_url = f"https://t.me/{BOT_USERNAME}?start={file_id_str}"
    
    if has_perm and not testing_mode.get(chat_id):
        markup.add(InlineKeyboardButton("✏️ تعديل الاسم", callback_data=f"rn_{file_id_str}"), InlineKeyboardButton("🔄 استبدال الملف", callback_data=f"rp_{file_id_str}"))
        markup.add(InlineKeyboardButton("🗑️ حذف الملف", callback_data=f"dl_{file_id_str}"), InlineKeyboardButton("📦 نقل الملف", callback_data=f"mv_{file_id_str}"))
        markup.add(InlineKeyboardButton("🔗 رابط مباشر (للمشاركة)", url=f"https://t.me/share/url?url={share_url}"))
    else:
        markup.add(InlineKeyboardButton("🔗 شارك الملف مع زملائك", url=f"https://t.me/share/url?url={share_url}"))
        markup.add(InlineKeyboardButton("⚠️ أبلغ عن خطأ بالملف", callback_data=f"err_{file_id_str}"))

    caption = res.get('caption', res['name']) + f"\n\n🔻 عدد التحميلات: {res.get('downloads', 0)}"

    if res['type'] == 'text': bot.send_message(chat_id, res['content'], reply_markup=markup)
    elif res['type'] == 'photo': bot.send_photo(chat_id, res['file_id'], caption=caption, reply_markup=markup)
    else: bot.send_document(chat_id, res['file_id'], caption=caption, reply_markup=markup)

# --- أوامر التوجيه والمستخدمين ---
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    name = message.from_user.first_name
    parts = message.text.split()
    
    if len(parts) > 1:
        try:
            res = files_col.find_one({"_id": ObjectId(parts[1])})
            if res:
                files_col.update_one({"_id": ObjectId(parts[1])}, {"$inc": {"downloads": 1}})
                bot.send_message(chat_id, "📥 جاري إحضار الملف...")
                send_file_to_user(chat_id, res, has_permission(chat_id, res['menu_path']))
                return
        except: pass

    users_col.update_one({"chat_id": chat_id}, {"$set": {"first_name": name, "username": f"@{message.from_user.username}"}}, upsert=True)
    user_path[chat_id] = []
    reset_modes(chat_id)
    testing_mode[chat_id] = False
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📚 تصفح بوت الدفعة")
    
    welcome_text = (f"أهلاً بك يا {name} في منصة الذكاء الاصطناعي وعلوم البيانات 🎓\n\n"
                    f"المنصة تتيح لك الوصول للمحاضرات والملخصات، تتبع التنبيهات، والبحث في الأرشيف الأكاديمي.\n"
                    f"اضغط على الزر بالأسفل للتصفح البدء.")
    bot.send_message(chat_id, welcome_text, reply_markup=markup)

@bot.message_handler(commands=['info', 'stat'])
def system_commands(message):
    chat_id = message.chat.id
    if message.text == '/info':
        info = "🎓 *منصة الذكاء الاصطناعي وعلوم البيانات*\nالمرجع الأكاديمي الشامل لطلاب الدفعة الثانية.\nنسخة النظام المستقر: 5.0"
        bot.send_message(chat_id, info, parse_mode="Markdown")
    elif message.text == '/stat':
        markup = ReplyKeyboardMarkup(resize_keyboard=True).add("📚 تصفح بوت الدفعة")
        bot.send_message(chat_id, "📊 خيار التصفح السريع متاح، اضغط بالأسفل للوصول للمستويات:", reply_markup=markup)

# --- تفعيل الخصائص الذكية والميزات المتكاملة للمنصة ---
@bot.message_handler(func=lambda m: m.text in ["🔥 الملفات الأكثر شعبية", "🆕 تحديثات اليوم", "🧠 معلومات الذكاء الاصطناعي", "🚨 طوارئ الاختبارات (مراجعة سريعة)"])
def student_smart_features(message):
    chat_id = message.chat.id
    if message.text == "🔥 الملفات الأكثر شعبية":
        top = list(files_col.find().sort("downloads", -1).limit(5))
        if not top: bot.send_message(chat_id, "لا توجد إحصائيات تحميل حتى الآن.")
        else:
            bot.send_message(chat_id, "🔥 *الملفات الأكثر طلباً وتحميلاً هذا الأسبوع:*", parse_mode="Markdown")
            for f in top: send_file_to_user(chat_id, f, False)
    elif message.text == "🆕 تحديثات اليوم":
        yesterday = datetime.utcnow() - timedelta(days=1)
        new_files = list(files_col.find({"upload_date": {"$gte": yesterday}}).limit(10))
        if not new_files: bot.send_message(chat_id, "لم يتم إضافة محاضرات جديدة خلال الـ 24 ساعة الماضية.")
        else:
            bot.send_message(chat_id, "🆕 *آخر المحاضرات والملخصات المضافة اليوم:*", parse_mode="Markdown")
            for f in new_files: send_file_to_user(chat_id, f, False)
    elif message.text == "🧠 معلومات الذكاء الاصطناعي":
        bot.send_message(chat_id, "🤖 *تخصص الذكاء الاصطناعي وعلوم البيانات*\nتخصص مستقبلي قوي يعتمد على دراسة البرمجة، معالجة البيانات، والأنظمة الذكية والمستقلة.", parse_mode="Markdown")
    elif message.text == "🚨 طوارئ الاختبارات (مراجعة سريعة)":
        exam = get_emergency_exam()
        if exam: bot.send_message(chat_id, f"🚨 وضع الطوارئ مفعل للمذاكرة السريعة:\n\n*{exam}*", parse_mode="Markdown")
        else: bot.send_message(chat_id, "لا توجد اختبارات مجدولة خلال الـ 24 ساعة القادمة. بانتظار تحديث الإدارة.")

@bot.message_handler(func=lambda m: is_super_admin(m.chat.id) and m.text == "🛠️ إدارة المشرفين")
def manage_admins_panel(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True).add("➕ مشرف عام", "➕ مشرف مسار مخصص", "➖ إزالة مشرف", "🔝 القائمة الرئيسية")
    bot.send_message(message.chat.id, "🛠️ إدارة المشرفين - اختر نوع الصلاحية المطلوبة:", reply_markup=markup)

@bot.message_handler(func=lambda m: is_super_admin(m.chat.id) and m.text in ["➕ مشرف عام", "➕ مشرف مسار مخصص", "➖ إزالة مشرف"])
def manage_admins_execution(message):
    chat_id = message.chat.id
    reset_modes(chat_id)
    if message.text == "➕ مشرف عام":
        admin_action_mode[chat_id] = "add_global_admin"
        bot.send_message(chat_id, "أرسل المعرّف الرقمي (ID) للمشرف العام الجديد:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء"))
    elif message.text == "➕ مشرف مسار مخصص":
        admin_action_mode[chat_id] = "add_path_admin_id"
        bot.send_message(chat_id, "أرسل المعرّف الرقمي (ID) للمشرف أولاً:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء"))

# --- معالجة طلبات البحث، الأدوات والأجهزة المفقودة ---
@bot.message_handler(func=lambda m: m.text in ["🔍 بحث عن ملف", "👨‍💻 أدوات المبرمج", "🆘 طلب ملف مفقود"])
def student_utilities(message):
    chat_id = message.chat.id
    reset_modes(chat_id)
    if message.text == "🔍 بحث عن ملف":
        admin_action_mode[chat_id] = "search"
        bot.send_message(chat_id, "🔍 أرسل كلمة البحث (اسم المحاضرة أو المقرر):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء"))
    elif message.text == "👨‍💻 أدوات المبرمج":
        admin_action_mode[chat_id] = "format_code"
        bot.send_message(chat_id, "👨‍💻 أرسل كود Python الخاص بك هنا لتنسيقه برمجياً وضبطه:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء"))
    elif message.text == "🆘 طلب ملف مفقود":
        admin_action_mode[chat_id] = "req_file"
        bot.send_message(chat_id, "🆘 اكتب اسم الملف الناقص وسنقوم بإشعار المشرف العام والمختص لتوفيره فوراً:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء"))

# --- 🛠️ إصلاح استقبال الأزرار الإدارية الحتمية بدقة مطابقة مائة بالمائة ---
@bot.message_handler(func=lambda m: m.text in ["👤 تجربة كمستخدم", "➕ إضافة ملف/نص", "📂 إضافة مجلد", "🗑️ تفريغ القسم", "🛑 إنهاء التجربة والعودة للإشراف", "⚙️ زر الأمان (تشغيل/تعطيل)", "📊 تقرير الإنجاز", "📢 رسالة جماعية"])
def admin_exact_triggers(message):
    chat_id = message.chat.id
    text = message.text
    path_str = get_path_string(chat_id)
    
    # التحقق من الصلاحيات للمسار قبل تفعيل الإجراء
    if text in ["👤 تجربة كمستخدم", "➕ إضافة ملف/نص", "📂 إضافة مجلد", "🗑️ تفريغ القسم"] and not has_permission(chat_id, path_str):
        return

    if text == "👤 تجربة كمستخدم":
        testing_mode[chat_id] = True
        bot.send_message(chat_id, "👀 تم تفعيل وضع المستخدم، الأزرار الإدارية مخفية الآن.")
        show_menu(chat_id)
    elif text == "🛑 إنهاء التجربة والعودة للإشراف":
        testing_mode[chat_id] = False
        bot.send_message(chat_id, "💼 تم إلغاء وضع المستخدم، عادت صلاحيات الإشراف والتحكم.")
        show_menu(chat_id)
    elif text == "➕ إضافة ملف/نص":
        reset_modes(chat_id)
        upload_mode[chat_id] = True
        bot.send_message(chat_id, "📥 أرسل الآن الملف، الصورة أو النص (أو قم بعمل توجيه Forward مباشرة):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء"))
    elif text == "📂 إضافة مجلد":
        reset_modes(chat_id)
        add_folder_mode[chat_id] = True
        bot.send_message(chat_id, "📂 أرسل اسم المجلد الفرعي الجديد المطلوب إنشاؤه:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء"))
    elif text == "🗑️ تفريغ القسم":
        # حذف آمن يعتمد على تطابق مسار القسم الحالي
        files_col.delete_many({"menu_path": path_str})
        folders_col.delete_many({"parent_path": path_str})
        log_action(chat_id, f"تفريغ المجلد: {path_str}")
        bot.send_message(chat_id, "🗑️ تم مسح كافة محتويات وملفات هذا المجلد بنجاح من قاعدة البيانات!")
        show_menu(chat_id)
    elif text == "📊 تقرير الإنجاز" and is_super_admin(chat_id):
        rep = f"📊 *تقرير لوحة الإدارة العليا*\n\n👤 الطلاب المشتركين: {users_col.count_documents({})}\n📄 إجمالي الملفات والمحاضرات: {files_col.count_documents({})}"
        bot.send_message(chat_id, rep, parse_mode="Markdown")
    elif text == "⚙️ زر الأمان (تشغيل/تعطيل)" and is_super_admin(chat_id):
        markup = ReplyKeyboardMarkup(resize_keyboard=True).add("▶️ تشغيل البوت", "⏸️ إيقاف البوت", "🔝 القائمة الرئيسية")
        bot.send_message(chat_id, "🛡️ غرفة التحكم بالأمان وحالة المنصة الافتراضية:", reply_markup=markup)

# --- إدارة حالات الأمان ---
@bot.message_handler(func=lambda m: is_super_admin(m.chat.id) and m.text in ["▶️ تشغيل البوت", "⏸️ إيقاف البوت"])
def exec_security(message):
    status = "active" if message.text == "▶️ تشغيل البوت" else "inactive"
    settings_col.update_one({}, {"$set": {"status": status}}, upsert=True)
    msg = "✅ تم تشغيل المنصة للجميع بنجاح." if status == "active" else "⛔ تم تعطيل البوت وإغلاقه بوجه المستخدمين مؤقتاً."
    bot.send_message(message.chat.id, msg)
    show_menu(message.chat.id)

# --- معالجة المدخلات والحالات المتقدمة (أرشفة، صلاحيات، تعديل، نقل) ---
@bot.message_handler(content_types=['text', 'document', 'photo'], func=lambda m: admin_action_mode.get(m.chat.id) or upload_mode.get(m.chat.id) or add_folder_mode.get(m.chat.id))
def handle_action_modes(message):
    chat_id = message.chat.id
    mode = admin_action_mode.get(chat_id)
    text = message.text
    path_str = get_path_string(chat_id)

    if text == "🛑 إلغاء":
        reset_modes(chat_id); show_menu(chat_id)
        return

    if mode == "search":
        results = files_col.find({"name": {"$regex": text, "$options": "i"}}).limit(5)
        found = False
        for r in results:
            found = True
            bot.send_message(chat_id, f"🔍 نتيجة البحث وعثر عليها في المسار التالي:\n{r['menu_path']}")
            send_file_to_user(chat_id, r, has_permission(chat_id, r['menu_path']))
        if not found: bot.send_message(chat_id, "❌ لم نجد ملفات تطابق عنوان بحثك.")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if mode == "format_code":
        formatted = f"```python\n{text}\n```"
        bot.send_message(chat_id, "💻 *تم تنسيق الكود البرمجي ووضعه داخل صندوق نسخ سريع:*", parse_mode="Markdown")
        bot.send_message(chat_id, formatted, parse_mode="Markdown")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if mode == "req_file":
        requests_col.insert_one({"user_id": chat_id, "name": message.from_user.first_name, "req": text, "status": "pending"})
        bot.send_message(chat_id, "✅ تم تدوين طلبك وإشعار المشرف العام والمشرفين الأكاديميين لتوفيره قريباً.")
        bot.send_message(SUPER_ADMIN_ID, f"🔔 طلب مفقود جديد من {message.from_user.first_name}:\n{text}")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if mode == "add_global_admin" and is_super_admin(chat_id):
        try:
            admins_col.update_one({"id": int(text.strip())}, {"$set": {"type": "global"}}, upsert=True)
            bot.send_message(chat_id, f"✅ تمت ترقية المعرف {text} إلى مشرف عام على البوت بنجاح.")
        except: bot.send_message(chat_id, "❌ خطأ في الإضافة.")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if mode == "add_path_admin_id" and is_super_admin(chat_id):
        try:
            temp_data[chat_id] = int(text.strip())
            admin_action_mode[chat_id] = "add_path_admin_path"
            user_path[chat_id] = [] # 🚀 التوجيه التلقائي للمدير نحو المستويات لحسم الصلاحية بسهولة
            bot.send_message(chat_id, "✅ تم حفظ المعرّف. تم نقلك تلقائياً لواجهة المستويات؛ تصفح واضغط تأكيد الصلاحية عند المجلد المطلوب.")
            show_menu(chat_id)
        except: bot.send_message(chat_id, "❌ أرسل أرقام الآيدي فقط.")
        return

    if mode == "add_path_admin_path" and text == "✅ تعيين صلاحية المشرف هنا":
        admins_col.update_one(
            {"id": temp_data[chat_id]},
            {"$set": {"type": "path"}, "$addToSet": {"allowed_paths": path_str}},
            upsert=True
        )
        bot.send_message(chat_id, f"✅ تم تثبيت المشرف بنجاح وتخصيص صلاحيته حصرياً للمسار المختار:\n{path_str}")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if mode == "rename_file":
        obj_id = action_payload.get(chat_id)
        files_col.update_one({"_id": ObjectId(obj_id)}, {"$set": {"name": text.strip()}})
        bot.send_message(chat_id, "✅ تم تعديل اسم المستند بنجاح واكتمل التحديث.")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if mode == "replace_file":
        obj_id = action_payload.get(chat_id)
        if message.content_type == 'document':
            files_col.update_one({"_id": ObjectId(obj_id)}, {"$set": {"type": "document", "file_id": message.document.file_id, "name": message.caption or message.document.file_name, "caption": message.caption}})
        elif message.content_type == 'photo':
            files_col.update_one({"_id": ObjectId(obj_id)}, {"$set": {"type": "photo", "file_id": message.photo[-1].file_id, "name": message.caption or "صورة محدثة", "caption": message.caption}})
        elif message.content_type == 'text':
            files_col.update_one({"_id": ObjectId(obj_id)}, {"$set": {"type": "text", "content": text, "name": text[:25] + "..."}})
        bot.send_message(chat_id, "✅ تم استبدال وتحديث الملف بنجاح.")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if mode == "move_file_dest" and text == "📦 أنقل الملف إلى هذا القسم":
        obj_id = action_payload.get(chat_id)
        files_col.update_one({"_id": ObjectId(obj_id)}, {"$set": {"menu_path": path_str}})
        bot.send_message(chat_id, f"📦 تم نقل الملف بنجاح وحفظه في القسم الجديد:\n{path_str}")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if add_folder_mode.get(chat_id) and message.content_type == 'text' and has_permission(chat_id, path_str):
        folders_col.insert_one({"parent_path": path_str, "folder_name": text.strip()})
        bot.send_message(chat_id, f"✅ تم إنشاء مجلد فرعي جديد باسم: {text.strip()}")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if upload_mode.get(chat_id) and has_permission(chat_id, path_str):
        name = text[:25]+"..." if message.content_type == 'text' else (message.caption or (message.document.file_name if message.content_type == 'document' else "صورة توضيحية"))
        doc = {"menu_path": path_str, "name": name, "type": message.content_type, "caption": message.caption, "downloads": 0, "upload_date": datetime.utcnow()}
        if message.content_type == 'text': doc['content'] = text
        else: doc['file_id'] = message.document.file_id if message.content_type == 'document' else message.photo[-1].file_id
        files_col.insert_one(doc)
        bot.send_message(chat_id, f"✅ تم الحفظ بنجاح وأرشفته في المجلد الحالي: {name}")
        reset_modes(chat_id); show_menu(chat_id)
        return

# --- معالجة الـ Callback المباشر للملفات (حذف، تعديل، نقل) ---
@bot.callback_query_handler(func=lambda call: call.data.startswith(('rn_', 'rp_', 'dl_', 'mv_', 'err_')))
def handle_callbacks(call):
    chat_id = call.message.chat.id
    action, obj_id = call.data.split('_')
    
    if action == 'err':
        reports_col.insert_one({"file_id": obj_id, "reporter": chat_id, "status": "pending"})
        bot.answer_callback_query(call.id, "✅ تم تسجيل بلاغك، وسيتم مراجعته وتصحيح الخطأ من الإدارة.", show_alert=True)
        bot.send_message(SUPER_ADMIN_ID, f"⚠️ بلاغ عن خطأ في الملف ذو المعرّف الرقمي: {obj_id}")
        return

    doc = files_col.find_one({"_id": ObjectId(obj_id)})
    if not doc or not has_permission(chat_id, doc['menu_path']):
        bot.answer_callback_query(call.id, "❌ غير مصرح لك بالتحكم أو إدارة هذا الملف.", show_alert=True)
        return

    if action == 'dl':
        files_col.delete_one({"_id": ObjectId(obj_id)})
        bot.delete_message(chat_id, call.message.message_id)
        bot.answer_callback_query(call.id, "🗑️ تم حذف الملف نهائياً.")
        show_menu(chat_id)
    elif action == 'rn':
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "rename_file"
        action_payload[chat_id] = obj_id
        bot.send_message(chat_id, f"✏️ اكتب الاسم الجديد للمستند الحالي:")
        bot.answer_callback_query(call.id)
    elif action == 'rp':
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "replace_file"
        action_payload[chat_id] = obj_id
        bot.send_message(chat_id, f"🔄 أرسل الآن المستند أو النص الجديد الذي سيحل محله:")
        bot.answer_callback_query(call.id)
    elif action == 'mv':
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "move_file_dest"
        action_payload[chat_id] = obj_id
        user_path[chat_id] = [] # نقل ذكي: إرجاع المدير للرئيسية ليتصفح مكان الحفظ الجديد بسلاسة
        bot.send_message(chat_id, "📦 تم تفعيل وضع النقل الذكي للملف؛ تصفح الآن الأقسام والمجلدات واضغط زر الحفظ والنقل عند المجلد الهدف.")
        show_menu(chat_id)
        bot.answer_callback_query(call.id)

# --- محرك التنقل واستعراض الهرم الأكاديمي الشامل ---
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

    # استعراض المستندات والملخصات
    if text.startswith("📄 ") or text.startswith("📌 ") or text.startswith("🖼️ "):
        clean = text.replace("📄 ", "").replace("📌 ", "").replace("🖼️ ", "")
        res = files_col.find_one({"menu_path": path_str, "name": clean})
        if res: send_file_to_user(chat_id, res, has_permission(chat_id, path_str))
        return

    # الدخول للمجلدات الفرعية والديناميكية
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
    return "LMS Secure Engine 5.0 Active! 🚀", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
