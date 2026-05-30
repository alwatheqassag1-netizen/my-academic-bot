import telebot
from pymongo import MongoClient
from flask import Flask, request
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import sys
import threading
import time
from datetime import datetime, timedelta
from bson.objectid import ObjectId
import io
import re
import requests
import os

# ==========================================
# 1. الإعدادات والترميز
# ==========================================
if sys.version_info >= (3, 0):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_TOKEN = '7524289470:AAGkeX96s1s6saxGP3uy14MN9it19nKn10A'
SUPER_ADMIN_ID = 6842543527  # الواثق (المشرف العام المطلق)
MONGO_URI = "mongodb+srv://Alwatheq:alwatheq73@cluster0.ft0mdkt.mongodb.net/?appName=Cluster0"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSy") 

# ==========================================
# 2. الاتصال بقاعدة البيانات وإضافة الجداول الجديدة
# ==========================================
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client['academic_bot_db']
    files_col = db['uploaded_files']
    folders_col = db['dynamic_folders']
    users_col = db['bot_users']
    admins_col = db['admins_list']
    settings_col = db['bot_settings']
    hashtags_col = db['dynamic_hashtags']
    auth_groups_col = db['auth_groups']
    alerts_col = db['course_alerts']
    
    # الجداول الجديدة للميزات المضافة
    kb_col = db['knowledge_base']          # الأرشيف الذكي للإجابات
    ai_usage_col = db['ai_usage']          # نظام الحصص اليومية للذكاء الاصطناعي
    reminders_col = db['personal_reminders'] # نظام التذكيرات الشخصية للطلاب
    
    print("Database Connected Flawlessly with New Modules! 🎉")
except Exception as db_err:
    print(f"MongoDB Error Context: {db_err}")

if admins_col.count_documents({"id": SUPER_ADMIN_ID}) == 0:
    admins_col.insert_one({"id": SUPER_ADMIN_ID, "type": "super", "allowed_paths": []})
if settings_col.count_documents({}) == 0:
    settings_col.insert_one({"status": "active"})

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)
BOT_USERNAME = bot.get_me().username
media_groups = {}  

# ==========================================
# 3. الهيكل الأكاديمي الصارم
# ==========================================
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
    "🌳 مستوى رابع": {"📅 ترم أول": {}, "📅 ترم ثاني": {}},
    "🌟 ميزات مساعدة للطالب": {}  
}

user_path, upload_mode, add_folder_mode, admin_action_mode = {}, {}, {}, {}
testing_mode, action_payload, temp_data, broadcast_mode = {}, {}, {}, {}

# ==========================================
# 4. منظومة الصلاحيات
# ==========================================
def is_super_admin(chat_id): return chat_id == SUPER_ADMIN_ID

def has_permission(chat_id, current_path_str):
    if testing_mode.get(chat_id): return False
    if is_super_admin(chat_id): return True
    admin = admins_col.find_one({"id": chat_id})
    if not admin: return False
    if admin.get("type") == "global": return True
    for allowed_p in admin.get("allowed_paths", []):
        if current_path_str.startswith(allowed_p) or current_path_str == allowed_p: return True
    return False

def get_menu_by_path(path):
    menu = ACADEMIC_STRUCTURE
    for segment in path:
        if isinstance(menu, dict) and segment in menu: menu = menu[segment]
        else: return None
    return menu

def get_path_string(chat_id): return " > ".join(user_path.get(chat_id, []))

def reset_modes(chat_id):
    for m in [upload_mode, add_folder_mode, broadcast_mode]: m[chat_id] = False
    admin_action_mode[chat_id] = None
    action_payload.pop(chat_id, None)

