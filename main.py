import telebot
from pymongo import MongoClient
from flask import Flask, request
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
import sys
import io

if sys.version_info >= (3, 0):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_TOKEN = '7524289470:AAGkeX96s1s6saxGP3uy14MN9it19nKn10A'
ADMIN_IDS = [6842543527, 5585934059, 1084564343] 

MONGO_URI = "mongodb+srv://Alwatheq:alwatheq73@cluster0.ft0mdkt.mongodb.net/?appName=Cluster0"

try:
    client = MongoClient(MONGO_URI)
    db = client['academic_bot_db']
    files_col = db['uploaded_files']
    users_col = db['bot_users']
    print("Connected to MongoDB Atlas successfully! 🎉")
except Exception as e:
    print(f"MongoDB connection error: {e}")

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)

# 📌 الهيكل الأكاديمي الثابت والمنظم بنظام المجلدات
ACADEMIC_STRUCTURE = {
    "🌱 مستوى أول": {
        "📅 ترم أول": {},
        "📅 ترم ثاني": {
            "🕋 الثقافة الإسلامية": {
                "📁 محاضرات وملخصات": {},
                "📝 نماذج اختبارات": {}
            },
            "📚 لغة عربية 2": {
                "📁 محاضرات وملخصات": {},
                "📝 نماذج اختبارات": {}
            },
            "🇬🇧 لغة إنجليزية 2": {
                "📁 محاضرات وملخصات": {},
                "📝 نماذج اختبارات": {}
            },
            "📈 تفاضل وتكامل 2": {
                "📂 محاضرات نظري": {},
                "📐 محاضرات تمارين": {},
                "📝 نماذج اختبارات نظري": {},
                "✍️ نماذج تمارين": {},
                "📚 مراجع خارجية": {}
            },
            "📊 مقدمة في علوم البيانات": {
                "👨‍🏫 محاضرات المهندس": {},
                "📜 ملخص محاضرات": {},
                "⚙️ محاضرات العملي": {},
                "📝 نماذج اختبارات نظري": {}
            },
            "💻 برمجة حاسوب": {
                "📂 محاضرات نظري": {},
                "🖥️ محاضرات العملي": {},
                "📝 نماذج اختبارات": {},
                "🚀 التمارين والمشاريع العملية": {}
            },
            "🗂️ رياضيات متقطعة": {
                "📂 محاضرات نظري": {},
                "✏️ محاضرات تمارين": {},
                "📝 نماذج اختبارات": {},
                "📚 مراجع خارجية": {}
            }
        }
    },
    "🌿 مستوى ثاني": {"📅 ترم أول": {}, "📅 ترم ثاني": {}},
    "☘️ مستوى ثالث": {"📅 ترم أول": {}, "📅 ترم ثاني": {}},
    "🌳 مستوى رابع": {"📅 ترم أول": {}, "📅 ترم ثاني": {}}
}

user_path = {}  
upload_mode = {}
testing_mode = {}

def get_menu_by_path(path):
    menu = ACADEMIC_STRUCTURE
    for p in path:
        if p in menu:
            menu = menu[p]
        else:
            return None
    return menu

def get_path_string(chat_id):
    return " > ".join(user_path.get(chat_id, []))

def is_final_folder(path):
    menu = get_menu_by_path(path)
    if isinstance(menu, dict) and len(menu) == 0 and len(path) > 2:
        return True
    return False

