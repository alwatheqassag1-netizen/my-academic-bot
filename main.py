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

# حل مشكلة الترميز
if sys.version_info >= (3, 0):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_TOKEN = '7524289470:AAGkeX96s1s6saxGP3uy14MN9it19nKn10A'
SUPER_ADMIN_ID = 6842543527
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
    logs_col = db['admin_logs']
    print("MongoDB Connected! 🎉")
except Exception as e:
    print(f"MongoDB Error: {e}")

if admins_col.count_documents({}) == 0:
    admins_col.insert_one({"id": SUPER_ADMIN_ID, "type": "super", "allowed_paths": []})
if settings_col.count_documents({}) == 0:
    settings_col.insert_one({"status": "active"})

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)
BOT_USERNAME = bot.get_me().username

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

user_path, upload_mode, add_folder_mode, admin_action_mode = {}, {}, {}, {}
testing_mode, action_payload, temp_data = {}, {}, {}

def is_super_admin(chat_id): return chat_id == SUPER_ADMIN_ID

def has_permission(chat_id, current_path_str):
    if testing_mode.get(chat_id): return False
    if is_super_admin(chat_id): return True
    admin = admins_col.find_one({"id": chat_id})
    if not admin: return False
    if admin.get("type") == "global": return True
    for p in admin.get("allowed_paths", []):
        if current_path_str.startswith(p) or current_path_str == p: return True
    return False

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
    admin_action_mode[chat_id] = None
    action_payload.pop(chat_id, None)

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

@bot.message_handler(content_types=['document', 'photo'], func=lambda m: m.chat.type in ['group', 'supergroup', 'channel'])
def auto_archive_handler(message):
    caption = message.caption or ""
    for tag, path in HASHTAG_MAP.items():
        if tag in caption:
            name = caption.replace(tag, "").strip() or ("مستند" if message.content_type == 'document' else "صورة")
            doc = {"menu_path": path, "name": name, "type": message.content_type, "caption": caption, "downloads": 0, "upload_date": datetime.utcnow()}
            if message.content_type == 'document': doc['file_id'] = message.document.file_id
            else: doc['file_id'] = message.photo[-1].file_id
            files_col.insert_one(doc)
            break

def show_menu(chat_id):
    path = user_path.get(chat_id, [])
    current_menu = get_menu_by_path(path)
    path_str = get_path_string(chat_id)
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    mode = admin_action_mode.get(chat_id)
    if mode == "add_path_admin_path":
        markup.add(KeyboardButton("✅ تعيين صلاحية المشرف هنا"), KeyboardButton("🛑 إلغاء"))
        bot.send_message(chat_id, f"📍 تصفح الأقسام لتحديد الصلاحية.\nالمسار الحالي: {path_str or 'الرئيسية'}")
    elif mode == "move_file_dest":
        markup.add(KeyboardButton("📦 أنقل الملف إلى هذا القسم"), KeyboardButton("🛑 إلغاء"))
        bot.send_message(chat_id, f"📦 تصفح الأقسام لنقل الملف.\nالمسار الحالي: {path_str or 'الرئيسية'}")

    if not path:
        for key in ACADEMIC_STRUCTURE.keys(): markup.add(KeyboardButton(key))
        markup.add("🔥 الملفات الأكثر شعبية", "🆕 تحديثات اليوم")
        markup.add("🧠 معلومات الذكاء الاصطناعي", "🔍 بحث عن ملف")
        markup.add("🆘 طلب ملف مفقود")
        if is_super_admin(chat_id) and not testing_mode.get(chat_id):
            markup.add("📊 تقرير الإنجاز", "📢 رسالة جماعية", "⏰ التنبيهات المجدولة", "🛠️ إدارة المشرفين", "⚠️ التبليغات", "⚙️ زر الأمان (تشغيل/تعطيل)")
        bot.send_message(chat_id, "مرحباً بك في المنصة الأكاديمية 🎓\nاختر من القائمة للبدء:", reply_markup=markup)
        return

    if isinstance(current_menu, dict):
        for key in current_menu.keys(): markup.add(KeyboardButton(key))
            
    for df in folders_col.find({"parent_path": path_str}): markup.add(KeyboardButton(f"📁 {df['folder_name']}"))
    for f in files_col.find({"menu_path": path_str}):
        icon = "📌" if f.get("type") == "text" else "🖼️" if f.get("type") == "photo" else "📄"
        markup.add(KeyboardButton(f"{icon} {f['name']}"))

    markup.add("🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية")
    
    if testing_mode.get(chat_id):
        markup.add("🛑 إنهاء التجربة والعودة للإشراف")
    elif has_permission(chat_id, path_str) and mode not in ["add_path_admin_path", "move_file_dest"]:
        markup.add("👤 تجربة كمستخدم", "➕ إضافة ملف/نص", "📂 إضافة مجلد", "🗑️ تفريغ القسم")

    bot.send_message(chat_id, f"📂 القسم: {path_str}", reply_markup=markup)

