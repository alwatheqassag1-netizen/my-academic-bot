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
import requests

# ==========================================
# 1. الإعدادات الأساسية وحل مشكلة الترميز
# ==========================================
if sys.version_info >= (3, 0):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_TOKEN = '7524289470:AAGkeX96s1s6saxGP3uy14MN9it19nKn10A'
SUPER_ADMIN_ID = 6842543527  # الواثق (المدير الأعلى المطلق)
MONGO_URI = "mongodb+srv://Alwatheq:alwatheq73@cluster0.ft0mdkt.mongodb.net/?appName=Cluster0"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# ==========================================
# 2. الاتصال الآمن بقاعدة البيانات 
# ==========================================
try:
    client = MongoClient(MONGO_URI)
    db = client['academic_bot_db']
    files_col = db['uploaded_files']
    folders_col = db['dynamic_folders']
    users_col = db['bot_users']
    admins_col = db['admins_list']
    settings_col = db['bot_settings']
    hashtags_col = db['dynamic_hashtags']
    auth_groups_col = db['auth_groups']
    print("Database Connected Perfectly! 🎉")
except Exception as e:
    print(f"MongoDB Error: {e}")

# تأمين إعدادات البوت والمدير الافتراضية
if admins_col.count_documents({"id": SUPER_ADMIN_ID}) == 0:
    admins_col.insert_one({"id": SUPER_ADMIN_ID, "type": "super", "allowed_paths": []})
if settings_col.count_documents({}) == 0:
    settings_col.insert_one({"status": "active"})
if hashtags_col.count_documents({}) == 0:
    hashtags_col.insert_many([
        {"tag": "#ثقافة_محاضرات", "path": "🌱 مستوى أول > 📅 ترم ثاني > 🕋 الثقافة الإسلامية > 📁 محاضرات وملخصات"},
        {"tag": "#بيانات_عملي", "path": "🌱 مستوى أول > 📅 ترم ثاني > 📊 مقدمة في علوم البيانات > ⚙️ محاضرات العملي"},
        {"tag": "#برمجة_نظري", "path": "🌱 مستوى أول > 📅 ترم ثاني > 💻 برمجة حاسوب > 📂 محاضرات نظري"}
    ])

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)
BOT_USERNAME = bot.get_me().username

# ==========================================
# 3. الهيكل الأكاديمي والمتغيرات
# ==========================================
media_groups = {} # لتجميع الملفات المرسلة دفعة واحدة

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

# ==========================================
# 4. دوال الصلاحيات والأمان
# ==========================================
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
    upload_mode[chat_id] = False; add_folder_mode[chat_id] = False; broadcast_mode[chat_id] = False
    admin_action_mode[chat_id] = None; action_payload.pop(chat_id, None)

# ==========================================
# 5. دوال رفع واستدعاء الملفات (تم حل مشكلة الـ PDF نهائياً)
# ==========================================
def build_file_doc(message, path_str):
    """دالة تجهيز الملف لقاعدة البيانات لضمان حفظ الـ file_id بدقة"""
    if message.content_type == 'document':
        name = message.document.file_name or "ملف"
        file_id = message.document.file_id
    elif message.content_type == 'photo':
        name = "صورة"
        file_id = message.photo[-1].file_id
    elif message.content_type == 'video':
        name = message.video.file_name or "فيديو"
        file_id = message.video.file_id
    else:
        name = "مرفق"
        file_id = None
        
    name = (message.caption or name).replace("📄", "").replace("📌", "").replace("🖼️", "").strip()
    return {
        "menu_path": path_str,
        "name": name[:60], # حماية من الأسماء الطويلة جداً
        "type": message.content_type,
        "caption": message.caption,
        "file_id": file_id,
        "downloads": 0,
        "upload_date": datetime.utcnow()
    }

