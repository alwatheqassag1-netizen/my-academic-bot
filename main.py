import telebot
from pymongo import MongoClient
from flask import Flask, request
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
import sys
import io

if sys.version_info >= (3, 0):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_TOKEN = '7524289470:AAGkeX96s1s6saxGP3uy14MN9it19nKn10A'

# 👑 حساب المدير الأعلى (الواثق) لخيارات الإحصائيات الحصرية
SUPER_ADMIN_ID = 6842543527
# 👥 قائمة المشرفين 
ADMIN_IDS = [6842543527, 5585934059, 1084564343, 8545242147] 

MONGO_URI = "mongodb+srv://Alwatheq:alwatheq73@cluster0.ft0mdkt.mongodb.net/?appName=Cluster0"

try:
    client = MongoClient(MONGO_URI)
    db = client['academic_bot_db']
    files_col = db['uploaded_files']
    folders_col = db['dynamic_folders'] # قاعدة بيانات جديدة للمجلدات
    users_col = db['bot_users']
    print("Connected to MongoDB Atlas successfully! 🎉")
except Exception as e:
    print(f"MongoDB connection error: {e}")

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

def show_menu(chat_id):
    path = user_path.get(chat_id, [])
    current_menu = get_menu_by_path(path)
    path_str = get_path_string(chat_id)
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # 1. عرض القائمة الرئيسية وميزاتها الإدارية
    if not path:
        for key in ACADEMIC_STRUCTURE.keys():
            markup.add(KeyboardButton(key))
        markup.add("👨‍💻 تواصل مع المطور")
        
        # ميزات الإدارة في القائمة الرئيسية
        if chat_id in ADMIN_IDS and not testing_mode.get(chat_id):
            markup.add("📢 إرسال رسالة جماعية (لكل المشتركين)")
        if chat_id == SUPER_ADMIN_ID and not testing_mode.get(chat_id):
            markup.add("👥 إحصائيات المشتركين")
            
        msg_text = "مرحباً بك في المنصة الأكاديمية لقسم الذكاء الاصطناعي وعلوم البيانات (الدفعة الثانية) 🎓\n\n👇 فضلاً، اختر من القائمة أدناه للبدء:"
        bot.send_message(chat_id, msg_text, reply_markup=markup)
        return

    # 2. عرض المجلدات الأساسية
    if isinstance(current_menu, dict):
        for key in current_menu.keys():
            markup.add(KeyboardButton(key))
            
    # 3. عرض المجلدات الديناميكية (التي يضيفها المشرفون)
    dynamic_folders = list(folders_col.find({"parent_path": path_str}))
    for df in dynamic_folders:
        markup.add(KeyboardButton(f"📁 {df['folder_name']}"))

    # 4. عرض الملفات والنصوص المرفوعة
    db_files = list(files_col.find({"menu_path": path_str}))
    for f in db_files:
        icon = "📝" if f.get("type") == "text" else "🖼️" if f.get("type") == "photo" else "📄"
        markup.add(KeyboardButton(f"{icon} {f['name']}"))

    markup.add("🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية")
    
    # 5. خيارات التحكم داخل الأقسام
    if testing_mode.get(chat_id):
        markup.add("🛑 إنهاء التجربة والعودة للإشراف")
    elif chat_id in ADMIN_IDS:
        markup.add("👤 تجربة كمستخدم", "➕ إضافة ملف أو نص", "📂 إضافة مجلد جديد")
        markup.add("🗑️ تفريغ هذا القسم")

    msg_text = f"📂 القسم الحالي: {path_str}\n\nاختر من القائمة أدناه:"
    bot.send_message(chat_id, msg_text, reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    # حفظ بيانات الطالب للإحصائيات الحصرية
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

@bot.message_handler(func=lambda m: m.text in ["🛑 إلغاء الأمر", "🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية", "🛑 إنهاء التجربة والعودة للإشراف", "👨‍💻 تواصل مع المطور", "📢 إرسال رسالة جماعية (لكل المشتركين)", "👥 إحصائيات المشتركين"])
def handle_control_buttons(message):
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

    # ميزة الإحصائيات (مخصصة للواثق فقط)
    elif text == "👥 إحصائيات المشتركين" and chat_id == SUPER_ADMIN_ID:
        users = list(users_col.find())
        msg = f"📊 إحصائيات البوت الحصرية:\n👥 إجمالي عدد الطلاب المشتركين: {len(users)}\n\n"
        for u in users:
            msg += f"👤 {u.get('first_name', 'مجهول')} | {u.get('username', 'لا يوجد')}\n"
        
        # إرسال كملف إذا كان النص طويلاً جداً
        if len(msg) > 4000:
            with io.StringIO(msg) as f:
                f.name = "Students_Data.txt"
                bot.send_document(chat_id, f, caption="البيانات كاملة في هذا الملف لكثرة العدد.")
        else:
            bot.send_message(chat_id, msg)

    # ميزة الإرسال الجماعي
    elif text == "📢 إرسال رسالة جماعية (لكل المشتركين)" and chat_id in ADMIN_IDS:
        reset_modes(chat_id)
        broadcast_mode[chat_id] = True
        markup = ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")
        bot.send_message(chat_id, "📢 وضع الإرسال الجماعي مُفعّل!\n\nأرسل الآن الرسالة، أو الصورة، أو الملف الذي تريد توزيعه على جميع الطلاب...\nسيتم نشره فوراً 🚀", reply_markup=markup)

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

@bot.message_handler(func=lambda m: m.chat.id in ADMIN_IDS and m.text in ["➕ إضافة ملف أو نص", "📂 إضافة مجلد جديد", "🗑️ تفريغ هذا القسم", "👤 تجربة كمستخدم"] and not testing_mode.get(m.chat.id))
def admin_controls(message):
    chat_id = message.chat.id
    text = message.text
    
    if text == "➕ إضافة ملف أو نص":
        reset_modes(chat_id)
        upload_mode[chat_id] = True
        markup = ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")
        bot.send_message(chat_id, "📥 وضع الإضافة مُفعّل!\nأرسل الآن (ملف، صورة، أو حتى رسالة نصية طويلة) ليتم حفظها كزر هنا.\nللنصوص: سيأخذ البوت أول كلمات كعنوان للزر.", reply_markup=markup)
    
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

# 🚀 استقبال كل أنواع البيانات (ملفات، نصوص، صور، مجلدات، وإرسال جماعي)
@bot.message_handler(content_types=['text', 'document', 'photo', 'video', 'audio'], func=lambda m: m.chat.id in ADMIN_IDS and (upload_mode.get(m.chat.id) or add_folder_mode.get(m.chat.id) or broadcast_mode.get(m.chat.id)))
def handle_inputs(message):
    chat_id = message.chat.id
    path_str = get_path_string(chat_id)

    # 1. معالجة الإرسال الجماعي (Broadcast)
    if broadcast_mode.get(chat_id):
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
        show_menu(chat_id)
        return

    # 2. معالجة إنشاء المجلدات
    if add_folder_mode.get(chat_id) and message.content_type == 'text':
        folder_name = message.text.strip()
        folders_col.insert_one({"parent_path": path_str, "folder_name": folder_name})
        add_folder_mode[chat_id] = False
        bot.send_message(chat_id, f"✅ تم إنشاء المجلد: {folder_name}")
        show_menu(chat_id)
        return

    # 3. معالجة الرفع (ملفات أو نصوص أو صور)
    if upload_mode.get(chat_id):
        if message.content_type == 'text':
            title = message.text[:25] + "..." if len(message.text) > 25 else message.text
            files_col.insert_one({"menu_path": path_str, "name": title, "type": "text", "content": message.text})
            bot.send_message(chat_id, f"✅ تم حفظ النص، وسيظهر كزر باسم: {title}")
            
        elif message.content_type == 'document':
            name = message.caption if message.caption else message.document.file_name
            files_col.insert_one({"menu_path": path_str, "name": name, "type": "document", "file_id": message.document.file_id, "caption": message.caption})
            bot.send_message(chat_id, f"✅ تم حفظ الملف: {name}")
            
        elif message.content_type == 'photo':
            name = message.caption if message.caption else f"صورة توضيحية"
            files_col.insert_one({"menu_path": path_str, "name": name, "type": "photo", "file_id": message.photo[-1].file_id, "caption": message.caption})
            bot.send_message(chat_id, f"✅ تم حفظ الصورة: {name}")
        
        # لضمان استمرار الرفع المتعدد
        # upload_mode[chat_id] يبقى True حتى يضغط المشرف "إلغاء الأمر"

@bot.message_handler(func=lambda message: True)
def handle_navigation(message):
    chat_id = message.chat.id
    text = message.text
    path_str = get_path_string(chat_id)
    
    if chat_id not in user_path:
        user_path[chat_id] = []

    # إذا ضغط على زر لملف أو نص
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

    # إذا ضغط على زر لمجلد ديناميكي
    if text.startswith("📁 "):
        folder_name = text.replace("📁 ", "")
        user_path[chat_id].append(folder_name)
        show_menu(chat_id)
        return

    # التنقل في المجلدات الأساسية
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
    return "Academic Bot is fully featured and perfectly stable! 🚀", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