def send_file_to_user(chat_id, res, has_perm):
    markup = InlineKeyboardMarkup(row_width=2)
    file_id_str = str(res['_id'])
    share_url = f"https://t.me/{BOT_USERNAME}?start={file_id_str}"
    
    if has_perm and not testing_mode.get(chat_id):
        markup.add(InlineKeyboardButton("✏️ تعديل", callback_data=f"rn_{file_id_str}"), InlineKeyboardButton("🔄 استبدال", callback_data=f"rp_{file_id_str}"))
        markup.add(InlineKeyboardButton("🗑️ حذف", callback_data=f"dl_{file_id_str}"), InlineKeyboardButton("📦 نقل", callback_data=f"mv_{file_id_str}"))
        markup.add(InlineKeyboardButton("🔗 رابط مشاركة", url=f"https://t.me/share/url?url={share_url}"))
    else:
        markup.add(InlineKeyboardButton("🔗 شارك الملف", url=f"https://t.me/share/url?url={share_url}"))
        markup.add(InlineKeyboardButton("⚠️ إبلاغ عن خطأ", callback_data=f"err_{file_id_str}"))

    caption = res.get('caption', res['name']) + f"\n\n🔻 التحميلات: {res.get('downloads', 0)}"
    if res['type'] == 'text': bot.send_message(chat_id, res['content'], reply_markup=markup)
    elif res['type'] == 'photo': bot.send_photo(chat_id, res['file_id'], caption=caption, reply_markup=markup)
    else: bot.send_document(chat_id, res['file_id'], caption=caption, reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    users_col.update_one({"chat_id": chat_id}, {"$set": {"first_name": message.from_user.first_name, "username": f"@{message.from_user.username}"}}, upsert=True)
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
    user_path[chat_id] = []
    reset_modes(chat_id)
    testing_mode[chat_id] = False
    show_menu(chat_id)

@bot.message_handler(commands=['info', 'stat'])
def sys_cmds(message):
    if message.text == '/info':
        info = ("🎓 *دليل استخدام المنصة الأكاديمية*\n\n"
                "🔹 *للتنقل:* اضغط على الأزرار السفلية لاختيار المستوى، ثم الترم، ثم المقرر لتجد المحاضرات والنماذج.\n"
                "🔹 *بحث سريع:* استخدم زر (🔍 بحث عن ملف) للوصول لأي محاضرة مباشرة.\n"
                "🔹 *الإشعارات:* ستصلك رسائل تنبيه بمواعيد الاختبارات الهامة تلقائياً.\n"
                "🔹 *الملفات المفقودة:* يمكنك طلب أي ملف غير موجود عبر (🆘 طلب ملف مفقود).\n\n"
                "هذه المنصة هي الأرشيف الذكي لطلاب الذكاء الاصطناعي - الإصدار 5.0")
        bot.send_message(message.chat.id, info, parse_mode="Markdown")
    elif message.text == '/stat':
        user_path[message.chat.id] = []
        show_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.text in ["🔥 الملفات الأكثر شعبية", "🆕 تحديثات اليوم", "🧠 معلومات الذكاء الاصطناعي", "🛠️ إدارة المشرفين"])