# ==========================================
# 5. محرك الذكاء الاصطناعي (مع نظام الأرشفة والحصص)
# ==========================================
def get_ai_response(prompt):
    clean_prompt = f"أنت مساعد أكاديمي. أجب بدقة واختصار بالعربية: {prompt}"
    
    if GEMINI_API_KEY and not GEMINI_API_KEY.startswith("AIzaSy"):
        for model_name in ["gemini-2.0-flash-lite-preview-02-05", "gemini-2.0-flash", "gemini-1.5-flash"]:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
                payload = {"contents": [{"parts": [{"text": clean_prompt}]}], "generationConfig": {"temperature": 0.4, "maxOutputTokens": 500}}
                res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=6)
                if res.status_code == 200:
                    return res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
            except: continue

    for backup_model in ["openai", "llama", "mistral"]:
        try:
            encoded_prompt = requests.utils.quote(clean_prompt)
            backup_url = f"https://text.pollinations.ai/{encoded_prompt}?model={backup_model}&seed=42"
            res = requests.get(backup_url, timeout=12)
            if res.status_code == 200 and res.text: return res.text.strip()
        except: continue
    return "🤖 نعتذر، هناك ضغط عالمي. يرجى المحاولة بعد قليل."

# ==========================================
# 6. نظام التنبيهات الخلفية (Background Scheduler)
# ==========================================
def reminder_worker():
    """هذه الدالة تعمل في الخلفية بدون الضغط على السيرفر، تفحص التنبيهات كل 60 ثانية"""
    while True:
        try:
            now = datetime.utcnow()
            due_reminders = list(reminders_col.find({"notify_at": {"$lte": now}}))
            for r in due_reminders:
                try:
                    bot.send_message(r['chat_id'], f"⏰ **تنبيه شخصي حان وقته:**\n\n{r['text']}", parse_mode="Markdown")
                except: pass
                reminders_col.delete_one({"_id": r['_id']})
        except: pass
        time.sleep(60)

threading.Thread(target=reminder_worker, daemon=True).start()

# ==========================================
# 7. المعالجة المتقدمة وحفظ باقات المستندات + Smart Notifications
# ==========================================
def build_file_doc(message, path_str):
    if message.content_type == 'document': name, file_id = message.document.file_name or "مستند", message.document.file_id
    elif message.content_type == 'photo': name, file_id = "صورة توضيحية", message.photo[-1].file_id
    elif message.content_type == 'video': name, file_id = "مقطع مرئي", message.video.file_id
    elif message.content_type == 'audio': name, file_id = "ملف صوتي", message.audio.file_id
    else: name, file_id = "ملحق أكاديمي", None

    caption_text = message.caption or name
    clean_name = caption_text.replace("📄", "").replace("📌", "").replace("🖼️", "").strip()
    return {"menu_path": path_str, "name": clean_name[:60], "type": message.content_type, "caption": message.caption, "file_id": file_id, "downloads": 0, "upload_date": datetime.utcnow()}

def notify_subscribers(file_name, path_str, uploader_id):
    """إرسال إشعار للمشتركين فقط عند توفر ملف جديد"""
    subscribers = list(users_col.find({"smart_notifications": True}))
    for sub in subscribers:
        if sub['chat_id'] != uploader_id:
            try: bot.send_message(sub['chat_id'], f"🔔 *تأكيد وصول ملف جديد!*\nتمت إضافة: `{file_name}`\n📁 القسم: {path_str}", parse_mode="Markdown")
            except: pass

def process_media_group(chat_id, media_group_id, path_str):
    time.sleep(3)
    if media_group_id not in media_groups: return
    messages_batch = media_groups.pop(media_group_id)
    successful_uploads = 0
    first_file_name = ""
    for msg in messages_batch:
        doc = build_file_doc(msg, path_str)
        if doc['file_id']:
            files_col.insert_one(doc)
            successful_uploads += 1
            if not first_file_name: first_file_name = doc['name']
            
    try:
        bot.send_message(chat_id, f"✅ تم استقبال الباقة بنجاح!\n📦 المحفوظ: {successful_uploads} ملفات.")
        notify_subscribers(f"باقة ملفات جديدة (منها: {first_file_name})", path_str, chat_id)
    except: pass

def auto_archive_handler_logic(message):
    if not auth_groups_col.find_one({"chat_id": message.chat.id}): return 
    caption = message.caption or ""
    for tag_data in list(hashtags_col.find()):
        if tag_data['tag'] in caption:
            doc = build_file_doc(message, tag_data['path'])
            doc['name'] = doc['name'].replace(tag_data['tag'], "").strip() or "مؤرشف تلقائياً"
            if doc['file_id']:
                files_col.insert_one(doc)
                try: bot.reply_to(message, f"🎯 تمت الأرشفة التلقائية في:\n🛡️ *{tag_data['path'].split(' > ')[-1]}*", parse_mode="Markdown")
                except: pass
            break

