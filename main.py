import telebot
from pymongo import MongoClient
from flask import Flask, request
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
import sys
import io

# حل مشكلة الترميز
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
    print("Connected to MongoDB Atlas successfully! 🎉")
except Exception as e:
    print(f"MongoDB connection error: {e}")

# تهيئة المشرفين الأساسيين إذا كانت قاعدة البيانات فارغة في أول تشغيل
if admins_col.count_documents({}) == 0:
    initial_admins = [{"id": SUPER_ADMIN_ID}, {"id": 5585934059}, {"id": 1084564343}, {"id": 8545242147}]
    admins_col.insert_many(initial_admins)

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)

# 📌 الهيكل الأكاديمي الأساسي
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
admin_action_mode = {}  # وضع إدارة المشرفين (add أو remove)

def is_admin(chat_id):
    return admins_col.find_one({"id": chat_id}) is not None

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

def show_menu(chat_id):
    path = user_path.get(chat_id, [])
    current_menu = get_menu_by_path(path)
    path_str = get_path_string(chat_id)
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    if not path:
        for key in ACADEMIC_STRUCTURE.keys():
            markup.add(KeyboardButton(key))
        markup.add("👨‍💻 تواصل مع المطور")
        
        # صلاحيات المدير الأعلى (الواثق فقط)
        if chat_id == SUPER_ADMIN_ID and not testing_mode.get(chat_id):
            markup.add("📢 إرسال رسالة جماعية", "👥 إحصائيات المشتركين")
            markup.add("🛠️ إدارة المشرفين")
            
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
        icon = "📝" if f.get("type") == "text" else "🖼️" if f.get("type") == "photo" else "📄"
        markup.add(KeyboardButton(f"{icon} {f['name']}"))

    markup.add("🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية")
    
    # خيارات المشرفين العامة في الأقسام
    if testing_mode.get(chat_id):
        markup.add("🛑 إنهاء التجربة والعودة للإشراف")
    elif is_admin(chat_id):
        markup.add("👤 تجربة كمستخدم", "➕ إضافة ملف أو نص", "📂 إضافة مجلد جديد")
        markup.add("🗑️ تفريغ هذا القسم")

    msg_text = f"📂 القسم الحالي: {path_str}\n\nاختر من القائمة أدناه:"
    bot.send_message(chat_id, msg_text, reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_data = {
        "chat_id": chat_id,
        "first_name": message.from_user.first_name,
        "username": f"@{message.from_user.username}" if message.from_user.username else "لا يوجد معرف"
    }
    users_col.update_one({"chat_id": chat_id}, {"$set": user_data}, upsert=True)
    
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
        msg_dev = (
            "👋 مرحباً بك في قسم الدعم الفني والتطوير الأكاديمي!\n\n"
            "💬 للتواصل مع طاقم الإشراف مباشرة عبر الحسابات الرسمية أدناه:\n\n"
            "👔 المندوب العام للدفعة:\n🔹 الواثق بالله عساج ⇦ (@AlwatheqAssag)\n\n"
            "🛠️ فريق الدعم الفني والبرمجي:\n🔹 جلال المهدي ⇦ (@jalal_almahdy)\n🔹 براء حسن ⇦ (@br44ai)\n🔹 ليث مرزوق ⇦ (@laithmarzoq1)\n"
        )
        bot.send_message(chat_id, msg_dev)
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

# 👑 خصائص المدير الأعلى (الواثق)
@bot.message_handler(func=lambda m: m.chat.id == SUPER_ADMIN_ID and m.text in ["📢 إرسال رسالة جماعية", "👥 إحصائيات المشتركين", "🛠️ إدارة المشرفين", "➕ إضافة مشرف", "➖ إزالة مشرف"])
def super_admin_controls(message):
    chat_id = message.chat.id
    text = message.text

    if text == "👥 إحصائيات المشتركين":
        users = list(users_col.find())
        msg = f"📊 إحصائيات البوت الحصرية:\n👥 إجمالي عدد الطلاب المشتركين: {len(users)}\n\n"
        for u in users:
            msg += f"👤 {u.get('first_name', 'مجهول')} | {u.get('username', 'لا يوجد')} | ID: {u.get('chat_id')}\n"
        if len(msg) > 4000:
            with io.StringIO(msg) as f:
                f.name = "Students_Data.txt"
                bot.send_document(chat_id, f, caption="البيانات كاملة في هذا الملف لكثرة العدد.")
        else:
            bot.send_message(chat_id, msg)

    elif text == "📢 إرسال رسالة جماعية":
        reset_modes(chat_id)
        broadcast_mode[chat_id] = True
        markup = ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")
        bot.send_message(chat_id, "📢 وضع الإرسال الجماعي مُفعّل!\nأرسل الآن الرسالة أو الملف وسيتم توزيعه على الجميع 🚀", reply_markup=markup)

    elif text == "🛠️ إدارة المشرفين":
        reset_modes(chat_id)
        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2).add("➕ إضافة مشرف", "➖ إزالة مشرف", "🔝 القائمة الرئيسية")
        
        current_admins = list(admins_col.find())
        msg = "🛠️ **قائمة المشرفين الحاليين:**\n"
        for a in current_admins:
            msg += f"🔹 ID: {a['id']}\n"
        msg += "\nاختر الإجراء المطلوب من القائمة أدناه:"
        bot.send_message(chat_id, msg, reply_markup=markup, parse_mode="Markdown")

    elif text == "➕ إضافة مشرف":
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "add"
        markup = ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")
        bot.send_message(chat_id, "أرسل الآن الآيدي (ID) الخاص بالمشرف الجديد ليتم إضافته النظام:", reply_markup=markup)

    elif text == "➖ إزالة مشرف":
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "remove"
        markup = ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")
        bot.send_message(chat_id, "أرسل الآيدي (ID) الخاص بالمشرف الذي تريد إزالته:", reply_markup=markup)

