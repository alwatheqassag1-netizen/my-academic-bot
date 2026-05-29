import telebot
from pymongo import MongoClient
from flask import Flask, request
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import sys
import threading
import time
from datetime import datetime, timedelta
from bson.objectid import ObjectId
import os
import re
import google.generativeai as genai

# 1. حل مشكلة الترميز للنصوص العربية
if sys.version_info >= (3, 0):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 2. الإعدادات الأساسية
API_TOKEN = '7524289470:AAGkeX96s1s6saxGP3uy14MN9it19nKn10A'
SUPER_ADMIN_ID = 6842543527  # الواثق (المدير الأعلى المطلق)
MONGO_URI = "mongodb+srv://Alwatheq:alwatheq73@cluster0.ft0mdkt.mongodb.net/?appName=Cluster0"

# 3. إعداد الذكاء الاصطناعي (Gemini)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# 4. الاتصال الآمن بقاعدة البيانات (تم إضافة جداول الهاشتاجات والمجموعات)
try:
    client = MongoClient(MONGO_URI)
    db = client['academic_bot_db']
    files_col = db['uploaded_files']
    folders_col = db['dynamic_folders']
    users_col = db['bot_users']
    admins_col = db['admins_list']
    settings_col = db['bot_settings']
    alerts_col = db['scheduled_alerts']
    requests_col = db['file_requests']
    hashtags_col = db['dynamic_hashtags'] # جدول الهاشتاجات
    auth_groups_col = db['auth_groups'] # جدول المجموعات المعتمدة
    print("Database Connected Perfectly! 🎉")
except Exception as e:
    print(f"MongoDB Error: {e}")

if admins_col.count_documents({"id": SUPER_ADMIN_ID}) == 0:
    admins_col.insert_one({"id": SUPER_ADMIN_ID, "type": "super", "allowed_paths": []})
if settings_col.count_documents({}) == 0:
    settings_col.insert_one({"status": "active"})

# إضافة الهاشتاجات الافتراضية إذا كانت فارغة
if hashtags_col.count_documents({}) == 0:
    hashtags_col.insert_many([
        {"tag": "#ثقافة_محاضرات", "path": "🌱 مستوى أول > 📅 ترم ثاني > 🕋 الثقافة الإسلامية > 📁 محاضرات وملخصات"},
        {"tag": "#بيانات_عملي", "path": "🌱 مستوى أول > 📅 ترم ثاني > 📊 مقدمة في علوم البيانات > ⚙️ محاضرات العملي"},
        {"tag": "#برمجة_نظري", "path": "🌱 مستوى أول > 📅 ترم ثاني > 💻 برمجة حاسوب > 📂 محاضرات نظري"}
    ])

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)
BOT_USERNAME = bot.get_me().username

# 5. الهيكل الأكاديمي
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

user_path, upload_mode, add_folder_mode, admin_action_mode = {}, {}, {}, {}
testing_mode, action_payload, temp_data, broadcast_mode = {}, {}, {}, {}

# === دوال الصلاحيات المركزية ===
def is_super_admin(chat_id): 
    return chat_id == SUPER_ADMIN_ID

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

def get_path_string(chat_id): 
    return " > ".join(user_path.get(chat_id, []))

def reset_modes(chat_id):
    upload_mode[chat_id] = False
    add_folder_mode[chat_id] = False
    broadcast_mode[chat_id] = False
    admin_action_mode[chat_id] = None
    action_payload.pop(chat_id, None)

# === أوامر المجموعات (Auth System) ===
@bot.message_handler(commands=['auth'])
def auth_group(message):
    if message.chat.type in ['group', 'supergroup'] and message.from_user.id == SUPER_ADMIN_ID:
        auth_groups_col.update_one({"chat_id": message.chat.id}, {"$set": {"title": message.chat.title}}, upsert=True)
        bot.reply_to(message, "✅ تم اعتماد هذه المجموعة بنجاح. البوت الآن يراقب الهاشتاجات هنا للرفع التلقائي.")