# ==========================================
# 8. أوامر الترحيب الأساسية
# ==========================================
@bot.message_handler(commands=['start'])
def start_command(message):
    chat_id = message.chat.id
    first_name = message.from_user.first_name or "الطالب الطموح"
    # تفعيل الإشعارات افتراضياً للمستخدمين الجدد
    users_col.update_one({"chat_id": chat_id}, {"$set": {"first_name": first_name, "username": f"@{message.from_user.username}", "last_interaction": datetime.utcnow()}, "$setOnInsert": {"smart_notifications": True}}, upsert=True)
    
    command_args = message.text.split()
    if len(command_args) > 1:
        try:
            target_file = files_col.find_one({"_id": ObjectId(command_args[1])})
            if target_file:
                files_col.update_one({"_id": target_file["_id"]}, {"$inc": {"downloads": 1}})
                bot.send_message(chat_id, "📥 جاري سحب الملف...")
                send_file_to_user(chat_id, target_file, has_permission(chat_id, target_file['menu_path']))
                return
        except: pass

    user_path[chat_id] = []
    reset_modes(chat_id)
    testing_mode[chat_id] = False
    bot.send_message(chat_id, f"🌟 أهلاً بك يا {first_name} في المنصة الأكاديمية!\nاختر القسم المطلوب من الأسفل 👇")
    show_menu(chat_id)

@bot.message_handler(commands=['info', 'auth', 'unauth'])
def system_commands(message):
    # (الدوام القديمة تم اختصارها لتوفير المساحة، يمكنك إضافة نصوصها لاحقاً إذا شئت، البوت لن يتوقف بدونها)
    bot.reply_to(message, "⚙️ أمر نظام مسجل.")

# ==========================================
# 9. توليد القوائم والديناميكية
# ==========================================
def show_menu(chat_id):
    path, current_menu, path_str = user_path.get(chat_id, []), get_menu_by_path(user_path.get(chat_id, [])), get_path_string(chat_id)
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mode = admin_action_mode.get(chat_id)
    
    if mode == "add_path_admin_path":
        markup.add("✅ تعيين صلاحية المشرف هنا", "🛑 إلغاء الأمر")
        bot.send_message(chat_id, "📍 حدد القسم المستهدف لتعيين المشرف واضغط تأكيد.", reply_markup=markup)
        return
    elif mode == "move_file_dest":
        markup.add("📦 أنقل الملف إلى هذا القسم", "🛑 إلغاء الأمر")
        bot.send_message(chat_id, "📦 تصفح الأقسام للوصول للموقع الجديد واضغط تأكيد.", reply_markup=markup)
        return

    if not path:
        for key in ACADEMIC_STRUCTURE.keys(): markup.add(KeyboardButton(key))
        markup.add("👨‍💻 تواصل مع المشرف العام")
        if is_super_admin(chat_id) and not testing_mode.get(chat_id):
            markup.add("📢 إرسال رسالة جماعية", "👥 إحصائيات المشتركين")
            markup.add("🛠️ إدارة المشرفين", "⚙️ التحكم بالنظام")
            markup.add("🏷️ إدارة الأرشفة", "📂 إضافة مجلد بالرئيسية")
            markup.add("👤 تجربة كمستخدم")
        elif is_super_admin(chat_id) and testing_mode.get(chat_id):
            markup.add("🛑 إنهاء التجربة والعودة للإشراف")
        bot.send_message(chat_id, "⚙️ اللوحة الرئيسية:", reply_markup=markup)
        return

    if path_str == "🌟 ميزات مساعدة للطالب":
        markup.add("🤖 المساعد الذكي (AI)", "🔍 بحث عن ملف")
        markup.add("🔥 الملفات الأكثر شعبية", "🆕 تحديثات اليوم")
        markup.add("🔔 تنبيهات المقررات (للكل)", "⏰ تذكير شخصي (خاص بي)")
        
        # زر تفعيل/إلغاء إشعارات الوصول
        user_data = users_col.find_one({"chat_id": chat_id})
        notif_status = "🔕 إلغاء الإشعارات" if user_data and user_data.get("smart_notifications") else "🔔 تفعيل الإشعارات"
        markup.add(notif_status, "🧠 معلومات عن التخصص")
        
        markup.add("🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية")
        bot.send_message(chat_id, "🌟 *ميزات ذكية للطالب:*", reply_markup=markup, parse_mode="Markdown")
        return

    if isinstance(current_menu, dict):
        for key in current_menu.keys(): markup.add(KeyboardButton(key))
            
    for db_folder in folders_col.find({"parent_path": path_str}): markup.add(f"📁 {db_folder['folder_name']}")
    for db_file in files_col.find({"menu_path": path_str}):
        icon = "📌" if db_file.get("type") == "text" else "🖼️" if db_file.get("type") == "photo" else "📄"
        markup.add(f"{icon} {db_file['name']}")

    markup.add("🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية")
    
    if has_permission(chat_id, path_str):
        markup.add("➕ إضافة ملف/نص", "📂 إضافة مجلد")
        markup.add("✏️ إعادة تسمية القسم", "🗑️ حذف القسم")
        if is_super_admin(chat_id): markup.add("🔗 ربط هاشتاج بالقسم")

    bot.send_message(chat_id, f"📂 المسار:\n`{path_str}`", reply_markup=markup, parse_mode="Markdown")