# ⚙️ خصائص المشرفين العامة (للواثق والمشرفين الآخرين)
@bot.message_handler(func=lambda m: is_admin(m.chat.id) and m.text in ["➕ إضافة ملف أو نص", "📂 إضافة مجلد جديد", "🗑️ تفريغ هذا القسم", "👤 تجربة كمستخدم"] and not testing_mode.get(m.chat.id))
def admin_controls(message):
    chat_id = message.chat.id
    text = message.text
    
    if text == "➕ إضافة ملف أو نص":
        reset_modes(chat_id)
        upload_mode[chat_id] = True
        markup = ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")
        bot.send_message(chat_id, "📥 وضع الإضافة مُفعّل!\nأرسل الآن (ملف، صورة، أو حتى رسالة نصية طويلة) ليتم حفظها كزر هنا.", reply_markup=markup)
    
    elif text == "📂 إضافة مجلد جديد":
        reset_modes(chat_id)
        add_folder_mode[chat_id] = True
        markup = ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")
        bot.send_message(chat_id, "📂 أرسل الآن اسم المجلد الجديد ليتم إنشاؤه داخل هذا القسم:", reply_markup=markup)

    elif text == "🗑️ تفريغ هذا القسم":
        path_str = get_path_string(chat_id)
        files_col.delete_many({"menu_path": path_str})
        folders_col.delete_many({"parent_path": path_str})
        bot.send_message(chat_id, "🗑️ تم مسح كافة الملفات والمجلدات من هذا القسم بنجاح!")
        show_menu(chat_id)

    elif text == "👤 تجربة كمستخدم":
        testing_mode[chat_id] = True
        show_menu(chat_id)