def features_handler(message):
    chat_id = message.chat.id
    if message.text == "🔥 الملفات الأكثر شعبية":
        top = list(files_col.find().sort("downloads", -1).limit(5))
        if not top: bot.send_message(chat_id, "لا توجد إحصائيات بعد.")
        else:
            for f in top: send_file_to_user(chat_id, f, False)
    elif message.text == "🆕 تحديثات اليوم":
        yesterday = datetime.utcnow() - timedelta(days=1)
        new_files = list(files_col.find({"upload_date": {"$gte": yesterday}}).limit(10))
        if not new_files: bot.send_message(chat_id, "لا يوجد ملفات جديدة اليوم.")
        else:
            for f in new_files: send_file_to_user(chat_id, f, False)
    elif message.text == "🧠 معلومات الذكاء الاصطناعي":
        bot.send_message(chat_id, "🤖 *الذكاء الاصطناعي وعلوم البيانات*\nتخصص يدمج البرمجة، الرياضيات، وتحليل البيانات.", parse_mode="Markdown")
    elif message.text == "🛠️ إدارة المشرفين" and is_super_admin(chat_id):
        bot.send_message(chat_id, "اختر:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("➕ مشرف عام", "➕ مشرف مسار مخصص", "➖ إزالة مشرف", "🔝 القائمة الرئيسية"))

@bot.message_handler(func=lambda m: m.text in ["🔍 بحث عن ملف", "🆘 طلب ملف مفقود"])
def util_handler(message):
    chat_id = message.chat.id
    reset_modes(chat_id)
    if message.text == "🔍 بحث عن ملف":
        admin_action_mode[chat_id] = "search"
        bot.send_message(chat_id, "🔍 أرسل كلمة للبحث:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء"))
    elif message.text == "🆘 طلب ملف مفقود":
        admin_action_mode[chat_id] = "req_file"
        bot.send_message(chat_id, "🆘 أرسل اسم الملف والمادة:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء"))

@bot.message_handler(func=lambda m: m.text in ["👤 تجربة كمستخدم", "➕ إضافة ملف/نص", "📂 إضافة مجلد", "🗑️ تفريغ القسم", "🛑 إنهاء التجربة والعودة للإشراف", "⚙️ زر الأمان (تشغيل/تعطيل)", "📊 تقرير الإنجاز", "📢 رسالة جماعية", "➕ مشرف عام", "➕ مشرف مسار مخصص", "➖ إزالة مشرف"])
def exact_admin_buttons(message):
    chat_id = message.chat.id
    text = message.text
    path_str = get_path_string(chat_id)

    if text == "🛑 إنهاء التجربة والعودة للإشراف":
        testing_mode[chat_id] = False
        bot.send_message(chat_id, "💼 عادت صلاحيات الإشراف.")
        show_menu(chat_id)
        return

    if text in ["👤 تجربة كمستخدم", "➕ إضافة ملف/نص", "📂 إضافة مجلد", "🗑️ تفريغ القسم"] and not has_permission(chat_id, path_str):
        return

    if text == "👤 تجربة كمستخدم":
        testing_mode[chat_id] = True
        bot.send_message(chat_id, "👀 وضع المستخدم مفعل.")
        show_menu(chat_id)
    elif text == "➕ إضافة ملف/نص":
        reset_modes(chat_id)
        upload_mode[chat_id] = True
        bot.send_message(chat_id, "📥 أرسل الملف، الصورة أو النص:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء"))
    elif text == "📂 إضافة مجلد":
        reset_modes(chat_id)
        add_folder_mode[chat_id] = True
        bot.send_message(chat_id, "📂 أرسل اسم المجلد الفرعي:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء"))
    elif text == "🗑️ تفريغ القسم":
        files_col.delete_many({"menu_path": path_str})
        folders_col.delete_many({"parent_path": path_str})
        bot.send_message(chat_id, "🗑️ تم مسح محتويات القسم بالكامل!")
        show_menu(chat_id)
    elif text == "📊 تقرير الإنجاز" and is_super_admin(chat_id):
        bot.send_message(chat_id, f"📊 *التقرير*\nالطلاب: {users_col.count_documents({})}\nالملفات: {files_col.count_documents({})}", parse_mode="Markdown")
    elif text == "⚙️ زر الأمان (تشغيل/تعطيل)" and is_super_admin(chat_id):
        bot.send_message(chat_id, "🛡️ حالة النظام:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("▶️ تشغيل البوت", "⏸️ إيقاف البوت", "🔝 القائمة الرئيسية"))
    elif text == "➕ مشرف عام" and is_super_admin(chat_id):
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "add_global_admin"
        bot.send_message(chat_id, "أرسل ID المشرف العام:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء"))
    elif text == "➕ مشرف مسار مخصص" and is_super_admin(chat_id):
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "add_path_admin_id"
        bot.send_message(chat_id, "أرسل ID المشرف:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء"))