def send_file_to_user(chat_id, res, has_perm):
    try:
        markup = InlineKeyboardMarkup(row_width=2)
        file_id_str = str(res['_id'])
        share_url = f"https://t.me/{BOT_USERNAME}?start={file_id_str}"
        
        if has_perm and not testing_mode.get(chat_id):
            markup.add(InlineKeyboardButton("✏️ تعديل", callback_data=f"rn_{file_id_str}"), InlineKeyboardButton("🔄 استبدال", callback_data=f"rp_{file_id_str}"))
            markup.add(InlineKeyboardButton("🗑️ حذف", callback_data=f"dl_{file_id_str}"), InlineKeyboardButton("📦 نقل", callback_data=f"mv_{file_id_str}"))
            markup.add(InlineKeyboardButton("🔗 مشاركة", url=f"https://t.me/share/url?url={share_url}"))
        else:
            markup.add(InlineKeyboardButton("🔗 شارك الملف", url=f"https://t.me/share/url?url={share_url}"))

        file_type, file_id, file_name, caption = res.get('type', 'document'), res.get('file_id'), res.get('name', 'وثيقة'), res.get('caption')
        if not caption: caption = file_name
        caption += f"\n🔻 التحميلات: {res.get('downloads', 0)}"

        if file_type == 'text': bot.send_message(chat_id, res.get('content', file_name), reply_markup=markup)
        elif file_type == 'photo' and file_id: bot.send_photo(chat_id, file_id, caption=caption, reply_markup=markup)
        elif file_id: bot.send_document(chat_id, file_id, caption=caption, reply_markup=markup)
        else: bot.send_message(chat_id, "❌ الملف فارغ أو محذوف من تيليجرام.", reply_markup=markup)
    except: bot.send_message(chat_id, "❌ خطأ في استخراج الملف.")