# 🚀 استقبال البيانات ومعالجتها (الإرسال الجماعي، المجلدات، الملفات، والمشرفين)
@bot.message_handler(content_types=['text', 'document', 'photo', 'video', 'audio'], func=lambda m: is_admin(m.chat.id) and (upload_mode.get(m.chat.id) or add_folder_mode.get(m.chat.id) or broadcast_mode.get(m.chat.id) or admin_action_mode.get(m.chat.id)))
def handle_inputs(message):
    chat_id = message.chat.id
    path_str = get_path_string(chat_id)

    # معالجة إضافة/إزالة المشرفين
    if admin_action_mode.get(chat_id) and chat_id == SUPER_ADMIN_ID:
        try:
            target_id = int(message.text.strip())
            if admin_action_mode[chat_id] == "add":
                if not is_admin(target_id):
                    admins_col.insert_one({"id": target_id})
                    bot.send_message(chat_id, f"✅ تم إضافة المشرف ({target_id}) بنجاح!")
                else:
                    bot.send_message(chat_id, "⚠️ هذا المشرف موجود بالفعل.")
            elif admin_action_mode[chat_id] == "remove":
                if target_id == SUPER_ADMIN_ID:
                    bot.send_message(chat_id, "❌ لا يمكنك إزالة نفسك (المدير الأعلى)!")
                else:
                    admins_col.delete_one({"id": target_id})
                    bot.send_message(chat_id, f"✅ تم إزالة المشرف ({target_id}) بنجاح!")
            
            reset_modes(chat_id)
            # إعادة إظهار القائمة الرئيسية
            user_path[chat_id] = []
            show_menu(chat_id)
        except ValueError:
            bot.send_message(chat_id, "❌ الرجاء إرسال الآيدي كأرقام فقط (مثال: 123456789)")
        return

    # معالجة الإرسال الجماعي (للواثق فقط)
    if broadcast_mode.get(chat_id) and chat_id == SUPER_ADMIN_ID:
        broadcast_mode[chat_id] = False
        bot.send_message(chat_id, "⏳ جاري التوزيع على الطلاب، الرجاء الانتظار...")
        users = list(users_col.find())
        success = 0
        for u in users:
            try:
                bot.copy_message(u['chat_id'], chat_id, message.message_id)
                success += 1
            except:
                pass
        bot.send_message(chat_id, f"✅ تمت العملية بنجاح! تم إرسال الرسالة إلى {success} طالب.")
        user_path[chat_id] = []
        show_menu(chat_id)
        return

    # معالجة إنشاء المجلدات
    if add_folder_mode.get(chat_id) and message.content_type == 'text':
        folder_name = message.text.strip()
        folders_col.insert_one({"parent_path": path_str, "folder_name": folder_name})
        add_folder_mode[chat_id] = False
        bot.send_message(chat_id, f"✅ تم إنشاء المجلد: {folder_name}")
        show_menu(chat_id)
        return

    # معالجة الرفع (نصوص، ملفات، صور)
    if upload_mode.get(chat_id):
        if message.content_type == 'text':
            title = message.text[:25] + "..." if len(message.text) > 25 else message.text
            files_col.insert_one({"menu_path": path_str, "name": title, "type": "text", "content": message.text})
            bot.send_message(chat_id, f"✅ تم حفظ النص باسم: {title}")
        elif message.content_type == 'document':
            name = message.caption if message.caption else message.document.file_name
            files_col.insert_one({"menu_path": path_str, "name": name, "type": "document", "file_id": message.document.file_id, "caption": message.caption})
            bot.send_message(chat_id, f"✅ تم حفظ الملف: {name}")
        elif message.content_type == 'photo':
            name = message.caption if message.caption else f"صورة توضيحية"
            files_col.insert_one({"menu_path": path_str, "name": name, "type": "photo", "file_id": message.photo[-1].file_id, "caption": message.caption})
            bot.send_message(chat_id, f"✅ تم حفظ الصورة: {name}")

@bot.message_handler(func=lambda message: True)
def handle_navigation(message):
    chat_id = message.chat.id
    text = message.text
    path_str = get_path_string(chat_id)
    
    if chat_id not in user_path:
        user_path[chat_id] = []

    if text.startswith("📄 ") or text.startswith("📝 ") or text.startswith("🖼️ "):
        clean_name = text[3:] 
        res = files_col.find_one({"menu_path": path_str, "name": clean_name})
        if res:
            if res['type'] == 'text':
                bot.send_message(chat_id, res['content'])
            elif res['type'] == 'photo':
                bot.send_photo(chat_id, res['file_id'], caption=res.get('caption'))
            else:
                bot.send_document(chat_id, res['file_id'], caption=res.get('caption'))
        return

    if text.startswith("📁 "):
        folder_name = text.replace("📁 ", "")
        user_path[chat_id].append(folder_name)
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
    return "Academic Bot: Super Admin System is Active! 🚀", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
