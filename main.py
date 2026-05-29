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
SUPER_ADMIN_ID = 6842543527  # الآيدي الخاص بالواثق (المدير الأعلى)

MONGO_URI = "mongodb+srv://Alwatheq:alwatheq73@cluster0.ft0mdkt.mongodb.net/?appName=Cluster0"

try:
    client = MongoClient(MONGO_URI)
    db = client['academic_bot_db']
    files_col = db['uploaded_files']
    folders_col = db['dynamic_folders']
    users_col = db['bot_users']
    admins_col = db['admins_list']
    settings_col = db['bot_settings']
    alerts_col = db['scheduled_alerts'] # قاعدة بيانات التنبيهات المجدولة
    print("Connected to MongoDB Atlas successfully! 🎉")
except Exception as e:
    print(f"MongoDB connection error: {e}")

if admins_col.count_documents({}) == 0:
    initial_admins = [{"id": SUPER_ADMIN_ID}, {"id": 8545242147}]
    admins_col.insert_many(initial_admins)

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

user_path = {}  
upload_mode = {}
add_folder_mode = {}
broadcast_mode = {}
testing_mode = {}
admin_action_mode = {}
action_payload = {}
temp_alert_data = {}

def is_admin(chat_id):
    return admins_col.find_one({"id": chat_id}) is not None

def is_bot_active():
    setting = settings_col.find_one()
    return setting.get("status") == "active" if setting else True

def get_menu_by_path(path):
    menu = ACADEMIC_STRUCTURE
    for p in path:
        if isinstance(menu, dict) and p in menu:
            menu = menu[p]
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

# 🕒 محرك إرسال التنبيهات المجدولة في الخلفية
def alert_checker_thread():
    while True:
        try:
            # توقيت اليمن (UTC +3)
            now_yemen = datetime.utcnow() + timedelta(hours=3)
            current_time_str = now_yemen.strftime("%Y-%m-%d %H:%M")
            
            due_alerts = list(alerts_col.find({"status": "pending", "send_time": current_time_str}))
            for alert in due_alerts:
                users = list(users_col.find())
                success_count = 0
                for u in users:
                    try:
                        bot.send_message(u['chat_id'], f"🔔 *تنبيه أكاديمي مجدول:*\n\n{alert['message']}", parse_mode="Markdown")
                        success_count += 1
                    except:
                        pass
                alerts_col.update_one({"_id": alert['_id']}, {"$set": {"status": "sent", "reached": success_count}})
        except Exception as e:
            print(f"Scheduler Error: {e}")
        time.sleep(45)

threading.Thread(target=alert_checker_thread, daemon=True).start()

@bot.message_handler(func=lambda m: not is_bot_active() and m.chat.id != SUPER_ADMIN_ID)
def system_offline(message):
    bot.send_message(message.chat.id, "⛔ المنصة الأكاديمية مغلقة حالياً للصيانة بقرار من الإدارة العليا. يرجى المحاولة لاحقاً.")

def show_menu(chat_id):
    path = user_path.get(chat_id, [])
    current_menu = get_menu_by_path(path)
    path_str = get_path_string(chat_id)
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    if not path:
        for key in ACADEMIC_STRUCTURE.keys():
            markup.add(KeyboardButton(key))
        markup.add("👨‍💻 تواصل مع المطور")
        
        if chat_id == SUPER_ADMIN_ID and not testing_mode.get(chat_id):
            markup.add("📢 إرسال رسالة جماعية", "👥 إحصائيات المشتركين")
            markup.add("⏰ التنبيهات المجدولة", "🛠️ إدارة المشرفين")
            markup.add("⚙️ زر الأمان (إغلاق البوت)")
            
        msg_text = "مرحباً بك في المنصة الأكاديمية لقسم الذكاء الاصطناعي وعلوم البيانات (الدفعة الثانية) 🎓\n\n👇 فضلاً، اختر من القائمة أدناه للبدء:"
        bot.send_message(chat_id, msg_text, reply_markup=markup)
        return

    if isinstance(current_menu, dict):
        for key in current_menu.keys():
            markup.add(KeyboardButton(key))
            
    dynamic_folders = list(folders_col.find({"parent_path": path_str}))
    for df in dynamic_folders:
        markup.add(KeyboardButton(f"📁 {df['folder_name']}"))

    db_files = list(files_col.find({"menu_path": path_str}))
    for f in db_files:
        icon = "📌" if f.get("type") == "text" else "🖼️" if f.get("type") == "photo" else "📄"
        markup.add(KeyboardButton(f"{icon} {f['name']}"))

    markup.add("🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية")
    
    if testing_mode.get(chat_id):
        markup.add("🛑 إنهاء التجربة والعودة للإشراف")
    elif is_admin(chat_id):
        markup.add("👤 تجربة كمستخدم", "➕ إضافة ملف أو نص", "📂 إضافة مجلد جديد")
        markup.add("🗑️ تفريغ هذا القسم")

    msg_text = f"📂 القسم الحالي: {path_str}\n\nاختر من القائمة أدناه:"
    bot.send_message(chat_id, msg_text, reply_markup=markup)