@bot.message_handler(commands=['unauth'])
def unauth_group(message):
    if message.chat.type in ['group', 'supergroup'] and message.from_user.id == SUPER_ADMIN_ID:
        auth_groups_col.delete_one({"chat_id": message.chat.id})
        bot.reply_to(message, "⛔ تم إزالة الاعتماد. البوت سيتجاهل أي هاشتاج في هذه المجموعة.")

# === الأرشفة التلقائية الديناميكية ===
@bot.message_handler(content_types=['document', 'photo'], func=lambda m: m.chat.type in ['group', 'supergroup', 'channel'])
def auto_archive_handler(message):
    # التحقق من أن المجموعة معتمدة
    if not auth_groups_col.find_one({"chat_id": message.chat.id}):
        return 

    caption = message.caption or ""
    tags = list(hashtags_col.find())
    
    for tag_data in tags:
        tag = tag_data['tag']
        path = tag_data['path']
        if tag in caption:
            name = caption.replace(tag, "").strip() or ("مستند أرشيف" if message.content_type == 'document' else "صورة أرشيف")
            name = name.replace("📄", "").replace("📌", "").replace("🖼️", "").strip()
            
            doc = {"menu_path": path, "name": name, "type": message.content_type, "caption": caption, "downloads": 0, "upload_date": datetime.utcnow()}
            if message.content_type == 'document': doc['file_id'] = message.document.file_id
            else: doc['file_id'] = message.photo[-1].file_id
            files_col.insert_one(doc)
            try: bot.reply_to(message, f"✅ تمت الأرشفة التلقائية في قسم:\n{path.split('>')[-1].strip()}")
            except: pass
            break

# === دوال القوائم والتنقل ===
def show_menu(chat_id):
    path = user_path.get(chat_id, [])
    current_menu = get_menu_by_path(path)
    path_str = get_path_string(chat_id)
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    mode = admin_action_mode.get(chat_id)
    
    if mode == "add_path_admin_path":
        markup.add(KeyboardButton("✅ تعيين صلاحية المشرف هنا"), KeyboardButton("🛑 إلغاء الأمر"))
        bot.send_message(chat_id, f"📍 تصفح الأقسام للوصول للمقرر المطلوب، ثم اضغط زر التعيين.\nالمسار الحالي: {path_str or 'الرئيسية'}")
    elif mode == "move_file_dest":
        markup.add(KeyboardButton("📦 أنقل الملف إلى هذا القسم"), KeyboardButton("🛑 إلغاء الأمر"))
        bot.send_message(chat_id, f"📦 تصفح الأقسام واضغط لنقل الملف هنا.\nالمسار الحالي: {path_str or 'الرئيسية'}")

    if not path:
        for key in ACADEMIC_STRUCTURE.keys(): markup.add(KeyboardButton(key))
        markup.add("🔥 الملفات الأكثر شعبية", "🆕 تحديثات اليوم")
        markup.add("🤖 المساعد الذكي (AI)", "🔍 بحث عن ملف")
        markup.add("🧠 معلومات عن التخصص", "👨‍💻 تواصل مع المطور")
        
        if is_super_admin(chat_id) and not testing_mode.get(chat_id):
            markup.add("📢 إرسال رسالة جماعية", "👥 إحصائيات المشتركين")
            markup.add("🛠️ إدارة المشرفين", "⚙️ التحكم بالنظام")
            markup.add("🏷️ إدارة الأرشفة والهاشتاجات") # الزر الجديد للمدير
            
        bot.send_message(chat_id, "مرحباً بك في المنصة الأكاديمية (الدفعة الثانية) 🎓\n\n👇 فضلاً، اختر من القائمة أدناه للبدء:", reply_markup=markup)
        return

    if isinstance(current_menu, dict):
        for key in current_menu.keys(): markup.add(KeyboardButton(key))
            
    for df in folders_col.find({"parent_path": path_str}): 
        markup.add(KeyboardButton(f"📁 {df['folder_name']}"))
        
    for f in files_col.find({"menu_path": path_str}):
        icon = "📌" if f.get("type") == "text" else "🖼️" if f.get("type") == "photo" else "📄"
        markup.add(KeyboardButton(f"{icon} {f['name']}"))

    markup.add("🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية")
    
    if testing_mode.get(chat_id):
        markup.add("🛑 إنهاء التجربة والعودة للإشراف")
    elif has_permission(chat_id, path_str) and mode not in ["add_path_admin_path", "move_file_dest"]:
        markup.add("👤 تجربة كمستخدم", "➕ إضافة ملف/نص", "📂 إضافة مجلد")
        if is_super_admin(chat_id): 
            markup.add("🔗 ربط هاشتاج بالقسم") # زر الربط السريع داخل القسم للمدير الأعلى

    bot.send_message(chat_id, f"📂 القسم الحالي: {path_str}", reply_markup=markup)