def process_media_group(chat_id, media_group_id, path_str):
    """دالة لاستقبال 10 أو 20 ملف دفعة واحدة وحفظها في قاعدة البيانات"""
    time.sleep(3) # إعطاء تليجرام وقتاً لإرسال كامل الدفعة
    if media_group_id not in media_groups: return
    messages = media_groups.pop(media_group_id)
    added_count = 0
    for msg in messages:
        doc = build_file_doc(msg, path_str)
        if doc['file_id']: # لضمان عدم حفظ بيانات فارغة
            files_col.insert_one(doc)
            added_count += 1
    try: bot.send_message(chat_id, f"✅ تم حفظ {added_count} ملفات دفعة واحدة بنجاح في:\n📁 {path_str}")
    except: pass

def send_file_to_user(chat_id, res, has_perm):
    """دالة استدعاء وإرسال الملفات المعالجة للمشكلة القديمة"""
    try:
        markup = InlineKeyboardMarkup(row_width=2)
        file_id_str = str(res['_id'])
        share_url = f"https://t.me/{BOT_USERNAME}?start={file_id_str}"
        
        if has_perm and not testing_mode.get(chat_id):
            markup.add(InlineKeyboardButton("✏️ تعديل الاسم", callback_data=f"rn_{file_id_str}"), InlineKeyboardButton("🔄 استبدال الملف", callback_data=f"rp_{file_id_str}"))
            markup.add(InlineKeyboardButton("🗑️ حذف", callback_data=f"dl_{file_id_str}"), InlineKeyboardButton("📦 نقل", callback_data=f"mv_{file_id_str}"))
            markup.add(InlineKeyboardButton("🔗 مشاركة", url=f"https://t.me/share/url?url={share_url}"))
        else:
            markup.add(InlineKeyboardButton("🔗 شارك الملف", url=f"https://t.me/share/url?url={share_url}"))

        # المعالجة الدقيقة للبيانات لضمان الإرسال
        file_type = res.get('type', 'document')
        file_id = res.get('file_id')
        file_name = res.get('name', 'ملف')
        
        caption = res.get('caption')
        if not caption or caption.strip() == "": caption = file_name
        caption += f"\n\n🔻 التحميلات: {res.get('downloads', 0)}"

        # الإرسال الفعلي حسب النوع
        if file_type == 'text':
            bot.send_message(chat_id, res.get('content', file_name), reply_markup=markup)
        elif file_type == 'photo' and file_id:
            bot.send_photo(chat_id, file_id, caption=caption, reply_markup=markup)
        elif file_id: # هذا يضمن إرسال الـ PDF والمستندات
            bot.send_document(chat_id, file_id, caption=caption, reply_markup=markup)
        else:
            bot.send_message(chat_id, "❌ خطأ: ملف الـ PDF أو المستند غير متوفر في سيرفرات تليجرام.", reply_markup=markup)
            
    except Exception as e:
        bot.send_message(chat_id, f"❌ حدث خطأ غير متوقع أثناء استدعاء الملف: {e}")

# ==========================================
# 6. نظام الذكاء الاصطناعي המضمون 100% (Fallback)
# ==========================================
def get_ai_response(prompt):
    if not GEMINI_API_KEY: return "❌ الذكاء الاصطناعي غير متصل. يرجى إضافة المفتاح السري."
    
    # قائمة الموديلات للطوارئ (الخفيف والسريع أولاً)
    models = [
        "gemini-2.0-flash-lite-preview-02-05", 
        "gemini-2.0-flash", 
        "gemini-1.5-flash", 
        "gemini-1.5-pro", 
        "gemini-pro"
    ]
    
    clean_prompt = f"أنت مساعد أكاديمي ذكي لطلاب علوم البيانات. أجب باختصار وبأسلوب مفيد: {prompt}"
    
    for model in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            data = {"contents": [{"parts": [{"text": clean_prompt}]}], "generationConfig": {"temperature": 0.5, "maxOutputTokens": 400}}
            response = requests.post(url, json=data, timeout=8) # وقت أسرع ليتنقل للموديل الآخر فوراً
            if response.status_code == 200:
                return response.json()['candidates'][0]['content']['parts'][0]['text']
        except Exception:
            continue # تخطى الخطأ وانتقل للموديل التالي فوراً
            
    return "🤖 أعتذر، يوجد ضغط هائل جداً على سيرفرات الذكاء الاصطناعي حالياً. سأكون متاحاً بعد لحظات."