def show_menu(chat_id):
    path = user_path.get(chat_id, [])
    current_menu = get_menu_by_path(path)
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    if not path:
        for key in ACADEMIC_STRUCTURE.keys():
            markup.add(KeyboardButton(key))
        markup.add("👨‍💻 تواصل مع المشرفين")
        msg_text = (
            "مرحباً بك في المنصة الأكاديمية لقسم الذكاء الاصطناعي وعلوم البيانات (الدفعة الثانية) 🎓\n\n"
            "👇 فضلاً، اختر مستواك الدراسي من القائمة أدناه للبدء:"
        )
        bot.send_message(chat_id, msg_text, reply_markup=markup)
        return

    if isinstance(current_menu, dict):
        for key in current_menu.keys():
            markup.add(KeyboardButton(key))
            
    path_str = get_path_string(chat_id)
    db_files = list(files_col.find({"menu_path": path_str}))
    for f in db_files:
        markup.add(KeyboardButton(f"📄 {f['file_name']}"))

    markup.add("🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية")
    
    if testing_mode.get(chat_id):
        markup.add("🛑 إنهاء التجربة والعودة للإشراف")
    elif chat_id in ADMIN_IDS:
        if is_final_folder(path):
            markup.add("👤 تجربة كمستخدم", "➕ إضافة ملف")
            markup.add("🗑️ تفريغ هذا القسم")
        else:
            markup.add("👤 تجربة كمستخدم")

    msg_text = f"📂 القسم الحالي: {path_str if path_str else 'الرئيسية'}\n\nاختر من القائمة أدناه:"
    bot.send_message(chat_id, msg_text, reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    users_col.update_one({"chat_id": chat_id}, {"$set": {"chat_id": chat_id}}, upsert=True)
    user_path[chat_id] = []
    upload_mode[chat_id] = False
    testing_mode[chat_id] = False
    show_menu(chat_id)

@bot.message_handler(func=lambda m: m.text in ["🛑 إنهاء إضافة الملفات", "🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية", "🛑 إنهاء التجربة والعودة للإشراف"])
def handle_control_buttons(message):
    chat_id = message.chat.id
    text = message.text
    
    if text == "🛑 إنهاء إضافة الملفات":
        upload_mode[chat_id] = False
        bot.send_message(chat_id, "إغلاق وضع الرفع المتعدد... ⚙️")
        show_menu(chat_id)
    elif text == "🛑 إنهاء التجربة والعودة للإشراف":
        testing_mode[chat_id] = False
        show_menu(chat_id)
    elif text == "🔝 القائمة الرئيسية":
        user_path[chat_id] = []
        upload_mode[chat_id] = False
        show_menu(chat_id)
    elif text == "🔙 الرجوع للقائمة السابقة":
        if chat_id in user_path and user_path[chat_id]:
            user_path[chat_id].pop()
        upload_mode[chat_id] = False
        show_menu(chat_id)

@bot.message_handler(func=lambda m: m.chat.id in ADMIN_IDS and m.text == "➕ إضافة ملف" and not testing_mode.get(m.chat.id))
def enable_upload(message):
    chat_id = message.chat.id
    upload_mode[chat_id] = True
    markup = ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إنهاء إضافة الملفات")
    bot.send_message(chat_id, "📥 وضع الرفع المتعدد مُفعّل داخل هذا المجلد!\nأرسل ملفاتك (مذكرة، ملخص، نموذج) الآن مباشرة.\n\nعند الانتهاء اضغط الزر أدناه 👇", reply_markup=markup)

@bot.message_handler(func=lambda m: m.chat.id in ADMIN_IDS and m.text == "🗑️ تفريغ هذا القسم" and not testing_mode.get(m.chat.id))
def clear_folder(message):
    chat_id = message.chat.id
    path_str = get_path_string(chat_id)
    files_col.delete_many({"menu_path": path_str})
    bot.send_message(chat_id, "🗑️ تم مسح الملفات من السحابة لهذا المجلد بنجاح!")
    show_menu(chat_id)

@bot.message_handler(content_types=['document'], func=lambda m: m.chat.id in ADMIN_IDS and upload_mode.get(m.chat.id))
def receive_files(message):
    chat_id = message.chat.id
    path_str = get_path_string(chat_id)
    file_name = message.caption if message.caption else message.document.file_name
    file_id = message.document.file_id
    
    files_col.insert_one({"menu_path": path_str, "file_name": file_name, "file_id": file_id})
    bot.send_message(chat_id, f"✅ تم الحفظ السحابي الدائم للملف داخل المجلد: {file_name}")

@bot.message_handler(func=lambda message: True)
def handle_navigation(message):
    chat_id = message.chat.id
    text = message.text
    
    if chat_id not in user_path:
        user_path[chat_id] = []

    if text == "👤 تجربة كمستخدم" and chat_id in ADMIN_IDS:
        testing_mode[chat_id] = True
        show_menu(chat_id)
        return
        
    # 🌟 تحديث دالة التواصل لتصبح ترحيبية وتفاعلية تليق بإدارة الدفعة
    if text == "👨‍💻 تواصل مع المطور":
        msg_dev = (
            "👋 مرحباً بك في قسم الدعم الفني والتطوير الأكاديمي!\n\n"
            "نحن هنا دائماً لخدمتكم، ونستقبل بكل رحابة صدر أي استفسارات، مقترحات، أو ملفات تعليمية "
            "(ملخصات، ملازم، مراجع، أو نماذج اختبارات) ترون أنها قد تفيد طلاب وطالبات الدفعة وتثري البوت.\n\n"
            "💬 لا تتردد في التواصل مع طاقم الإشراف مباشرة عبر الحسابات الرسمية أدناه:\n\n"
            "👔 المندوب العام للدفعة:\n"
            "🔹 الواثق بالله عساج ⇦ (@AlwatheqAssag)\n\n"
            "🛠️ فريق الدعم الفني ومشرفي المنصة :\n"
            "🔹 جلال المهدي ⇦ (@jalal_almahdy)\n"
            "🔹 براء حسن ⇦ (@br44ai)\n\n"
            "✨ مساهمتكم تصنع الفارق.. شكراً لتعاونكم المستمر!"
        )
        bot.send_message(chat_id, msg_dev)
        return

    if text.startswith("📄 "):
        clean_file_name = text.replace("📄 ", "")
        path_str = get_path_string(chat_id)
        res = files_col.find_one({"menu_path": path_str, "file_name": clean_file_name})
        if res:
            bot.send_document(chat_id, res['file_id'])
        return

    current_menu = get_menu_by_path(user_path[chat_id])
    if isinstance(current_menu, dict) and text in current_menu:
        user_path[chat_id].append(text)
        show_menu(chat_id)

@app.route('/' + API_TOKEN, methods=['POST'])
def getMessage():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "!", 200

@app.route("/")
def webhook():
    bot.remove_webhook()
    return "Academic Bot is working perfectly 100% with Folder Structures! 🚀", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