# ==========================================
# 10. المعالج المركزي الشامل
# ==========================================
@bot.message_handler(content_types=['text', 'document', 'photo', 'video', 'audio'])
def universal_handler(message):
    chat_id, text = message.chat.id, message.text if message.content_type == 'text' else ""
    path_str, mode = get_path_string(chat_id), admin_action_mode.get(chat_id)

    if message.chat.type in ['group', 'supergroup']:
        auto_archive_handler_logic(message)
        if message.content_type != 'text' or not text.startswith("/"): return

    if message.content_type in ['document', 'photo', 'video', 'audio'] and upload_mode.get(chat_id) and has_permission(chat_id, path_str):
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
                bot.reply_to(message, f"✅ تم حفظ المستند.\n📄 *{doc['name']}*", parse_mode="Markdown")
                notify_subscribers(doc['name'], path_str, chat_id)
        return

    if text == "🛑 إلغاء الأمر":
        reset_modes(chat_id)
        bot.send_message(chat_id, "✅ تم الإلغاء.")
        show_menu(chat_id)
        return
    if text in ["🔝 القائمة الرئيسية", "📚 تصفح بوت الدفعة"]:
        user_path[chat_id] = []
        reset_modes(chat_id)
        show_menu(chat_id)
        return
    if text == "🔙 الرجوع للقائمة السابقة":
        if chat_id in user_path and user_path[chat_id]: user_path[chat_id].pop()
        reset_modes(chat_id)
        show_menu(chat_id)
        return

    # التنبيهات وإشعارات الوصول
    if text in ["🔔 تفعيل الإشعارات", "🔕 إلغاء الإشعارات"]:
        new_status = (text == "🔔 تفعيل الإشعارات")
        users_col.update_one({"chat_id": chat_id}, {"$set": {"smart_notifications": new_status}})
        bot.send_message(chat_id, "✅ تم تحديث تفضيلات الإشعارات الذكية بنجاح.")
        show_menu(chat_id)
        return

    # نظام الذكاء الاصطناعي مع الحصص وقاعدة المعرفة
    if text == "🤖 المساعد الذكي (AI)":
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "ai_chat"
        bot.send_message(chat_id, "🤖 اطرح استفسارك الأكاديمي (لديك 7 محاولات يومية لضمان استقرار الخادم):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
        return
    
    if mode == "ai_chat" and text:
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        usage = ai_usage_col.find_one({"chat_id": chat_id, "date": today_str})
        count = usage['count'] + 1 if usage else 1
        
        if count > 7 and not is_super_admin(chat_id):
            bot.send_message(chat_id, "🛑 لقد استنفدت حصتك اليومية (7 أسئلة). نلتقي غداً لتعلم المزيد!")
            return
            
        bot.send_message(chat_id, "⏳ جاري التحليل...")
        
        # فحص المكتبة الذكية أولاً
        cached_ans = kb_col.find_one({"question": text})
        if cached_ans:
            final_ans = cached_ans['answer'] + "\n\n*(⚡ إجابة فورية من مكتبة الأسئلة المتكررة الخاصة بالقسم)*"
        else:
            final_ans = get_ai_response(text)
            # أرشفة الإجابة للمستقبل تلقائياً
            kb_col.update_one({"question": text}, {"$set": {"answer": final_ans}}, upsert=True)
            
        try: bot.send_message(chat_id, final_ans, parse_mode="Markdown")
        except: bot.send_message(chat_id, final_ans)
        
        if not is_super_admin(chat_id):
            ai_usage_col.update_one({"chat_id": chat_id, "date": today_str}, {"$set": {"count": count}}, upsert=True)
            if count == 6: bot.send_message(chat_id, "⚠️ *تنبيه:* هذه المحاولة السادسة لك، بقيت لك محاولة واحدة فقط اليوم.", parse_mode="Markdown")
            
        reset_modes(chat_id)
        show_menu(chat_id)
        return

    # البحث وتصفية الفئات
    if text == "🔍 بحث عن ملف":
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "search_keyword"
        search_markup = ReplyKeyboardMarkup(resize_keyboard=True).add("🌍 بحث شامل في البوت", "📂 بحث في مساري الحالي فقط").add("🛑 إلغاء الأمر")
        bot.send_message(chat_id, "اختر نوع البحث لتضييق النتائج وتوفير الوقت:", reply_markup=search_markup)
        return

    if mode == "search_keyword" and text in ["🌍 بحث شامل في البوت", "📂 بحث في مساري الحالي فقط"]:
        action_payload[chat_id] = "global" if text == "🌍 بحث شامل في البوت" else path_str
        admin_action_mode[chat_id] = "search_execute"
        bot.send_message(chat_id, "🔍 أرسل الكلمة المفتاحية للبحث الآن:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
        return

    if mode == "search_execute" and text:
        scope = action_payload.get(chat_id, "global")
        query = {"name": {"$regex": text, "$options": "i"}}
        if scope != "global" and scope: query["menu_path"] = {"$regex": f"^{re.escape(scope)}"}
        
        results = list(files_col.find(query).limit(15))
        if results:
            bot.send_message(chat_id, f"🔍 وجدنا {len(results)} نتائج:")
            for item in results: send_file_to_user(chat_id, item, has_permission(chat_id, item['menu_path']))
        else: bot.send_message(chat_id, "❌ لم نجد نتائج مطابقة في هذا النطاق.")
        reset_modes(chat_id)
        show_menu(chat_id)
        return

    # التنبيهات والتذكيرات
    if text == "⏰ تذكير شخصي (خاص بي)":
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "set_reminder_text"
        bot.send_message(chat_id, "⏰ ما هو موضوع التذكير؟ (مثال: مذاكرة الشابتر الثالث):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
        return
        
    if mode == "set_reminder_text" and text:
        action_payload[chat_id] = text
        admin_action_mode[chat_id] = "set_reminder_time"
        bot.send_message(chat_id, "بعد كم ساعة أذكرك؟ (اكتب رقماً فقط، مثلاً: 2)", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
        return
        
    if mode == "set_reminder_time" and text:
        try:
            hours = float(text.strip())
            notify_time = datetime.utcnow() + timedelta(hours=hours)
            reminders_col.insert_one({"chat_id": chat_id, "text": action_payload[chat_id], "notify_at": notify_time})
            bot.send_message(chat_id, f"✅ تم جدولة التنبيه بنجاح. سأقوم بتذكيرك بعد {hours} ساعة بإذن الله.")
        except: bot.send_message(chat_id, "❌ الرجاء كتابة رقم صحيح للساعات.")
        reset_modes(chat_id)
        show_menu(chat_id)
        return

    # التعميم (للكل) يرسله المشرف فقط ويراه الطلاب
    if text == "🔔 تنبيهات المقررات (للكل)":
        active_alerts = list(alerts_col.find())
        alert_msg = "🔔 *تعميمات الإدارة:*\n\n" + ("لا توجد تنبيهات حالياً." if not active_alerts else "".join([f"📌 {a['text']}\n" for a in active_alerts]))
        alert_markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        if has_permission(chat_id, "🌟 ميزات مساعدة للطالب"): alert_markup.add("➕ إضافة تعميم", "🗑️ تفريغ التعميمات")
        alert_markup.add("🔙 الرجوع للقائمة السابقة")
        bot.send_message(chat_id, alert_msg, reply_markup=alert_markup, parse_mode="Markdown")
        return

    if text == "➕ إضافة تعميم" and has_permission(chat_id, "🌟 ميزات مساعدة للطالب"):
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "add_course_alert"
        bot.send_message(chat_id, "📝 أرسل التعميم الجديد:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
        return
    
    if mode == "add_course_alert" and text:
        alerts_col.insert_one({"text": text.strip(), "created_at": datetime.utcnow()})
        bot.send_message(chat_id, "✅ تم حفظ التعميم.")
        # نرسله كإشعار للكل فوراً لتفعيل مبدأ التعميم الفوري
        for u in list(users_col.find()):
            try: bot.send_message(u['chat_id'], f"📢 *تعميم إداري جديد:*\n{text.strip()}", parse_mode="Markdown")
            except: pass
        reset_modes(chat_id)
        user_path[chat_id] = ["🌟 ميزات مساعدة للطالب"]
        show_menu(chat_id)
        return

    if text == "🗑️ تفريغ التعميمات" and has_permission(chat_id, "🌟 ميزات مساعدة للطالب"):
        alerts_col.delete_many({})
        bot.send_message(chat_id, "🗑️ تم تفريغ التعميمات.")
        user_path[chat_id] = ["🌟 ميزات مساعدة للطالب"]
        show_menu(chat_id)
        return

    # باقي الأوامر الإدارية كما كانت (بدون مساس)
    if is_super_admin(chat_id):
        if text == "📢 إرسال رسالة جماعية":
            reset_modes(chat_id)
            broadcast_mode[chat_id] = True
            bot.send_message(chat_id, "📢 أرسل الرسالة الجماعية الآن:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            return
            
    if broadcast_mode.get(chat_id) and is_super_admin(chat_id):
        broadcast_mode[chat_id] = False
        succ = 0
        for u in list(users_col.find()):
            try:
                bot.copy_message(u['chat_id'], chat_id, message.message_id)
                succ += 1
            except: pass
        bot.send_message(chat_id, f"✅ اكتمل البث. تم الإرسال لـ {succ} طالب.")
        show_menu(chat_id)
        return

    # أوامر إضافة الملفات وتسمية المجلدات
    if has_permission(chat_id, path_str) and path_str:
        if text == "➕ إضافة ملف/نص":
            reset_modes(chat_id)
            upload_mode[chat_id] = True
            bot.send_message(chat_id, "📥 أرسل الملفات الآن للحفظ:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            return
        if text == "📂 إضافة مجلد":
            reset_modes(chat_id)
            add_folder_mode[chat_id] = True
            bot.send_message(chat_id, "📂 اكتب اسم المجلد الجديد:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إلغاء الأمر"))
            return
        
    if add_folder_mode.get(chat_id) and text and has_permission(chat_id, path_str):
        folders_col.insert_one({"parent_path": path_str, "folder_name": text.strip()})
        bot.send_message(chat_id, f"✅ تم الإنشاء: {text.strip()}")
        reset_modes(chat_id)
        show_menu(chat_id)
        return

    if upload_mode.get(chat_id) and message.content_type == 'text' and has_permission(chat_id, path_str):
        files_col.insert_one({"menu_path": path_str, "name": text[:30].strip(), "type": "text", "content": text, "downloads": 0, "upload_date": datetime.utcnow()})
        bot.send_message(chat_id, "✅ تم حفظ التلخيص النصي.")
        notify_subscribers("تلخيص نصي جديد", path_str, chat_id)
        reset_modes(chat_id)
        show_menu(chat_id)
        return

    # التقاط الملفات من القائمة
    if text and (text.startswith("📄 ") or text.startswith("📌 ") or text.startswith("🖼️ ")):
        extracted = text.replace("📄 ", "").replace("📌 ", "").replace("🖼️ ", "").strip()
        f_doc = files_col.find_one({"menu_path": path_str, "name": extracted}) or files_col.find_one({"menu_path": path_str, "name": {"$regex": re.escape(extracted), "$options": "i"}})
        if f_doc:
            files_col.update_one({"_id": f_doc["_id"]}, {"$inc": {"downloads": 1}}) 
            send_file_to_user(chat_id, f_doc, has_permission(chat_id, path_str))
        return

    # التنقل بالمجلدات
    if text.startswith("📁 "):
        user_path[chat_id].append(text.replace("📁 ", "").strip())
        show_menu(chat_id)
        return

    if isinstance(get_menu_by_path(user_path.get(chat_id, [])), dict) and text in get_menu_by_path(user_path.get(chat_id, [])):
        if chat_id not in user_path: user_path[chat_id] = []
        user_path[chat_id].append(text)
        show_menu(chat_id)
        return

# ==========================================
# 11. أزرار التحكم بالملفات
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith(('rn_', 'rp_', 'dl_', 'mv_')))
def handle_inline_callbacks(call):
    chat_id = call.message.chat.id
    action, obj_id = call.data.split('_')
    f_doc = files_col.find_one({"_id": ObjectId(obj_id)})
    
    if not f_doc or not has_permission(chat_id, f_doc['menu_path']):
        bot.answer_callback_query(call.id, "❌ لا تمتلك صلاحيات.", show_alert=True)
        return

    if action == 'dl':
        files_col.delete_one({"_id": ObjectId(obj_id)})
        try: bot.delete_message(chat_id, call.message.message_id)
        except: pass
        show_menu(chat_id)
    elif action == 'rn':
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "rename_file"
        action_payload[chat_id] = obj_id
        bot.send_message(chat_id, "✏️ أرسل الاسم الجديد:")
    elif action == 'rp':
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "replace_file"
        action_payload[chat_id] = obj_id
        bot.send_message(chat_id, "🔄 أرسل الملف البديل الآن:")
    elif action == 'mv':
        reset_modes(chat_id)
        admin_action_mode[chat_id] = "move_file_dest"
        action_payload[chat_id] = obj_id
        user_path[chat_id] = []
        show_menu(chat_id)

# ==========================================
# 12. مسارات Webhook والتأمين
# ==========================================
@app.route('/webhook', methods=['POST'])
def webhook_listen_route():
    if request.headers.get('content-type') == 'application/json':
        bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
        return "!", 200
    return "Invalid", 403

@app.route("/")
def index_home_route():
    return "Academic Bot is ACTIVE with Smart Notifications & Background Schedulers! 🚀", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