# ==========================================
# 7. الأرشفة التلقائية للمجموعات (Auth)
# ==========================================
@bot.message_handler(commands=['auth'])
def auth_group(message):
    if message.chat.type in ['group', 'supergroup'] and message.from_user.id == SUPER_ADMIN_ID:
        auth_groups_col.update_one({"chat_id": message.chat.id}, {"$set": {"title": message.chat.title}}, upsert=True)
        bot.reply_to(message, "✅ تم اعتماد هذه المجموعة بنجاح للأرشفة.")

@bot.message_handler(commands=['unauth'])
def unauth_group(message):
    if message.chat.type in ['group', 'supergroup'] and message.from_user.id == SUPER_ADMIN_ID:
        auth_groups_col.delete_one({"chat_id": message.chat.id})
        bot.reply_to(message, "⛔ تم سحب الاعتماد.")

@bot.message_handler(content_types=['document', 'photo'], func=lambda m: m.chat.type in ['group', 'supergroup', 'channel'])
def auto_archive_handler(message):
    if not auth_groups_col.find_one({"chat_id": message.chat.id}): return 
    caption = message.caption or ""
    for tag_data in list(hashtags_col.find()):
        if tag_data['tag'] in caption:
            doc = build_file_doc(message, tag_data['path'])
            doc['name'] = doc['name'].replace(tag_data['tag'], "").strip() or "ملف مؤرشف"
            if doc['file_id']: files_col.insert_one(doc)
            break

# ==========================================
# 8. دوال بناء القوائم والعرض (القائمة الرئيسية)
# ==========================================
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
            markup.add("🏷️ إدارة الأرشفة والهاشتاجات")
            
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
        if is_super_admin(chat_id): markup.add("🔗 ربط هاشتاج بالقسم")

    bot.send_message(chat_id, f"📂 القسم الحالي: {path_str}", reply_markup=markup)

# ==========================================
# 9. أوامر البدء
# ==========================================
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
    bot.send_message(message.chat.id, "⛔ المنصة الأكاديمية مغلقة حالياً للصيانة بقرار من الإدارة العليا.")