def send_file_to_user(chat_id, res, has_perm):
    markup = InlineKeyboardMarkup(row_width=2)
    file_id_str = str(res['_id'])
    share_url = f"https://t.me/{BOT_USERNAME}?start={file_id_str}"
    
    if has_perm and not testing_mode.get(chat_id):
        markup.add(InlineKeyboardButton("✏️ تعديل الاسم", callback_data=f"rn_{file_id_str}"), InlineKeyboardButton("🔄 استبدال", callback_data=f"rp_{file_id_str}"))
        markup.add(InlineKeyboardButton("🗑️ حذف", callback_data=f"dl_{file_id_str}"), InlineKeyboardButton("📦 نقل", callback_data=f"mv_{file_id_str}"))
        markup.add(InlineKeyboardButton("🔗 رابط مشاركة", url=f"https://t.me/share/url?url={share_url}"))
    else:
        markup.add(InlineKeyboardButton("🔗 شارك الملف", url=f"https://t.me/share/url?url={share_url}"))

    caption = res.get('caption', res['name']) + f"\n\n🔻 التحميلات: {res.get('downloads', 0)}"
    if res['type'] == 'text': bot.send_message(chat_id, res['content'], reply_markup=markup)
    elif res['type'] == 'photo': bot.send_photo(chat_id, res['file_id'], caption=caption, reply_markup=markup)
    else: bot.send_document(chat_id, res['file_id'], caption=caption, reply_markup=markup)

# === الأوامر الأساسية ===
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

@bot.message_handler(func=lambda m: not settings_col.find_one({"status": "active"}) and m.chat.id != SUPER_ADMIN_ID)
def system_offline(message):
    bot.send_message(message.chat.id, "⛔ المنصة الأكاديمية مغلقة حالياً للصيانة والتحديث بقرار من الإدارة العليا. يرجى المحاولة لاحقاً.")