@bot.message_handler(func=lambda m: is_super_admin(m.chat.id) and m.text in ["▶️ تشغيل البوت", "⏸️ إيقاف البوت"])
def exec_security(message):
    status = "active" if message.text == "▶️ تشغيل البوت" else "inactive"
    settings_col.update_one({}, {"$set": {"status": status}}, upsert=True)
    bot.send_message(message.chat.id, "✅ تم التحديث.")
    show_menu(message.chat.id)

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
            bot.send_message(chat_id, f"🔍 نتيجة في:\n{r['menu_path']}")
            send_file_to_user(chat_id, r, has_permission(chat_id, r['menu_path']))
        if not found: bot.send_message(chat_id, "❌ لا توجد نتائج.")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if mode == "req_file":
        requests_col.insert_one({"user_id": chat_id, "name": message.from_user.first_name, "req": text, "status": "pending"})
        bot.send_message(chat_id, "✅ تم تسجيل طلبك.")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if mode == "add_global_admin" and is_super_admin(chat_id):
        try:
            admins_col.update_one({"id": int(text.strip())}, {"$set": {"type": "global"}}, upsert=True)
            bot.send_message(chat_id, "✅ تمت الإضافة.")
        except: bot.send_message(chat_id, "❌ خطأ.")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if mode == "add_path_admin_id" and is_super_admin(chat_id):
        try:
            temp_data[chat_id] = int(text.strip())
            admin_action_mode[chat_id] = "add_path_admin_path"
            user_path[chat_id] = []
            show_menu(chat_id)
        except: bot.send_message(chat_id, "❌ أرقام فقط.")
        return

    if mode == "add_path_admin_path" and text == "✅ تعيين صلاحية المشرف هنا":
        admins_col.update_one({"id": temp_data[chat_id]}, {"$set": {"type": "path"}, "$addToSet": {"allowed_paths": path_str}}, upsert=True)
        bot.send_message(chat_id, f"✅ تم التثبيت في:\n{path_str}")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if mode == "rename_file":
        files_col.update_one({"_id": ObjectId(action_payload.get(chat_id))}, {"$set": {"name": text.strip()}})
        bot.send_message(chat_id, "✅ تم التعديل.")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if mode == "replace_file":
        obj_id = action_payload.get(chat_id)
        if message.content_type == 'document': files_col.update_one({"_id": ObjectId(obj_id)}, {"$set": {"type": "document", "file_id": message.document.file_id, "name": message.caption or message.document.file_name, "caption": message.caption}})
        elif message.content_type == 'photo': files_col.update_one({"_id": ObjectId(obj_id)}, {"$set": {"type": "photo", "file_id": message.photo[-1].file_id, "name": message.caption or "صورة", "caption": message.caption}})
        elif message.content_type == 'text': files_col.update_one({"_id": ObjectId(obj_id)}, {"$set": {"type": "text", "content": text, "name": text[:25]}})
        bot.send_message(chat_id, "✅ تم الاستبدال.")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if mode == "move_file_dest" and text == "📦 أنقل الملف إلى هذا القسم":
        files_col.update_one({"_id": ObjectId(action_payload.get(chat_id))}, {"$set": {"menu_path": path_str}})
        bot.send_message(chat_id, f"📦 تم النقل إلى:\n{path_str}")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if add_folder_mode.get(chat_id) and message.content_type == 'text' and has_permission(chat_id, path_str):
        folders_col.insert_one({"parent_path": path_str, "folder_name": text.strip()})
        bot.send_message(chat_id, f"✅ تم إنشاء: {text.strip()}")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if upload_mode.get(chat_id) and has_permission(chat_id, path_str):
        name = text[:25] if message.content_type == 'text' else (message.caption or (message.document.file_name if message.content_type == 'document' else "صورة"))
        doc = {"menu_path": path_str, "name": name, "type": message.content_type, "caption": message.caption, "downloads": 0, "upload_date": datetime.utcnow()}
        if message.content_type == 'text': doc['content'] = text
        else: doc['file_id'] = message.document.file_id if message.content_type == 'document' else message.photo[-1].file_id
        files_col.insert_one(doc)
        bot.send_message(chat_id, f"✅ تم حفظ: {name}")
        reset_modes(chat_id); show_menu(chat_id)
        return