# ==========================================
# 10. المعالج المركزي الذكي (Universal Handler)
# ==========================================
@bot.message_handler(content_types=['text', 'document', 'photo', 'video', 'audio'])
def universal_handler(message):
    chat_id = message.chat.id
    text = message.text if message.content_type == 'text' else ""
    path_str = get_path_string(chat_id)
    mode = admin_action_mode.get(chat_id)

    # ---> استقبال الملفات (مفردة ودفعة واحدة) <---
    if message.content_type in ['document', 'photo', 'video', 'audio'] and upload_mode.get(chat_id):
        if has_permission(chat_id, path_str):
            if getattr(message, "media_group_id", None):
                gid = str(message.media_group_id)
                if gid not in media_groups:
                    media_groups[gid] = []
                    threading.Thread(target=process_media_group, args=(chat_id, gid, path_str)).start()
                media_groups[gid].append(message)
            else:
                doc = build_file_doc(message, path_str)
                if doc['file_id']:
                    files_col.insert_one(doc)
                    bot.reply_to(message, f"✅ تمت الإضافة بنجاح: {doc['name']}")
            return

    # الإلغاء
    if text == "🛑 إلغاء الأمر":
        reset_modes(chat_id); bot.send_message(chat_id, "✅ تم إلغاء الإجراء."); show_menu(chat_id); return
    
    # التنقل
    if text in ["🔝 القائمة الرئيسية", "📚 تصفح بوت الدفعة"]:
        user_path[chat_id] = []; reset_modes(chat_id); show_menu(chat_id); return
    if text == "🔙 الرجوع للقائمة السابقة":
        if chat_id in user_path and user_path[chat_id]: user_path[chat_id].pop()
        reset_modes(chat_id); show_menu(chat_id); return

    # الميزات العامة
    if text == "🔥 الملفات الأكثر شعبية":
        top = list(files_col.find({"downloads": {"$gt": 0}}).sort("downloads", -1).limit(5))
        if not top: bot.send_message(chat_id, "لا توجد ملفات محملة بعد لتكوين الإحصائية.")
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
        info_text = ("🚀 *الذكاء الاصطناعي وعلوم البيانات*\n\nتخصص المستقبل ولغة العصر الحديث! يدمج بين قوة البرمجة، وعمق الرياضيات.\n🎓 أنت مهندس حلول المستقبل. استمر، فالعالم ينتظر إبداعك!")
        bot.send_message(chat_id, info_text, parse_mode="Markdown"); return
    if text == "👨‍💻 تواصل مع المطور":
        dev_text = ("👨‍💻 *دعم وتطوير المنصة:*\n\n🔹 *الواثق بالله عساج* ⇦ (@AlwatheqAssag)\n\nلأي استفسار تقني أو إضافة ملخصات، تواصل معي.")
        bot.send_message(chat_id, dev_text, parse_mode="Markdown"); return
    if text == "🔍 بحث عن ملف":
        reset_modes(chat_id); admin_action_mode[chat_id] = "search"
        bot.send_message(chat_id, "🔍 أرسل كلمة للبحث (مثال: محاضرة):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
        return
    
    # الذكاء الاصطناعي
    if text == "🤖 المساعد الذكي (AI)":
        reset_modes(chat_id); admin_action_mode[chat_id] = "ai_chat"
        bot.send_message(chat_id, "🤖 أهلاً بك! اطرح أي سؤال علمي أو برمجي:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
        return
    if mode == "ai_chat" and text:
        bot.send_message(chat_id, "⏳ جاري التفكير...")
        answer = get_ai_response(text)
        try: bot.send_message(chat_id, answer, parse_mode="Markdown")
        except: bot.send_message(chat_id, answer)
        reset_modes(chat_id); show_menu(chat_id); return

    # ---> إحصائيات المشتركين الكاملة للمدير <---
    if is_super_admin(chat_id) and text == "👥 إحصائيات المشتركين":
        users = list(users_col.find())
        msg = f"📊 *إحصائيات النظام الشاملة:*\n👥 الإجمالي: {len(users)} طالب\n📁 الملفات المرفوعة: {files_col.count_documents({})}\n\n👤 *قائمة المشتركين (الاسم | المعرف | الآيدي):*\n"
        for u in users:
            msg += f"• {u.get('first_name', 'مجهول')} | {u.get('username', 'لا يوجد')} | `{u.get('chat_id')}`\n"
        
        if len(msg) > 3500: # حماية تليجرام من الرسائل الطويلة
            with io.StringIO(msg) as f:
                f.name = "Students_Data.txt"
                bot.send_document(chat_id, f, caption="نظراً لعدد الطلاب، تم تصدير البيانات في هذا الملف 📄")
        else:
            bot.send_message(chat_id, msg, parse_mode="Markdown")
        return

    # باقي أوامر المدير
    if is_super_admin(chat_id):
        if text == "🏷️ إدارة الأرشفة والهاشتاجات":
            markup = ReplyKeyboardMarkup(resize_keyboard=True).add("📋 عرض الهاشتاجات", "🗑️ حذف هاشتاج", "🔝 القائمة الرئيسية")
            bot.send_message(chat_id, "🏷️ *نظام الأرشفة الذكي:*\nلإضافة مجموعة أرسل `/auth` فيها.", reply_markup=markup, parse_mode="Markdown")
            return
        if text == "📋 عرض الهاشتاجات":
            groups, tags = list(auth_groups_col.find()), list(hashtags_col.find())
            msg = "🛡️ *المجموعات المعتمدة:*\n"
            for g in groups: msg += f"▪️ {g.get('title', 'مجموعة')}\n"
            msg += "\n🏷️ *الهاشتاجات النشطة:*\n"
            for t in tags: msg += f"🔸 {t['tag']} ⇦ {t['path'].split('>')[-1]}\n"
            bot.send_message(chat_id, msg or "لا توجد بيانات.", parse_mode="Markdown"); return
        if text == "🗑️ حذف هاشتاج":
            reset_modes(chat_id); admin_action_mode[chat_id] = "del_hashtag"
            bot.send_message(chat_id, "أرسل الهاشتاج للحذف:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return
        if text == "🔗 ربط هاشتاج بالقسم":
            reset_modes(chat_id); admin_action_mode[chat_id] = "add_hashtag"
            bot.send_message(chat_id, "أرسل الهاشتاج لربطه بالقسم الحالي:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return
        if text == "🛠️ إدارة المشرفين":
            markup = ReplyKeyboardMarkup(resize_keyboard=True).add("➕ إضافة مشرف عام", "➕ إضافة مشرف مسار مخصص", "➖ إزالة مشرف", "🔝 القائمة الرئيسية")
            bot.send_message(chat_id, "🛠️ إدارة الصلاحيات:", reply_markup=markup); return
        if text == "➕ إضافة مشرف عام":
            reset_modes(chat_id); admin_action_mode[chat_id] = "add_global_admin"
            bot.send_message(chat_id, "أرسل الآيدي للمشرف العام:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return
        if text == "➕ إضافة مشرف مسار مخصص":
            reset_modes(chat_id); admin_action_mode[chat_id] = "add_path_admin_id"
            bot.send_message(chat_id, "الخطوة 1: أرسل الآيدي للمشرف:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return
        if text == "➖ إزالة مشرف":
            reset_modes(chat_id); admin_action_mode[chat_id] = "remove_admin"
            bot.send_message(chat_id, "أرسل الآيدي للإزالة:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return
        if text == "📢 إرسال رسالة جماعية":
            reset_modes(chat_id); broadcast_mode[chat_id] = True
            bot.send_message(chat_id, "📢 أرسل الرسالة الآن ليتم تعميمها:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return
        if text == "⚙️ التحكم بالنظام":
            status_btn = "▶️ تشغيل البوت" if not settings_col.find_one({"status": "active"}) else "⏸️ إيقاف البوت"
            bot.send_message(chat_id, "🛡️ مركز التحكم:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(status_btn, "🔝 القائمة الرئيسية")); return
        if text in ["▶️ تشغيل البوت", "⏸️ إيقاف البوت"]:
            status = "active" if text == "▶️ تشغيل البوت" else "inactive"
            settings_col.update_one({}, {"$set": {"status": status}}, upsert=True)
            bot.send_message(chat_id, f"✅ تم {'التشغيل' if status == 'active' else 'الإيقاف'}."); show_menu(chat_id); return

    # عمليات إدارة الأقسام
    if text == "🛑 إنهاء التجربة والعودة للإشراف":
        testing_mode[chat_id] = False; bot.send_message(chat_id, "💼 عادت الصلاحيات."); show_menu(chat_id); return
    
    if has_permission(chat_id, path_str):
        if text == "👤 تجربة كمستخدم":
            testing_mode[chat_id] = True; bot.send_message(chat_id, "👀 أنت تتصفح كطالب الآن."); show_menu(chat_id); return
        if text == "➕ إضافة ملف/نص":
            reset_modes(chat_id); upload_mode[chat_id] = True
            bot.send_message(chat_id, "📥 أرسل الملفات (واحد أو دفعة) أو النص الآن:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return
        if text == "📂 إضافة مجلد":
            reset_modes(chat_id); add_folder_mode[chat_id] = True
            bot.send_message(chat_id, "📂 اكتب اسم المجلد الجديد:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر")); return

    # التقاط المدخلات في الأوضاع المختلفة
    if text == "✅ تعيين صلاحية المشرف هنا" and mode == "add_path_admin_path":
        admins_col.update_one({"id": temp_data[chat_id]}, {"$set": {"type": "path"}, "$addToSet": {"allowed_paths": path_str}}, upsert=True)
        bot.send_message(chat_id, f"✅ أصبح مسؤولاً عن:\n{path_str}"); reset_modes(chat_id); show_menu(chat_id); return
    if text == "📦 أنقل الملف إلى هذا القسم" and mode == "move_file_dest":
        files_col.update_one({"_id": ObjectId(action_payload.get(chat_id))}, {"$set": {"menu_path": path_str}})
        bot.send_message(chat_id, f"📦 تم نقل الملف إلى:\n{path_str}"); reset_modes(chat_id); show_menu(chat_id); return

    if mode == "add_hashtag" and text and is_super_admin(chat_id):
        if not text.startswith("#"): text = "#" + text
        hashtags_col.insert_one({"tag": text.strip(), "path": path_str})
        bot.send_message(chat_id, f"✅ تم الربط."); reset_modes(chat_id); show_menu(chat_id); return
        
    if mode == "del_hashtag" and text and is_super_admin(chat_id):
        if not text.startswith("#"): text = "#" + text
        res = hashtags_col.delete_one({"tag": text.strip()})
        bot.send_message(chat_id, "✅ تم الحذف." if res.deleted_count > 0 else "❌ غير موجود.")
        reset_modes(chat_id); show_menu(chat_id); return

    if broadcast_mode.get(chat_id) and is_super_admin(chat_id):
        broadcast_mode[chat_id] = False
        bot.send_message(chat_id, "⏳ جاري الإرسال للكل...")
        success = 0
        for u in list(users_col.find()):
            try: bot.copy_message(u['chat_id'], chat_id, message.message_id); success += 1
            except: pass
        bot.send_message(chat_id, f"✅ أُرسلت إلى {success} طالب."); show_menu(chat_id); return

    if mode == "search" and text:
        results = list(files_col.find({"name": {"$regex": text, "$options": "i"}}).limit(7))
        if results:
            bot.send_message(chat_id, "🔍 *النتائج:*", parse_mode="Markdown")
            for r in results: bot.send_message(chat_id, f"📁 {r['menu_path']}"); send_file_to_user(chat_id, r, has_permission(chat_id, r['menu_path']))
        else: bot.send_message(chat_id, "❌ لا يوجد ملف مطابق.")
        reset_modes(chat_id); show_menu(chat_id); return

    if mode == "add_global_admin" and text and is_super_admin(chat_id):
        try:
            admins_col.update_one({"id": int(text.strip())}, {"$set": {"type": "global"}}, upsert=True)
            bot.send_message(chat_id, "✅ تمت الإضافة كمشرف عام.")
        except: bot.send_message(chat_id, "❌ أرقام فقط.")
        reset_modes(chat_id); show_menu(chat_id); return

    if mode == "remove_admin" and text and is_super_admin(chat_id):
        try:
            target = int(text.strip())
            if target != SUPER_ADMIN_ID: admins_col.delete_one({"id": target}); bot.send_message(chat_id, "✅ تم التجريد.")
        except: bot.send_message(chat_id, "❌ أرقام فقط.")
        reset_modes(chat_id); show_menu(chat_id); return

    if mode == "add_path_admin_id" and text and is_super_admin(chat_id):
        try:
            temp_data[chat_id] = int(text.strip()); admin_action_mode[chat_id] = "add_path_admin_path"; user_path[chat_id] = []
            bot.send_message(chat_id, "✅ تصفح للقسم ثم اضغط زر التعيين."); show_menu(chat_id)
        except: bot.send_message(chat_id, "❌ أرقام فقط.")
        return

    if mode == "rename_file" and text:
        files_col.update_one({"_id": ObjectId(action_payload.get(chat_id))}, {"$set": {"name": text.strip()}})
        bot.send_message(chat_id, "✅ تم تغيير الاسم."); reset_modes(chat_id); show_menu(chat_id); return

    if mode == "replace_file":
        doc = build_file_doc(message, path_str)
        if message.content_type in ['document', 'photo']:
            files_col.update_one({"_id": ObjectId(action_payload.get(chat_id))}, {"$set": {"type": doc['type'], "file_id": doc['file_id'], "name": doc['name']}})
        elif message.content_type == 'text':
            files_col.update_one({"_id": ObjectId(action_payload.get(chat_id))}, {"$set": {"type": "text", "content": text, "name": text[:25]}})
        bot.send_message(chat_id, "✅ تم الاستبدال."); reset_modes(chat_id); show_menu(chat_id); return

    if add_folder_mode.get(chat_id) and text and has_permission(chat_id, path_str):
        folders_col.insert_one({"parent_path": path_str, "folder_name": text.strip()})
        bot.send_message(chat_id, f"✅ تم إنشاء مجلد: {text.strip()}"); reset_modes(chat_id); show_menu(chat_id); return

    if upload_mode.get(chat_id) and message.content_type == 'text' and has_permission(chat_id, path_str):
        files_col.insert_one({"menu_path": path_str, "name": text[:30].strip(), "type": "text", "content": text, "downloads": 0, "upload_date": datetime.utcnow()})
        bot.send_message(chat_id, f"✅ تمت إضافة النص."); reset_modes(chat_id); show_menu(chat_id); return

    # ---> استدعاء الملفات الفعلي (الـ PDF) <---
    if text and (text.startswith("📄 ") or text.startswith("📌 ") or text.startswith("🖼️ ")):
        clean_name = text.replace("📄 ", "").replace("📌 ", "").replace("🖼️ ", "").strip()
        res = files_col.find_one({"menu_path": path_str, "name": clean_name})
        if not res: res = files_col.find_one({"menu_path": path_str, "name": {"$regex": re.escape(clean_name), "$options": "i"}})
        
        if res:
            files_col.update_one({"_id": res["_id"]}, {"$inc": {"downloads": 1}}) 
            send_file_to_user(chat_id, res, has_permission(chat_id, path_str))
        else: bot.send_message(chat_id, "❌ لم يتم العثور على الملف.")
        return

    # التصفح في القوائم
    if text.startswith("📁 "):
        user_path[chat_id].append(text.replace("📁 ", "").strip()); show_menu(chat_id); return

    current_menu = get_menu_by_path(user_path.get(chat_id, []))
    if isinstance(current_menu, dict) and text in current_menu:
        if chat_id not in user_path: user_path[chat_id] = []
        user_path[chat_id].append(text); show_menu(chat_id); return

# ==========================================
# 11. أزرار التحكم الجانبية
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith(('rn_', 'rp_', 'dl_', 'mv_')))
def handle_callbacks(call):
    chat_id = call.message.chat.id
    action, obj_id = call.data.split('_')
    
    doc = files_col.find_one({"_id": ObjectId(obj_id)})
    if not doc or not has_permission(chat_id, doc['menu_path']):
        bot.answer_callback_query(call.id, "❌ لا تملك صلاحية.", show_alert=True); return

    if action == 'dl':
        files_col.delete_one({"_id": ObjectId(obj_id)}); bot.delete_message(chat_id, call.message.message_id)
        bot.answer_callback_query(call.id, "🗑️ تم الحذف."); show_menu(chat_id)
    elif action == 'rn':
        reset_modes(chat_id); admin_action_mode[chat_id] = "rename_file"; action_payload[chat_id] = obj_id
        bot.send_message(chat_id, "✏️ أرسل الاسم الجديد:")
    elif action == 'rp':
        reset_modes(chat_id); admin_action_mode[chat_id] = "replace_file"; action_payload[chat_id] = obj_id
        bot.send_message(chat_id, "🔄 أرسل الملف البديل الآن:")
    elif action == 'mv':
        reset_modes(chat_id); admin_action_mode[chat_id] = "move_file_dest"; action_payload[chat_id] = obj_id
        user_path[chat_id] = []; show_menu(chat_id)

@app.route('/webhook', methods=['POST'])
def webhook_listen():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "!", 200

@app.route("/")
def home():
    return "The Ultimate Academic Bot is RUNNING flawlessly! 🚀", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