def send_file_to_user(chat_id, res, user_is_admin):
    # إنشاء أزرار للملف
    markup = InlineKeyboardMarkup(row_width=2)
    file_id_str = str(res['_id'])
    share_url = f"https://t.me/{BOT_USERNAME}?start={file_id_str}"
    
    if user_is_admin and not testing_mode.get(chat_id):
        markup.add(
            InlineKeyboardButton("✏️ تعديل الاسم", callback_data=f"rn_{file_id_str}"),
            InlineKeyboardButton("🔄 استبدال الملف", callback_data=f"rp_{file_id_str}")
        )
        markup.add(InlineKeyboardButton("🗑️ حذف الملف", callback_data=f"dl_{file_id_str}"))
        markup.add(InlineKeyboardButton("🔗 رابط مباشر (للمشاركة)", url=f"https://t.me/share/url?url={share_url}"))
    else:
        markup.add(InlineKeyboardButton("🔗 شارك هذا الملف مع زملائك", url=f"https://t.me/share/url?url={share_url}"))

    # إرسال الملف بناءً على نوعه
    if res['type'] == 'text':
        bot.send_message(chat_id, res['content'], reply_markup=markup)
    elif res['type'] == 'photo':
        bot.send_photo(chat_id, res['file_id'], caption=res.get('caption', res['name']), reply_markup=markup)
    else:
        bot.send_document(chat_id, res['file_id'], caption=res.get('caption', res['name']), reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    
    # التحقق من الروابط العميقة (Deep Links)
    parts = message.text.split()
    if len(parts) > 1:
        file_id_str = parts[1]
        try:
            res = files_col.find_one({"_id": ObjectId(file_id_str)})
            if res:
                bot.send_message(chat_id, "📥 جاري إحضار الملف...")
                send_file_to_user(chat_id, res, is_admin(chat_id))
                return
        except Exception:
            bot.send_message(chat_id, "❌ الملف غير موجود أو تم حذفه.")
    
    # تحديث بيانات المستخدم
    user_data = {
        "chat_id": chat_id,
        "first_name": message.from_user.first_name,
        "username": f"@{message.from_user.username}" if message.from_user.username else "لا يوجد معرف"
    }
    users_col.update_one({"chat_id": chat_id}, {"$set": user_data}, upsert=True)
    
    # الشاشة الرئيسية الأولى
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📚 تصفح بوت الدفعة")
    if chat_id == SUPER_ADMIN_ID:
        markup.add("⚙️ الدخول للوحة الإدارة")
        
    welcome_text = "أهلاً بك في المنصة الأكاديمية الذكية 🎓\n\nاضغط على الزر بالأسفل لاستعراض المواد والمحاضرات."
    bot.send_message(chat_id, welcome_text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text in ["📚 تصفح بوت الدفعة", "⚙️ الدخول للوحة الإدارة"])
def enter_main_menu(message):
    chat_id = message.chat.id
    user_path[chat_id] = []
    reset_modes(chat_id)
    testing_mode[chat_id] = False
    show_menu(chat_id)

@bot.message_handler(func=lambda m: m.text in ["🛑 إلغاء الأمر", "🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية", "🛑 إنهاء التجربة والعودة للإشراف", "👨‍💻 تواصل مع المطور"])
def handle_general_buttons(message):
    chat_id = message.chat.id
    text = message.text
    
    if text == "🛑 إلغاء الأمر":
        reset_modes(chat_id)
        bot.send_message(chat_id, "تم إلغاء الإجراء الحالي ⚙️")
        show_menu(chat_id)
    elif text == "👨‍💻 تواصل مع المطور":
        bot.send_message(chat_id, "👋 مرحباً بك في قسم الدعم الفني...\n🔹 الواثق بالله عساج ⇦ (@AlwatheqAssag)\n🔹 جلال المهدي ⇦ (@jalal_almahdy)\n🔹 براء حسن ⇦ (@br44ai)\n🔹 ليث مرزوق ⇦ (@laithmarzoq1)")
    elif text == "🛑 إنهاء التجربة والعودة للإشراف":
        testing_mode[chat_id] = False
        show_menu(chat_id)
    elif text == "🔝 القائمة الرئيسية":
        user_path[chat_id] = []
        reset_modes(chat_id)
        show_menu(chat_id)
    elif text == "🔙 الرجوع للقائمة السابقة":
        if chat_id in user_path and user_path[chat_id]:
            user_path[chat_id].pop()
        reset_modes(chat_id)
        show_menu(chat_id)

@bot.message_handler(func=lambda m: m.chat.id == SUPER_ADMIN_ID and m.text == "⚙️ زر الأمان (إغلاق البوت)")
def security_panel(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    status_btn = "▶️ تشغيل البوت" if not is_bot_active() else "⏸️ إيقاف البوت"
    markup.add(status_btn, "🔝 القائمة الرئيسية")
    bot.send_message(message.chat.id, "🛡️ أهلاً بك في غرفة الأمان العُليا:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.chat.id == SUPER_ADMIN_ID and m.text in ["▶️ تشغيل البوت", "⏸️ إيقاف البوت"])
def execute_security_actions(message):
    chat_id = message.chat.id
    if message.text == "⏸️ إيقاف البوت":
        settings_col.update_one({}, {"$set": {"status": "inactive"}})
        bot.send_message(chat_id, "⛔ تم إغلاق النظام وحظر الجميع.")
        show_menu(chat_id)
    elif message.text == "▶️ تشغيل البوت":
        settings_col.update_one({}, {"$set": {"status": "active"}})
        bot.send_message(chat_id, "✅ تم تفعيل النظام وعاد للعمل.")
        show_menu(chat_id)

@bot.message_handler(func=lambda m: m.chat.id == SUPER_ADMIN_ID and m.text in ["📢 إرسال رسالة جماعية", "👥 إحصائيات المشتركين", "🛠️ إدارة المشرفين", "➕ إضافة مشرف", "➖ إزالة مشرف", "⏰ التنبيهات المجدولة", "➕ إضافة تنبيه", "📋 عرض وحذف التنبيهات"])
def super_admin_controls(message):
    chat_id = message.chat.id
    text = message.text

    if text == "👥 إحصائيات المشتركين":
        users = list(users_col.find())
        msg = f"📊 إحصائيات البوت:\n👥 الإجمالي: {len(users)}\n\n"
        for u in users: msg += f"👤 {u.get('first_name')} | {u.get('username')} | ID: {u.get('chat_id')}\n"
        if len(msg) > 4000:
            with io.StringIO(msg) as f:
                f.name = "Students_Data.txt"
                bot.send_document(chat_id, f)
        else: bot.send_message(chat_id, msg)

    elif text == "📢 إرسال رسالة جماعية":
        reset_modes(chat_id)
        broadcast_mode[chat_id] = True
        bot.send_message(chat_id, "📢 وضع الإرسال الجماعي مُفعّل! أرسل رسالتك:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))

    elif text == "🛠️ إدارة المشرفين":
        reset_modes(chat_id)
        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2).add("➕ إضافة مشرف", "➖ إزالة مشرف", "🔝 القائمة الرئيسية")
        msg = "🛠️ **المشرفين الحاليين:**\n"
        for a in list(admins_col.find()): msg += f"🔹 ID: {a['id']}\n"
        bot.send_message(chat_id, msg, reply_markup=markup, parse_mode="Markdown")

    elif text == "➕ إضافة مشرف":
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "add"
        bot.send_message(chat_id, "أرسل الآيدي (ID) الخاص بالمشرف الجديد:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))

    elif text == "➖ إزالة مشرف":
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "remove"
        bot.send_message(chat_id, "أرسل الآيدي (ID) الخاص بالمشرف لإزالته:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))

    elif text == "⏰ التنبيهات المجدولة":
        reset_modes(chat_id)
        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2).add("➕ إضافة تنبيه", "📋 عرض وحذف التنبيهات", "🔝 القائمة الرئيسية")
        bot.send_message(chat_id, "⏰ إدارة التنبيهات المجدولة (رسائل تلقائية تصل للطلاب في الوقت المحدد):", reply_markup=markup)

    elif text == "➕ إضافة تنبيه":
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "alert_msg"
        bot.send_message(chat_id, "📝 أرسل نص التنبيه الذي تريده أن يصل للطلاب:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))

    elif text == "📋 عرض وحذف التنبيهات":
        alerts = list(alerts_col.find({"status": "pending"}))
        if not alerts:
            bot.send_message(chat_id, "لا توجد تنبيهات مجدولة حالياً.")
            return
        for al in alerts:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🗑️ حذف هذا التنبيه", callback_data=f"dela_{str(al['_id'])}"))
            bot.send_message(chat_id, f"📅 الوقت: {al['send_time']}\n💬 النص: {al['message']}", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith(('rn_', 'rp_', 'dl_', 'dela_')))
def handle_inline_callbacks(call):
    chat_id = call.message.chat.id
    if not is_admin(chat_id):
        bot.answer_callback_query(call.id, "❌ لا تملك صلاحية.", show_alert=True)
        return
        
    action, obj_id = call.data.split('_')
    
    if action == 'dela': # حذف التنبيه
        alerts_col.delete_one({"_id": ObjectId(obj_id)})
        bot.delete_message(chat_id, call.message.message_id)
        bot.answer_callback_query(call.id, "✅ تم حذف التنبيه.")
        return

    # عمليات الملفات (تعديل، استبدال، حذف)
    try:
        doc = files_col.find_one({"_id": ObjectId(obj_id)})
        if not doc:
            bot.answer_callback_query(call.id, "❌ الملف غير موجود.", show_alert=True)
            return

        if action == 'dl': # حذف ملف
            files_col.delete_one({"_id": ObjectId(obj_id)})
            bot.delete_message(chat_id, call.message.message_id)
            bot.answer_callback_query(call.id, "✅ تم حذف الملف بنجاح.")
            show_menu(chat_id)
            
        elif action == 'rn': # تعديل اسم
            reset_modes(chat_id)
            admin_action_mode[chat_id] = "rename_file"
            action_payload[chat_id] = obj_id
            bot.send_message(chat_id, f"✏️ أرسل الاسم الجديد لـ:\n{doc['name']}", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            bot.answer_callback_query(call.id)
            
        elif action == 'rp': # استبدال ملف
            reset_modes(chat_id)
            admin_action_mode[chat_id] = "replace_file"
            action_payload[chat_id] = obj_id
            bot.send_message(chat_id, f"🔄 أرسل الملف الجديد ليحل محل:\n{doc['name']}", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            bot.answer_callback_query(call.id)
    except Exception as e:
        bot.answer_callback_query(call.id, "❌ حدث خطأ داخلي.")

@bot.message_handler(func=lambda m: is_admin(m.chat.id) and m.text in ["➕ إضافة ملف أو نص", "📂 إضافة مجلد جديد", "🗑️ تفريغ هذا القسم", "👤 تجربة كمستخدم"] and not testing_mode.get(m.chat.id))
def admin_controls(message):
    chat_id = message.chat.id
    if message.text == "➕ إضافة ملف أو نص":
        reset_modes(chat_id)
        upload_mode[chat_id] = True
        bot.send_message(chat_id, "📥 وضع الإضافة مُفعّل! أرسل الملف أو النص:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
    elif message.text == "📂 إضافة مجلد جديد":
        reset_modes(chat_id)
        add_folder_mode[chat_id] = True
        bot.send_message(chat_id, "📂 أرسل اسم المجلد الجديد:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
    elif message.text == "🗑️ تفريغ هذا القسم":
        files_col.delete_many({"menu_path": get_path_string(chat_id)})
        folders_col.delete_many({"parent_path": get_path_string(chat_id)})
        bot.send_message(chat_id, "🗑️ تم المسح بنجاح!")
        show_menu(chat_id)
    elif message.text == "👤 تجربة كمستخدم":
        testing_mode[chat_id] = True
        show_menu(chat_id)

@bot.message_handler(content_types=['text', 'document', 'photo', 'video', 'audio'], func=lambda m: is_admin(m.chat.id) and (upload_mode.get(m.chat.id) or add_folder_mode.get(m.chat.id) or broadcast_mode.get(m.chat.id) or admin_action_mode.get(m.chat.id)))
def handle_inputs(message):
    chat_id = message.chat.id
    path_str = get_path_string(chat_id)
    mode = admin_action_mode.get(chat_id)

    # 1. إعداد التنبيهات المجدولة
    if mode == "alert_msg" and message.content_type == 'text':
        temp_alert_data[chat_id] = message.text
        admin_action_mode[chat_id] = "alert_time"
        bot.send_message(chat_id, "⏰ ممتاز. الآن أرسل وقت التنبيه (بتوقيت اليمن) بالصيغة التالية بالضبط:\n\n`2026-05-30 14:30`\n\n(السنة-الشهر-اليوم الساعة:الدقيقة)", parse_mode="Markdown")
        return
        
    if mode == "alert_time" and message.content_type == 'text':
        try:
            time_format = "%Y-%m-%d %H:%M"
            datetime.strptime(message.text.strip(), time_format) # تحقق من صحة الصيغة
            alerts_col.insert_one({
                "message": temp_alert_data[chat_id],
                "send_time": message.text.strip(),
                "status": "pending"
            })
            bot.send_message(chat_id, f"✅ تم حفظ التنبيه وسيُرسل في الوقت المحدد: {message.text.strip()}")
            reset_modes(chat_id)
            show_menu(chat_id)
        except ValueError:
            bot.send_message(chat_id, "❌ صيغة الوقت خاطئة! يرجى إعادة كتابتها هكذا:\n2026-05-30 14:30")
        return

    # 2. تعديل اسم ملف
    if mode == "rename_file" and message.content_type == 'text':
        obj_id = action_payload.get(chat_id)
        files_col.update_one({"_id": ObjectId(obj_id)}, {"$set": {"name": message.text.strip()}})
        bot.send_message(chat_id, "✅ تم تغيير الاسم بنجاح.")
        reset_modes(chat_id)
        show_menu(chat_id)
        return

    # 3. استبدال ملف (بملف جديد)
    if mode == "replace_file":
        obj_id = action_payload.get(chat_id)
        if message.content_type == 'document':
            name = message.caption if message.caption else message.document.file_name
            files_col.update_one({"_id": ObjectId(obj_id)}, {"$set": {"type": "document", "file_id": message.document.file_id, "name": name, "caption": message.caption}})
            bot.send_message(chat_id, "✅ تم استبدال الملف بنجاح.")
        elif message.content_type == 'photo':
            name = message.caption if message.caption else "صورة توضيحية"
            files_col.update_one({"_id": ObjectId(obj_id)}, {"$set": {"type": "photo", "file_id": message.photo[-1].file_id, "name": name, "caption": message.caption}})
            bot.send_message(chat_id, "✅ تم استبدال الصورة بنجاح.")
        elif message.content_type == 'text':
            files_col.update_one({"_id": ObjectId(obj_id)}, {"$set": {"type": "text", "content": message.text, "name": message.text[:25] + "..."}})
            bot.send_message(chat_id, "✅ تم استبدال النص بنجاح.")
        reset_modes(chat_id)
        show_menu(chat_id)
        return

    # 4. أوامر المشرفين (إضافة أو حذف مشرفين)
    if mode in ["add", "remove"] and chat_id == SUPER_ADMIN_ID:
        try:
            target_id = int(message.text.strip())
            if mode == "add":
                if not is_admin(target_id):
                    admins_col.insert_one({"id": target_id})
                    bot.send_message(chat_id, f"✅ تمت الإضافة: {target_id}")
            elif mode == "remove":
                if target_id != SUPER_ADMIN_ID:
                    admins_col.delete_one({"id": target_id})
                    bot.send_message(chat_id, f"✅ تمت الإزالة: {target_id}")
            reset_modes(chat_id)
            user_path[chat_id] = []
            show_menu(chat_id)
        except ValueError:
            bot.send_message(chat_id, "❌ خطأ: أرسل الآيدي كأرقام فقط")
        return

    # 5. الإرسال الجماعي (Broadcast)
    if broadcast_mode.get(chat_id) and chat_id == SUPER_ADMIN_ID:
        broadcast_mode[chat_id] = False
        users = list(users_col.find())
        success = 0
        for u in users:
            try:
                bot.copy_message(u['chat_id'], chat_id, message.message_id)
                success += 1
            except: pass
        bot.send_message(chat_id, f"✅ تم الإرسال إلى {success} طالب.")
        user_path[chat_id] = []
        show_menu(chat_id)
        return

    # 6. إنشاء مجلد
    if add_folder_mode.get(chat_id) and message.content_type == 'text':
        folders_col.insert_one({"parent_path": path_str, "folder_name": message.text.strip()})
        add_folder_mode[chat_id] = False
        bot.send_message(chat_id, "✅ تم إنشاء المجلد.")
        show_menu(chat_id)
        return

    # 7. رفع ملف جديد
    if upload_mode.get(chat_id):
        if message.content_type == 'text':
            title = message.text[:25] + "..." if len(message.text) > 25 else message.text
            files_col.insert_one({"menu_path": path_str, "name": title, "type": "text", "content": message.text})
            bot.send_message(chat_id, f"✅ تم الحفظ: {title}")
        elif message.content_type == 'document':
            # 💡 السحب الذكي للاسم (من الوصف أو من الملف الأصلي)
            name = message.caption if message.caption else message.document.file_name
            files_col.insert_one({"menu_path": path_str, "name": name, "type": "document", "file_id": message.document.file_id, "caption": message.caption})
            bot.send_message(chat_id, f"✅ تم الحفظ: {name}")
        elif message.content_type == 'photo':
            name = message.caption if message.caption else "صورة توضيحية"
            files_col.insert_one({"menu_path": path_str, "name": name, "type": "photo", "file_id": message.photo[-1].file_id, "caption": message.caption})
            bot.send_message(chat_id, f"✅ تم الحفظ: {name}")

@bot.message_handler(func=lambda message: True)
def handle_navigation(message):
    chat_id = message.chat.id
    text = message.text
    path_str = get_path_string(chat_id)
    
    if chat_id not in user_path:
        user_path[chat_id] = []

    # عند اختيار المشرف/الطالب لملف معين
    if text.startswith("📄 ") or text.startswith("📌 ") or text.startswith("🖼️ "):
        clean_name = text.replace("📄 ", "").replace("📌 ", "").replace("🖼️ ", "")
        res = files_col.find_one({"menu_path": path_str, "name": clean_name})
        if res:
            send_file_to_user(chat_id, res, is_admin(chat_id))
        return

    if text.startswith("📁 "):
        user_path[chat_id].append(text.replace("📁 ", ""))
        show_menu(chat_id)
        return

    current_menu = get_menu_by_path(user_path[chat_id])
    if isinstance(current_menu, dict) and text in current_menu:
        user_path[chat_id].append(text)
        show_menu(chat_id)

@app.route('/webhook', methods=['POST'])
def getMessage():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "!", 200

@app.route("/")
def webhook():
    return "Academic Bot: Version 3.0 Active! 🚀", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
