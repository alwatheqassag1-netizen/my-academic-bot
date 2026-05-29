import telebot
from pymongo import MongoClient
from flask import Flask, request
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
import sys
import io

# حل مشكلة الترميز في السيرفرات لطباعة النصوص العربية بسلاسة
if sys.version_info >= (3, 0):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_TOKEN = '7524289470:AAGkeX96s1s6saxGP3uy14MN9it19nKn10A'
ADMIN_IDS = [6842543527, 5585934059, 1084564343] 

# 🔗 الرابط السحابي المحصن والمكتمل بكلمة السر الخاصة بك
MONGO_URI = "mongodb+srv://Alwatheq:alwatheq73@cluster0.ft0mdkt.mongodb.net/?appName=Cluster0"

try:
    # الاتصال بقاعدة البيانات السحابية الآمنة
    client = MongoClient(MONGO_URI)
    db = client['academic_bot_db']
    files_col = db['uploaded_files']
    users_col = db['bot_users']
    print("Connected to MongoDB Atlas successfully! 🎉")
except Exception as e:
    print(f"MongoDB connection error: {e}")

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)

# الهيكل الأكاديمي الثابت للقسم (الدفعة الثانية)
ACADEMIC_STRUCTURE = {
    "🌱 مستوى أول": {
        "📅 ترم أول": {},
        "📅 ترم ثاني": {
            "📖 الثقافة الإسلامية": ["📂 محاضرات وملخصات", "📝 نماذج اختبارات"],
            "🌙 لغة عربية 2": ["📂 محاضرات وملخصات", "📝 نماذج اختبارات"],
            "🇬🇧 لغة إنجليزية 2": ["📂 محاضرات وملخصات", "📝 نماذج اختبارات"],
            "📈 تفاضل وتكامل 2": ["📂 محاضرات نظري", "📐 محاضرات تمارين", "📝 نماذج اختبارات نظري", "✍️ نماذج تمارين", "📚 مراجع خارجية"],
            "📊 مقدمة في علوم البيانات": ["👨‍🏫 محاضرات المهندس", "📜 ملخص محاضرات", "⚙️ محاضرات العملي", "📝 نماذج اختبارات نظري"],
            "💻 برمجة حاسوب": ["📂 محاضرات نظري", "🖥️ محاضرات العملي", "📝 نماذج اختبارات", "🚀 التمارين والمشاريع العملية"],
            "🗂️ رياضيات متقطعة": ["📂 محاضرات نظري", "✏️ محاضرات تمارين", "📝 نماذج اختبارات", "📚 مراجع خارجية"]
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

def show_menu(chat_id):
    path = user_path.get(chat_id, [])
    current_menu = get_menu_by_path(path)
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    if not path:
        for key in ACADEMIC_STRUCTURE.keys():
            markup.add(KeyboardButton(key))
        markup.add("👨‍💻 تواصل مع المطور")
        msg_text = (
            "مرحباً بك في المنصة الأكاديمية لقسم الذكاء الاصطناعي وعلوم البيانات (الدفعة الثانية) 🎓\n\n"
            "👇 فضلاً، اختر مستواك الدراسي من القائمة أدناه للبدء:"
        )
        bot.send_message(chat_id, msg_text, reply_markup=markup)
        return

    if isinstance(current_menu, dict):
        for key in current_menu.keys():
            markup.add(KeyboardButton(key))
    
    elif isinstance(current_menu, list):
        for item in current_menu:
            markup.add(KeyboardButton(item))
            
        path_str = get_path_string(chat_id)
        # جلب روابط الملفات من السحابة الدائمة بشكل فوري وسريع
        db_files = list(files_col.find({"menu_path": path_str}))
        for f in db_files:
            markup.add(KeyboardButton(f"📄 {f['file_name']}"))

    markup.add("🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية")
    
    if testing_mode.get(chat_id):
        markup.add("🛑 إنهاء التجربة والعودة للإشراف")
    elif chat_id in ADMIN_IDS:
        if isinstance(current_menu, list):
            markup.add("👤 تجربة كمستخدم", "➕ إضافة ملف")
            markup.add("🗑️ تفريغ هذا القسم")
        else:
            markup.add("👤 تجربة كمستخدم")

    msg_text = f"📂 القسم الحالي: {' > '.join(path)}\n\nاختر من القائمة أدناه:"
    bot.send_message(chat_id, msg_text, reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    # حفظ المستخدمين في السحابة لمعرفة حجم التفاعل مستقبلاً
    users_col.update_one({"chat_id": chat_id}, {"$set": {"chat_id": chat_id}}, upsert=True)
    
    user_path[chat_id] = []
    upload_mode[chat_id] = False
    testing_mode[chat_id] = False
    show_menu(chat_id)

@bot.message_handler(func=lambda m: m.chat.id in ADMIN_IDS and m.text == "➕ إضافة ملف" and not testing_mode.get(m.chat.id))
def enable_upload(message):
    chat_id = message.chat.id
    upload_mode[chat_id] = True
    markup = ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إنهاء إضافة الملفات")
    bot.send_message(chat_id, "📥 وضع الرفع المتعدد الآمن والمضمون سحابياً مُفعّل!\nأرسل ملفاتك الآن.\n\nعند الانتهاء اضغط الزر أدناه 👇", reply_markup=markup)

@bot.message_handler(func=lambda m: m.chat.id in ADMIN_IDS and m.text == "🗑️ تفريغ هذا القسم" and not testing_mode.get(m.chat.id))
def clear_folder(message):
    chat_id = message.chat.id
    path_str = get_path_string(chat_id)
    files_col.delete_many({"menu_path": path_str})
    bot.send_message(chat_id, "🗑️ تم مسح الملفات من السحابة المضمونة لهذا القسم بنجاح!")
    show_menu(chat_id)

@bot.message_handler(content_types=['document'], func=lambda m: m.chat.id in ADMIN_IDS and upload_mode.get(m.chat.id))
def receive_files(message):
    chat_id = message.chat.id
    path_str = get_path_string(chat_id)
    file_name = message.caption if message.caption else message.document.file_name
    file_id = message.document.file_id
    
    # حفظ الـ file_id في قاعدة البيانات السحابية بأمان تام للأبد
    files_col.insert_one({"menu_path": path_str, "file_name": file_name, "file_id": file_id})
    bot.send_message(chat_id, f"✅ تم الحفظ السحابي الدائم للملف: {file_name}")

@bot.message_handler(func=lambda message: True)
def handle_navigation(message):
    chat_id = message.chat.id
    text = message.text
    
    if chat_id not in user_path:
        user_path[chat_id] = []

    if text == "🛑 إنهاء إضافة الملفات" and chat_id in ADMIN_IDS:
        upload_mode[chat_id] = False
        show_menu(chat_id)
        return
    if text == "🛑 إنهاء التجربة والعودة للإشراف":
        testing_mode[chat_id] = False
        show_menu(chat_id)
        return
    if text == "👤 تجربة كمستخدم" and chat_id in ADMIN_IDS:
        testing_mode[chat_id] = True
        show_menu(chat_id)
        return
    if text == "🔝 القائمة الرئيسية":
        user_path[chat_id] = []
        upload_mode[chat_id] = False
        show_menu(chat_id)
        return
    if text == "🔙 الرجوع للقائمة السابقة":
        if user_path[chat_id]:
            user_path[chat_id].pop()
        upload_mode[chat_id] = False
        show_menu(chat_id)
        return
    if text == "👨‍💻 تواصل مع المطور":
        msg_dev = "👥 طاقم الإشراف والدعم الفني للدفعة:\n🔹 المندوب: الواثق بالله عساج (@AlwatheqAssag)\n🔹 جلال المهدي (@jalal_almahdy)\n🔹 براء حسن (@br44ai)"
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
    elif isinstance(current_menu, list) and text in current_menu:
        user_path[chat_id].append(text)
        show_menu(chat_id)

@app.route('/' + API_TOKEN, methods=['POST'])
def getMessage():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "!", 200

@app.route("/")
def webhook():
    bot.remove_webhook()
    return "Academic Bot is working perfectly 100% with Permanent Cloud Storage! 🚀", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