@bot.callback_query_handler(func=lambda call: call.data.startswith(('rn_', 'rp_', 'dl_', 'mv_', 'err_')))
def handle_callbacks(call):
    chat_id = call.message.chat.id
    action, obj_id = call.data.split('_')
    
    if action == 'err':
        reports_col.insert_one({"file_id": obj_id, "reporter": chat_id, "status": "pending"})
        bot.answer_callback_query(call.id, "✅ تم تسجيل بلاغك.", show_alert=True)
        return

    doc = files_col.find_one({"_id": ObjectId(obj_id)})
    if not doc or not has_permission(chat_id, doc['menu_path']):
        bot.answer_callback_query(call.id, "❌ غير مصرح.", show_alert=True)
        return

    if action == 'dl':
        files_col.delete_one({"_id": ObjectId(obj_id)})
        bot.delete_message(chat_id, call.message.message_id)
        bot.answer_callback_query(call.id, "🗑️ تم الحذف.")
        show_menu(chat_id)
    elif action == 'rn':
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "rename_file"
        action_payload[chat_id] = obj_id
        bot.send_message(chat_id, f"✏️ اكتب الاسم الجديد:")
    elif action == 'rp':
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "replace_file"
        action_payload[chat_id] = obj_id
        bot.send_message(chat_id, f"🔄 أرسل المستند الجديد:")
    elif action == 'mv':
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "move_file_dest"
        action_payload[chat_id] = obj_id
        user_path[chat_id] = []
        show_menu(chat_id)

@bot.message_handler(func=lambda message: True)
def handle_nav(message):
    chat_id = message.chat.id
    text = message.text
    path_str = get_path_string(chat_id)
    
    if text in ["📚 تصفح بوت الدفعة", "🔝 القائمة الرئيسية"]:
        user_path[chat_id] = []
        reset_modes(chat_id)
        show_menu(chat_id)
        return

    if text == "🔙 الرجوع للقائمة السابقة":
        if chat_id in user_path and user_path[chat_id]: user_path[chat_id].pop()
        show_menu(chat_id)
        return

    # إصلاح شامل لاستدعاء الملفات بناءً على الآيقونة الدقيقة
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
    return "System Operational 🚀", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