# === المعالج المركزي الموحد ===
@bot.message_handler(content_types=['text', 'document', 'photo', 'video', 'audio'])
def universal_handler(message):
    chat_id = message.chat.id
    text = message.text if message.content_type == 'text' else ""
    path_str = get_path_string(chat_id)
    mode = admin_action_mode.get(chat_id)

    if text == "🛑 إلغاء الأمر":
        reset_modes(chat_id)
        bot.send_message(chat_id, "✅ تم إلغاء الإجراء بنجاح.")
        show_menu(chat_id)
        return

    if text == "✅ تعيين صلاحية المشرف هنا" and mode == "add_path_admin_path":
        admins_col.update_one({"id": temp_data[chat_id]}, {"$set": {"type": "path"}, "$addToSet": {"allowed_paths": path_str}}, upsert=True)
        bot.send_message(chat_id, f"✅ اكتملت المهمة! أصبح المشرف مسؤولاً عن القسم:\n{path_str}")
        reset_modes(chat_id); show_menu(chat_id)
        return
    if text == "📦 أنقل الملف إلى هذا القسم" and mode == "move_file_dest":
        files_col.update_one({"_id": ObjectId(action_payload.get(chat_id))}, {"$set": {"menu_path": path_str}})
        bot.send_message(chat_id, f"📦 تم نقل الملف وحفظه في:\n{path_str}")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if text in ["🔝 القائمة الرئيسية", "📚 تصفح بوت الدفعة"]:
        user_path[chat_id] = []
        reset_modes(chat_id); show_menu(chat_id)
        return
    if text == "🔙 الرجوع للقائمة السابقة":
        if chat_id in user_path and user_path[chat_id]: user_path[chat_id].pop()
        reset_modes(chat_id); show_menu(chat_id)
        return

    if text == "🔥 الملفات الأكثر شعبية":
        top = list(files_col.find({"downloads": {"$gt": 0}}).sort("downloads", -1).limit(5))
        if not top: bot.send_message(chat_id, "لا توجد ملفات تم تحميلها حتى الآن لتكوين الإحصائية.")
        else:
            bot.send_message(chat_id, "🔥 *أكثر 5 ملفات تم الاعتماد عليها:*", parse_mode="Markdown")
            for f in top: send_file_to_user(chat_id, f, False)
        return
        
    if text == "🆕 تحديثات اليوم":
        yesterday = datetime.utcnow() - timedelta(days=1)
        new_files = list(files_col.find({"upload_date": {"$gte": yesterday}}).limit(10))
        if not new_files: bot.send_message(chat_id, "لم يتم إضافة ملفات جديدة خلال 24 ساعة الماضية.")
        else:
            bot.send_message(chat_id, "🆕 *أحدث الإضافات للمنصة:*", parse_mode="Markdown")
            for f in new_files: send_file_to_user(chat_id, f, False)
        return
        
    if text == "🧠 معلومات عن التخصص":
        info_text = (
            "🚀 *الذكاء الاصطناعي وعلوم البيانات (AI & Data Science)*\n\n"
            "مرحباً بك في تخصص المستقبل، ولغة العصر الحديث! 🌟\n"
            "هذا التخصص ليس مجرد دراسة، بل هو البوابة لصناعة التكنولوجيا التي تقود العالم. يدمج التخصص بين قوة البرمجة، عمق الرياضيات، وعبقرية تحليل البيانات الضخمة.\n\n"
            "💡 *لماذا هذا التخصص؟*\n"
            "لأنك هنا تتعلم كيف تجعل الآلة تفكر، تحلل، وتتخذ القرارات! من أنظمة التوصية، إلى معالجة اللغات، وصولاً إلى الرؤية الحاسوبية؛ أنت تُهندس المستقبل.\n\n"
            "🎓 *أنت لست مجرد طالب، أنت مهندس حلول المستقبل.* استمر، فالعالم ينتظر إبداعك!"
        )
        bot.send_message(chat_id, info_text, parse_mode="Markdown")
        return
        
    if text == "👨‍💻 تواصل مع المطور":
        dev_text = (
            "👨‍💻 *دعم وتطوير المنصة:*\n\n"
            "🔹 *الواثق بالله عساج* ⇦ (@AlwatheqAssag)\n\n"
            "إذا كان لديك أي استفسار أكاديمي، أو مشكلة تقنية تواجهها في البوت، أو لديك ملخصات ومحاضرات قيمة تود إضافتها لتعم الفائدة على جميع زملائك، فلا تتردد في التواصل معي مباشرة.\n\n"
            "نحن هنا لخدمتكم وجعل مسيرتكم الجامعية أسهل! 🎓"
        )
        bot.send_message(chat_id, dev_text, parse_mode="Markdown")
        return

    if text == "🔍 بحث عن ملف":
        reset_modes(chat_id); admin_action_mode[chat_id] = "search"
        bot.send_message(chat_id, "🔍 أرسل كلمة للبحث عن الملف (مثال: تفاضل، برمجة):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
        return

    if text == "🤖 المساعد الذكي (AI)":
        reset_modes(chat_id); admin_action_mode[chat_id] = "ai_chat"
        bot.send_message(chat_id, "🤖 أهلاً بك! أنا مساعدك الذكي المدمج في المنصة.\nاطرح أي سؤال أكاديمي، برمجي، أو استفسار علمي وسأقوم بالإجابة عليه فوراً:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
        return

    # أوامر الإدارة العليا
    if is_super_admin(chat_id):
        if text == "🏷️ إدارة الأرشفة والهاشتاجات":
            markup = ReplyKeyboardMarkup(resize_keyboard=True).add("📋 عرض الهاشتاجات والمجموعات", "🗑️ حذف هاشتاج", "🔝 القائمة الرئيسية")
            bot.send_message(chat_id, "🏷️ *نظام الأرشفة الذكي:*\n\n🔹 *لإضافة مجموعة:* أضف البوت للجروب وأرسل فيه `/auth`.\n🔹 *لإضافة هاشتاج:* تصفح لأي قسم بالبوت واضغط (🔗 ربط هاشتاج بالقسم).", reply_markup=markup, parse_mode="Markdown")
            return
        if text == "📋 عرض الهاشتاجات والمجموعات":
            groups = list(auth_groups_col.find())
            tags = list(hashtags_col.find())
            msg = "🛡️ *المجموعات المعتمدة للرفع:*\n"
            for g in groups: msg += f"▪️ {g.get('title', 'مجموعة غير معروفة')}\n"
            msg += "\n🏷️ *الهاشتاجات النشطة:*\n"
            for t in tags: msg += f"🔸 {t['tag']} ⇦ {t['path'].split('>')[-1]}\n"
            if not groups and not tags: msg = "لا توجد مجموعات أو هاشتاجات نشطة حالياً."
            bot.send_message(chat_id, msg, parse_mode="Markdown")
            return
        if text == "🗑️ حذف هاشتاج":
            reset_modes(chat_id); admin_action_mode[chat_id] = "del_hashtag"
            bot.send_message(chat_id, "أرسل الهاشتاج الذي تريد حذفه (مثال: #ثقافة_نماذج):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            return
        if text == "🔗 ربط هاشتاج بالقسم":
            reset_modes(chat_id); admin_action_mode[chat_id] = "add_hashtag"
            bot.send_message(chat_id, "أرسل الهاشتاج الذي سيتم ربطه بهذا القسم (يجب أن يبدأ بـ #):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            return
            
        if text == "🛠️ إدارة المشرفين":
            markup = ReplyKeyboardMarkup(resize_keyboard=True).add("➕ إضافة مشرف عام", "➕ إضافة مشرف مسار مخصص", "➖ إزالة مشرف", "🔝 القائمة الرئيسية")
            bot.send_message(chat_id, "🛠️ إدارة الصلاحيات:\nالمشرف العام: يدير كل الأقسام والمواد.\nمشرف المسار: يدير مادة محددة فقط.", reply_markup=markup)
            return
        if text == "➕ إضافة مشرف عام":
            reset_modes(chat_id); admin_action_mode[chat_id] = "add_global_admin"
            bot.send_message(chat_id, "أرسل الآيدي (ID) للمشرف العام الجديد:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            return
        if text == "➕ إضافة مشرف مسار مخصص":
            reset_modes(chat_id); admin_action_mode[chat_id] = "add_path_admin_id"
            bot.send_message(chat_id, "الخطوة 1: أرسل الآيدي (ID) للمشرف المخصص:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            return
        if text == "➖ إزالة مشرف":
            reset_modes(chat_id); admin_action_mode[chat_id] = "remove_admin"
            bot.send_message(chat_id, "أرسل الآيدي (ID) للمشرف لإلغاء صلاحياته نهائياً:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            return
        if text == "👥 إحصائيات المشتركين":
            users = users_col.count_documents({})
            files = files_col.count_documents({})
            bot.send_message(chat_id, f"📊 *تقرير النظام:*\n👥 إجمالي الطلاب: {users}\n📁 إجمالي الملفات المرفوعة: {files}", parse_mode="Markdown")
            return
        if text == "📢 إرسال رسالة جماعية":
            reset_modes(chat_id); broadcast_mode[chat_id] = True
            bot.send_message(chat_id, "📢 أرسل الآن الرسالة (نص، صورة، أو ملف) ليتم توجيهها لجميع الطلاب:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            return
        if text == "⚙️ التحكم بالنظام":
            status_btn = "▶️ تشغيل البوت" if not settings_col.find_one({"status": "active"}) else "⏸️ إيقاف البوت"
            bot.send_message(chat_id, "🛡️ مركز التحكم بخوادم البوت:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(status_btn, "🔝 القائمة الرئيسية"))
            return
        if text in ["▶️ تشغيل البوت", "⏸️ إيقاف البوت"]:
            status = "active" if text == "▶️ تشغيل البوت" else "inactive"
            settings_col.update_one({}, {"$set": {"status": status}}, upsert=True)
            bot.send_message(chat_id, f"✅ تم {'التشغيل' if status == 'active' else 'الإيقاف'} بنجاح.")
            show_menu(chat_id)
            return

    # الأزرار الإدارية
    if text == "🛑 إنهاء التجربة والعودة للإشراف":
        testing_mode[chat_id] = False
        bot.send_message(chat_id, "💼 عادت صلاحيات الإشراف كاملة.")
        show_menu(chat_id)
        return
    if has_permission(chat_id, path_str):
        if text == "👤 تجربة كمستخدم":
            testing_mode[chat_id] = True
            bot.send_message(chat_id, "👀 أنت الآن تتصفح كطالب عادي (الأزرار الإدارية مخفية).")
            show_menu(chat_id)
            return
        if text == "➕ إضافة ملف/نص":
            reset_modes(chat_id); upload_mode[chat_id] = True
            bot.send_message(chat_id, "📥 أرسل الملف، الصورة، أو اكتب النص الآن:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            return
        if text == "📂 إضافة مجلد":
            reset_modes(chat_id); add_folder_mode[chat_id] = True
            bot.send_message(chat_id, "📂 اكتب اسم المجلد الفرعي الجديد:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            return

    # معالجة التقاط البيانات
    if mode == "add_hashtag" and text and is_super_admin(chat_id):
        if not text.startswith("#"): text = "#" + text
        hashtags_col.insert_one({"tag": text.strip(), "path": path_str})
        bot.send_message(chat_id, f"✅ تم ربط الهاشتاج {text} بهذا القسم بنجاح.")
        reset_modes(chat_id); show_menu(chat_id)
        return
        
    if mode == "del_hashtag" and text and is_super_admin(chat_id):
        if not text.startswith("#"): text = "#" + text
        res = hashtags_col.delete_one({"tag": text.strip()})
        if res.deleted_count > 0: bot.send_message(chat_id, f"✅ تم حذف الهاشتاج {text} بنجاح.")
        else: bot.send_message(chat_id, "❌ لم يتم العثور على الهاشتاج.")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if mode == "ai_chat" and text:
        if not GEMINI_API_KEY:
            bot.send_message(chat_id, "❌ الذكاء الاصطناعي غير متصل. يرجى من الإدارة إضافة مفتاح الـ API.")
        else:
            bot.send_message(chat_id, "⏳ جاري التفكير...")
            try:
                model_names = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']
                response = None
                for name in model_names:
                    try:
                        model = genai.GenerativeModel(name)
                        response = model.generate_content(text)
                        break
                    except: continue
                if response:
                    try: bot.send_message(chat_id, response.text, parse_mode="Markdown")
                    except: bot.send_message(chat_id, response.text)
                else: bot.send_message(chat_id, "❌ عذراً، لا يتوفر نموذج ذكاء اصطناعي متاح في حسابك حالياً.")
            except Exception as e:
                bot.send_message(chat_id, "❌ حدث خطأ في الخادم، حاول لاحقاً.")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if broadcast_mode.get(chat_id) and is_super_admin(chat_id):
        broadcast_mode[chat_id] = False
        users = list(users_col.find())
        success = 0
        bot.send_message(chat_id, "⏳ جاري الإرسال لجميع الطلاب...")
        for u in users:
            try:
                bot.copy_message(u['chat_id'], chat_id, message.message_id)
                success += 1
            except: pass
        bot.send_message(chat_id, f"✅ تمت العملية بنجاح! استلم الرسالة {success} طالب.")
        show_menu(chat_id)
        return

    if mode == "search" and text:
        results = list(files_col.find({"name": {"$regex": text, "$options": "i"}}).limit(7))
        if results:
            bot.send_message(chat_id, "🔍 *نتائج البحث:*", parse_mode="Markdown")
            for r in results:
                bot.send_message(chat_id, f"📁 في قسم:\n{r['menu_path']}")
                send_file_to_user(chat_id, r, has_permission(chat_id, r['menu_path']))
        else: bot.send_message(chat_id, "❌ لم نجد ملفات تطابق كلمتك.")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if mode == "add_global_admin" and text and is_super_admin(chat_id):
        try:
            admins_col.update_one({"id": int(text.strip())}, {"$set": {"type": "global"}}, upsert=True)
            bot.send_message(chat_id, "✅ تمت إضافة المشرف العام بنجاح.")
        except: bot.send_message(chat_id, "❌ خطأ: أرسل الأرقام فقط.")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if mode == "remove_admin" and text and is_super_admin(chat_id):
        try:
            target = int(text.strip())
            if target != SUPER_ADMIN_ID:
                admins_col.delete_one({"id": target})
                bot.send_message(chat_id, "✅ تم تجريد المشرف من صلاحياته.")
        except: bot.send_message(chat_id, "❌ خطأ: أرسل الأرقام فقط.")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if mode == "add_path_admin_id" and text and is_super_admin(chat_id):
        try:
            temp_data[chat_id] = int(text.strip())
            admin_action_mode[chat_id] = "add_path_admin_path"
            user_path[chat_id] = []
            bot.send_message(chat_id, "✅ الخطوة 2: تم حفظ الآيدي. تصفح الأقسام الآن للوصول للمادة، ثم اضغط تأكيد.")
            show_menu(chat_id)
        except: bot.send_message(chat_id, "❌ أرقام فقط.")
        return

    if mode == "rename_file" and text:
        files_col.update_one({"_id": ObjectId(action_payload.get(chat_id))}, {"$set": {"name": text.strip()}})
        bot.send_message(chat_id, "✅ تم تغيير اسم الملف.")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if mode == "replace_file":
        obj_id = action_payload.get(chat_id)
        if message.content_type == 'document': files_col.update_one({"_id": ObjectId(obj_id)}, {"$set": {"type": "document", "file_id": message.document.file_id, "name": message.caption or message.document.file_name, "caption": message.caption}})
        elif message.content_type == 'photo': files_col.update_one({"_id": ObjectId(obj_id)}, {"$set": {"type": "photo", "file_id": message.photo[-1].file_id, "name": message.caption or "صورة", "caption": message.caption}})
        elif message.content_type == 'text': files_col.update_one({"_id": ObjectId(obj_id)}, {"$set": {"type": "text", "content": text, "name": text[:25]}})
        bot.send_message(chat_id, "✅ تم استبدال المحتوى بنجاح.")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if add_folder_mode.get(chat_id) and text and has_permission(chat_id, path_str):
        folders_col.insert_one({"parent_path": path_str, "folder_name": text.strip()})
        bot.send_message(chat_id, f"✅ تم إنشاء مجلد: {text.strip()}")
        reset_modes(chat_id); show_menu(chat_id)
        return

    if upload_mode.get(chat_id) and has_permission(chat_id, path_str):
        name = text[:30] if message.content_type == 'text' else (message.caption or (message.document.file_name if message.content_type == 'document' else "ملف مرفق"))
        name = name.strip().replace("📄", "").replace("📌", "").replace("🖼️", "").strip()
        doc = {"menu_path": path_str, "name": name, "type": message.content_type, "caption": message.caption, "downloads": 0, "upload_date": datetime.utcnow()}
        if message.content_type == 'text': doc['content'] = text
        else: doc['file_id'] = message.document.file_id if message.content_type == 'document' else message.photo[-1].file_id
        files_col.insert_one(doc)
        bot.send_message(chat_id, f"✅ تمت الإضافة لقاعدة البيانات: {name}")
        reset_modes(chat_id); show_menu(chat_id)
        return

    # الاستدعاء الآمن للملفات والمحاضرات
    if text and (text.startswith("📄 ") or text.startswith("📌 ") or text.startswith("🖼️ ")):
        clean_name = text.replace("📄 ", "").replace("📌 ", "").replace("🖼️ ", "").strip()
        res = files_col.find_one({"menu_path": path_str, "name": clean_name})
        if not res:
            res = files_col.find_one({"menu_path": path_str, "name": {"$regex": re.escape(clean_name), "$options": "i"}})
        
        if res:
            files_col.update_one({"_id": res["_id"]}, {"$inc": {"downloads": 1}}) 
            send_file_to_user(chat_id, res, has_permission(chat_id, path_str))
        else: 
            bot.send_message(chat_id, "❌ لم أتمكن من العثور على الملف، قد يكون تم حذفه من قبل المشرفين.")
        return

    # التنقل في المجلدات
    if text.startswith("📁 "):
        user_path[chat_id].append(text.replace("📁 ", "").strip())
        show_menu(chat_id)
        return

    current_menu = get_menu_by_path(user_path.get(chat_id, []))
    if isinstance(current_menu, dict) and text in current_menu:
        if chat_id not in user_path: user_path[chat_id] = []
        user_path[chat_id].append(text)
        show_menu(chat_id)
        return

# === أزرار التحكم للملفات (Inline Buttons) ===
@bot.callback_query_handler(func=lambda call: call.data.startswith(('rn_', 'rp_', 'dl_', 'mv_')))
def handle_callbacks(call):
    chat_id = call.message.chat.id
    action, obj_id = call.data.split('_')
    
    doc = files_col.find_one({"_id": ObjectId(obj_id)})
    if not doc or not has_permission(chat_id, doc['menu_path']):
        bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية لإدارة هذا الملف.", show_alert=True)
        return

    if action == 'dl':
        files_col.delete_one({"_id": ObjectId(obj_id)})
        bot.delete_message(chat_id, call.message.message_id)
        bot.answer_callback_query(call.id, "🗑️ تم الحذف من قاعدة البيانات.")
        show_menu(chat_id)
    elif action == 'rn':
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "rename_file"
        action_payload[chat_id] = obj_id
        bot.send_message(chat_id, f"✏️ أرسل الاسم الجديد للملف:")
    elif action == 'rp':
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "replace_file"
        action_payload[chat_id] = obj_id
        bot.send_message(chat_id, f"🔄 أرسل المستند الجديد ليحل محل القديم:")
    elif action == 'mv':
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "move_file_dest"
        action_payload[chat_id] = obj_id
        user_path[chat_id] = []
        show_menu(chat_id)

@app.route('/webhook', methods=['POST'])
def webhook_listen():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "!", 200

@app.route("/")
def home():
    return "LMS Version 6.0 is RUNNING (AI + Auth Groups)! 🚀", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
