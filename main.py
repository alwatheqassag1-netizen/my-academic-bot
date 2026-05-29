import telebot
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import DictCursor
from flask import Flask, request
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
import sys

# ضمان قراءة النصوص والإيموجيات العربية بشكل صحيح داخل السيرفر
if sys.version_info >= (3, 0):
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_TOKEN = '7524289470:AAGkeX96s1s6saxGP3uy14MN9it19nKn10A'
ADMIN_IDS = [6842543527, 5585934059, 1084564343] 

# 🔐 تم تحديث كلمة المرور الصحيحة بنجاح هنا: alwatheq733
DATABASE_URL = "postgresql://postgres:alwatheq733@db.jknojabyblhpoudaowzr.supabase.co:5432/postgres"

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)

# --- مجمع اتصالات آمن ومحسن ---
try:
    db_pool = ThreadedConnectionPool(1, 10, DATABASE_URL)
except Exception as e:
    print(f"Error creating connection pool: {e}")
    db_pool = None

def get_db_connection():
    if db_pool:
        return db_pool.getconn()
    return psycopg2.connect(DATABASE_URL)

def release_db_connection(conn):
    if db_pool:
        db_pool.putconn(conn)
    else:
        conn.close()

# --- نظام إنشاء الجداول التلقائي والمؤمن ---
def init_db():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS items 
                          (id SERIAL PRIMARY KEY, name TEXT, type TEXT, file_id TEXT, parent_id INTEGER)''')
        cursor.execute('CREATE TABLE IF NOT EXISTS users (chat_id BIGINT PRIMARY KEY)')
        conn.commit()
        
        cursor.execute('SELECT COUNT(*) FROM items')
        if cursor.fetchone()[0] == 0:
            levels = ["🌱 مستوى أول", "🌿 مستوى ثاني", "☘️ مستوى ثالث", "🌳 مستوى رابع"]
            for l in levels: 
                cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (%s, \'مجلد\', 0)', (l,))
            conn.commit()
            
            # بناء هيكل الأترام بناء على الـ IDs المنشأة
            for parent_level_id in [1, 2, 3, 4]:
                cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (\'📅 ترم أول\', \'مجلد\', %s)', (parent_level_id,))
                cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (\'📅 ترم ثاني\', \'مجلد\', %s)', (parent_level_id,))
            conn.commit()
            
            # ربط المواد بالترم الثاني للمستوى الأول (تلقائياً ID: 6)
            subjects = [
                "📖 الثقافة الإسلامية", 
                "🌙 لغة عربية 2", 
                "🇬🇧 لغة إنجليزية 2", 
                "📈 تفاضل وتكامل 2", 
                "📊 مقدمة في علوم البيانات", 
                "💻 برمجة حاسوب", 
                "🗂️ رياضيات متقطعة"
            ]
            for s in subjects: 
                cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (%s, \'مجلد\', 6)', (s,))
            conn.commit()
            
            # المجلدات الفرعية للمواد العامة (IDs: 13, 14, 15)
            for i in [13, 14, 15]:
                cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (\'📂 محاضرات وملخصات\', \'مجلد\', %s)', (i,))
                cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (\'📝 نماذج اختبارات\', \'مجلد\', %s)', (i,))
                
            # التفاضل والتكامل 2 -> ID: 16
            calc_sub = ["📂 محاضرات نظري", "📐 محاضرات تمارين", "📝 نماذج اختبارات نظري", "✍️ نماذج تمارين", "📚 مراجع خارجية"]
            for c in calc_sub: cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (%s, \'مجلد\', 16)', (c,))
            
            # علوم البيانات -> ID: 17
            data_sub = ["👨‍🏫 محاضرات المهندس", "📜 ملخص محاضرات", "⚙️ محاضرات العملي", "📝 نماذج اختبارات نظري"]
            for d in data_sub: cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (%s, \'مجلد\', 17)', (d,))
            
            # برمجة حاسوب -> ID: 18
            prog_sub = ["📂 محاضرات نظري", "🖥️ محاضرات العملي", "📝 نماذج اختبارات", "🚀 التمارين والمشاريع العملية"]
            for p in prog_sub: cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (%s, \'مجلد\', 18)', (p,))
            
            # رياضيات متقطعة -> ID: 19
            math_sub = ["📂 محاضرات نظري", "✏️ محاضرات تمارين", "📝 نماذج اختبارات", "📚 مراجع خارجية"]
            for m in math_sub: cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (%s, \'مجلد\', 19)', (m,))
            
            conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error initializing database: {e}")

init_db()

testing_mode = {}
user_history = {}
upload_mode = {}

def get_current_parent(chat_id):
    if chat_id not in user_history or not user_history[chat_id]:
        user_history[chat_id] = [0]
    return user_history[chat_id][-1]

def show_menu(chat_id):
    parent_id = get_current_parent(chat_id)
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=DictCursor)
        cursor.execute('SELECT name, type, file_id FROM items WHERE parent_id = %s', (parent_id,))
        items = cursor.fetchall()
        cursor.close()
    finally:
        release_db_connection(conn)
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    files_count = 0
    for item in items:
        markup.add(KeyboardButton(item['name']))
        if item['type'] == "ملف": files_count += 1
    
    if parent_id == 0:
        markup.add("👨‍💻 تواصل مع المطور")
    
    if parent_id != 0:
        markup.add("🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية")
    
    if testing_mode.get(chat_id):
        markup.add("🛑 إنهاء التجربة والعودة للإشراف")
    elif chat_id in ADMIN_IDS:
        markup.add("👤 تجربة كمستخدم")
        markup.add("⚙️ إدارة هذه القائمة")
            
    if parent_id == 0:
        msg_text = (
            "مرحباً بك في المنصة الأكاديمية لقسم الذكاء الاصطناعي وعلوم البيانات (الدفعة الثانية) 🎓\n\n"
            "نضع بين يديك هذا البوت ليكون دليلك الشامل ومكتبتك المتكاملة؛ حيث يوفر لك وصولاً سهلاً وسريعاً لكافة المحاضرات، الملخصات، النماذج، والاختبارات، بالإضافة إلى التمارين والمراجعات.\n\n"
            "👇 فضلاً، اختر مستواك الدراسي من القائمة أدناه للبدء:"
        )
    else:
        msg_text = "اختر من القائمة أدناه:"
        if files_count > 0: msg_text += "\n(🗂️ يوجد ملفات جاهزة للتحميل)"
        
    bot.send_message(chat_id, msg_text, reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users (chat_id) VALUES (%s) ON CONFLICT (chat_id) DO NOTHING', (chat_id,))
        conn.commit()
        cursor.close()
    finally:
        release_db_connection(conn)
    user_history[chat_id] = [0]
    testing_mode[chat_id] = False
    upload_mode[chat_id] = False
    show_menu(chat_id)

@bot.message_handler(commands=['users'])
def list_users(message):
    if message.chat.id in ADMIN_IDS:
        conn = get_db_connection()
        try:
            cursor = conn.cursor(cursor_factory=DictCursor)
            cursor.execute('SELECT chat_id FROM users')
            users = cursor.fetchall()
            cursor.close()
        finally:
            release_db_connection(conn)
        if users:
            user_list = "\n".join([str(u['chat_id']) for u in users])
            bot.send_message(message.chat.id, f"👥 عدد المشتركين: {len(users)}\n\nقائمة أرقام التعريف (IDs):\n{user_list}")
        else:
            bot.send_message(message.chat.id, "❌ لا يوجد مستخدمون حالياً.")

@bot.message_handler(func=lambda m: m.text == "⚙️ إدارة هذه القائمة" and m.chat.id in ADMIN_IDS and not testing_mode.get(m.chat.id))
def manage_current_menu(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("➕ إضافة ملف", "📁 إدارة خيار جديد")
    markup.add("✏️ تعديل اسم", "🗑️ حذف خيار/ملف")
    markup.add("الغاء الأمر ❌")
    bot.send_message(message.chat.id, "🛠️ أنت تتحكم الآن في هذه القائمة، ماذا تريد أن تفعل؟", reply_markup=markup)

@bot.message_handler(func=lambda m: m.chat.id in ADMIN_IDS and m.text in ["➕ إضافة ملف", "📁 إدارة خيار جديد", "✏️ تعديل اسم", "🗑️ حذف خيار/ملف", "الغاء الأمر ❌"])
def admin_action(message):
    chat_id = message.chat.id
    if message.text == "الغاء الأمر ❌":
        upload_mode[chat_id] = False
        show_menu(chat_id)
    elif message.text == "➕ إضافة ملف":
        upload_mode[chat_id] = True
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("🛑 إنهاء إضافة الملفات")
        bot.send_message(chat_id, "📥 وضع الرفع المتعدد مُفعّل وبأعلى كفاءة الآن!\nأرسل ملفاتك دفعة واحدة.\n\nعند الانتهاء تماماً اضغط على الزر أدناه 👇", reply_markup=markup)
    elif message.text == "📁 إدارة خيار جديد":
        msg = bot.send_message(chat_id, "📥 أرسل اسم المجلد أو الخيار الجديد:")
        bot.register_next_step_handler(msg, receive_folder)
    elif message.text == "✏️ تعديل اسم":
        msg = bot.send_message(chat_id, "✏️ أرسل التعديل بالصيغة التالية تماماً:\nالاسم القديم, الاسم الجديد")
        bot.register_next_step_handler(msg, receive_rename)
    elif message.text == "🗑️ حذف خيار/ملف":
        msg = bot.send_message(chat_id, "🗑️ أرسل بدقة اسم الملف أو المجلد الذي تريد حذفه بشكل نهائي من هذه القائمة:")
        bot.register_next_step_handler(msg, receive_delete)

@bot.message_handler(content_types=['document'], func=lambda m: m.chat.id in ADMIN_IDS and upload_mode.get(m.chat.id) == True)
def receive_multiple_files(message):
    parent_id = get_current_parent(message.chat.id)
    file_name = message.caption if message.caption else message.document.file_name
    file_id = message.document.file_id
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO items (name, type, file_id, parent_id) VALUES (%s, \'ملف\', %s, %s)', (file_name, file_id, parent_id))
        conn.commit()
        cursor.close()
        bot.send_message(message.chat.id, f"✅ تم حفظ '{file_name}' بنجاح!")
    except Exception as e:
        print(f"Database error during file save: {e}")
        conn.rollback()
    finally:
        release_db_connection(conn)

def receive_folder(message):
    parent_id = get_current_parent(message.chat.id)
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (%s, \'مجلد\', %s)', (message.text, parent_id))
        conn.commit()
        cursor.close()
    finally:
        release_db_connection(conn)
    bot.send_message(message.chat.id, f"✅ تم إضافة '{message.text}' بنجاح!")
    show_menu(message.chat.id)

def receive_rename(message):
    try:
        old, new = message.text.split(", ")
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('UPDATE items SET name = %s WHERE name = %s AND parent_id = %s', (new, old, get_current_parent(message.chat.id)))
            conn.commit()
            cursor.close()
        finally:
            release_db_connection(conn)
        bot.send_message(message.chat.id, "✅ تم التعديل بنجاح!")
        show_menu(message.chat.id)
    except:
        bot.send_message(message.chat.id, "❌ خطأ في الصيغة. تأكد من وضع فاصلة بين الاسمين.")
        show_menu(message.chat.id)

def receive_delete(message):
    parent_id = get_current_parent(message.chat.id)
    name_to_delete = message.text
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=DictCursor)
        cursor.execute('SELECT id FROM items WHERE name = %s AND parent_id = %s', (name_to_delete, parent_id))
        item = cursor.fetchone()
        if item:
            cursor.execute('DELETE FROM items WHERE name = %s AND parent_id = %s', (name_to_delete, parent_id))
            conn.commit()
            bot.send_message(message.chat.id, f"✅ تم حذف '{name_to_delete}' بنجاح!")
        else:
            bot.send_message(message.chat.id, "❌ لم يتم العثور على هذا الاسم.")
        cursor.close()
    finally:
        release_db_connection(conn)
    show_menu(message.chat.id)

@bot.message_handler(func=lambda message: True)
def handle_nav(message):
    chat_id = message.chat.id
    text = message.text
    
    if text == "🛑 إنهاء إضافة الملفات" and chat_id in ADMIN_IDS:
        upload_mode[chat_id] = False
        bot.send_message(chat_id, "🔒 تم إغلاق وضع الرفع بنجاح والعودة للقائمة.")
        show_menu(chat_id)
        return
    
    if text == "🛑 إنهاء التجربة والعودة للإشراف":
        testing_mode[chat_id] = False
        show_menu(chat_id)
        return
    elif text == "👤 تجربة كمستخدم":
        testing_mode[chat_id] = True
        show_menu(chat_id)
        return
        
    if text == "🔝 القائمة الرئيسية":
        user_history[chat_id] = [0]
        show_menu(chat_id)
        return
    elif text == "🔙 الرجوع للقائمة السابقة":
        if len(user_history.get(chat_id, [])) > 1:
            user_history[chat_id].pop()
        show_menu(chat_id)
        return
        
    if text == "👨‍💻 تواصل مع المطور":
        msg_dev = (
            "مرحباً بك في ركن الدعم الفني والاستقبال الخاص بالمنصة.\n\n"
            "نسعد بتلقي استفساراتكم ومقترحاتكم البنّاءة، كما نرحب بمساهماتكم العلمية التي تثري المحتوى وتفيد الجميع.\n\n"
            "👥 طاقم الإشراف والدعم الفني الحالي:\n"
            "🔹 المشرف المندوب: الواثق بالله عساج (@AlwatheqAssag)\n"
            "🔹 مشرف المنصة: جلال المهدي (@jalal_almahdy)\n"
            "🔹 مشرف المنصة: براء حسن (@br44ai)\n\n"
            "معاً.. نصنع تجربة أكاديمية أسهل وأكثر فائدة. نحن بانتظار رسائلكم!"
        )
        bot.send_message(chat_id, msg_dev)
        return

    parent_id = get_current_parent(chat_id)
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=DictCursor)
        cursor.execute('SELECT id, type, file_id FROM items WHERE name = %s AND parent_id = %s', (text, parent_id))
        item = cursor.fetchone()
        cursor.close()
    finally:
        release_db_connection(conn)
    
    if item:
        if item['type'] == "مجلد":
            user_history[chat_id].append(item['id'])
            show_menu(chat_id)
        else:
            bot.send_document(chat_id, item['file_id'])

# --- نقطة استقبال الـ Webhook الفورية الخاصة بـ Flask ---
@app.route('/' + API_TOKEN, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook():
    bot.remove_webhook()
    return "Bot is running via Webhook & Supabase securely!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS items 
                      (id SERIAL PRIMARY KEY, name TEXT, type TEXT, file_id TEXT, parent_id INTEGER)''')
    cursor.execute('CREATE TABLE IF NOT EXISTS users (chat_id BIGINT PRIMARY KEY)')
    conn.commit()
    
    cursor.execute('SELECT COUNT(*) FROM items')
    if cursor.fetchone()[0] == 0:
        levels = ["🌱 مستوى أول", "🌿 مستوى ثاني", "☘️ مستوى ثالث", "🌳 مستوى رابع"]
        for l in levels: 
            cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (%s, \'مجلد\', 0)', (l,))
        conn.commit()
        
        for parent_level_id in [1, 2, 3, 4]:
            cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (\'📅 ترم أول\', \'مجلد\', %s)', (parent_level_id,))
            cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (\'📅 ترم ثاني\', \'مجلد\', %s)', (parent_level_id,))
        conn.commit()
        
        # ربط المواد بالترم الثاني للمستوى الأول (ID: 6) مع إيموجيات مخصصة ورسمية
        subjects = [
            "📖 الثقافة الإسلامية", 
            "🌙 لغة عربية 2", 
            "🇬🇧 لغة إنجليزية 2", 
            "📈 تفاضل وتكامل 2", 
            "📊 مقدمة في علوم البيانات", 
            "💻 برمجة حاسوب", 
            "🧮 رياضيات متقطعة"
        ]
        for s in subjects: 
            cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (%s, \'مجلد\', 6)', (s,))
        conn.commit()
        
        # المجلدات الفرعية للمواد العامة (ثقافة، عربي، إنجليزي) -> IDs: 13, 14, 15
        for i in [13, 14, 15]:
            cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (\'📂 محاضرات وملخصات\', \'مجلد\', %s)', (i,))
            cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (\'📝 نماذج اختبارات\', \'مجلد\', %s)', (i,))
            
        # التفاضل والتكامل 2 -> ID: 16
        calc_sub = ["📂 محاضرات نظري", "📐 محاضرات تمارين", "📝 نماذج اختبارات نظري", "✍️ نماذج تمارين", "📚 مراجع خارجية"]
        for c in calc_sub: cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (%s, \'مجلد\', 16)', (c,))
        
        # علوم البيانات -> ID: 17
        data_sub = ["👨‍🏫 محاضرات المهندس", "📜 ملخص محاضرات", "⚙️ محاضرات العملي", "📝 نماذج اختبارات نظري"]
        for d in data_sub: cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (%s, \'مجلد\', 17)', (d,))
        
        # برمجة حاسوب -> ID: 18
        prog_sub = ["📂 محاضرات نظري", "🖥️ محاضرات العملي", "📝 نماذج اختبارات", "🚀 التمارين والمشاريع العملية"]
        for p in prog_sub: cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (%s, \'مجلد\', 18)', (p,))
        
        # رياضيات متقطعة -> ID: 19
        math_sub = ["📂 محاضرات نظري", "✏️ محاضرات تمارين", "📝 نماذج اختبارات", "📚 مراجع خارجية"]
        for m in math_sub: cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (%s, \'مجلد\', 19)', (m,))
        
        conn.commit()
    cursor.close()
    conn.close()

init_db()

testing_mode = {}
user_history = {}
upload_mode = {}

def get_current_parent(chat_id):
    if chat_id not in user_history or not user_history[chat_id]:
        user_history[chat_id] = [0]
    return user_history[chat_id][-1]

def show_menu(chat_id):
    parent_id = get_current_parent(chat_id)
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute('SELECT name, type, file_id FROM items WHERE parent_id = %s', (parent_id,))
    items = cursor.fetchall()
    cursor.close()
    release_db_connection(conn)
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    files_count = 0
    for item in items:
        markup.add(KeyboardButton(item['name']))
        if item['type'] == "ملف": files_count += 1
    
    if parent_id == 0:
        markup.add("👨‍💻 تواصل مع المطور")
    
    if parent_id != 0:
        markup.add("🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية")
    
    if testing_mode.get(chat_id):
        markup.add("🛑 إنهاء التجربة والعودة للإشراف")
    elif chat_id in ADMIN_IDS:
        markup.add("👤 تجربة كمستخدم")
        markup.add("⚙️ إدارة هذه القائمة")
            
    if parent_id == 0:
        msg_text = (
            "مرحباً بك في المنصة الأكاديمية لقسم الذكاء الاصطناعي وعلوم البيانات (الدفعة الثانية) 🎓\n\n"
            "نضع بين يديك هذا البوت ليكون دليلك الشامل ومكتبتك المتكاملة؛ حيث يوفر لك وصولاً سهلاً وسريعاً لكافة المحاضرات، الملخصات، النماذج، والاختبارات، بالإضافة إلى التمارين والمراجعات.\n\n"
            "👇 فضلاً، اختر مستواك الدراسي من القائمة أدناه للبدء:"
        )
    else:
        msg_text = "اختر من القائمة أدناه:"
        if files_count > 0: msg_text += "\n(🗂️ يوجد ملفات جاهزة للتحميل)"
        
    bot.send_message(chat_id, msg_text, reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO users (chat_id) VALUES (%s) ON CONFLICT (chat_id) DO NOTHING', (chat_id,))
    conn.commit()
    cursor.close()
    release_db_connection(conn)
    user_history[chat_id] = [0]
    testing_mode[chat_id] = False
    upload_mode[chat_id] = False
    show_menu(chat_id)

@bot.message_handler(commands=['users'])
def list_users(message):
    if message.chat.id in ADMIN_IDS:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        cursor.execute('SELECT chat_id FROM users')
        users = cursor.fetchall()
        cursor.close()
        release_db_connection(conn)
        if users:
            user_list = "\n".join([str(u['chat_id']) for u in users])
            bot.send_message(message.chat.id, f"👥 عدد المشتركين: {len(users)}\n\nقائمة أرقام التعريف (IDs):\n{user_list}")
        else:
            bot.send_message(message.chat.id, "❌ لا يوجد مستخدمون حالياً.")

@bot.message_handler(func=lambda m: m.text == "⚙️ إدارة هذه القائمة" and m.chat.id in ADMIN_IDS and not testing_mode.get(m.chat.id))
def manage_current_menu(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("➕ إضافة ملف", "📁 إضافة مجلد/خيار")
    markup.add("✏️ تعديل اسم", "🗑️ حذف خيار/ملف")
    markup.add("الغاء الأمر ❌")
    bot.send_message(message.chat.id, "🛠️ أنت تتحكم الآن في هذه القائمة، ماذا تريد أن تفعل؟", reply_markup=markup)

@bot.message_handler(func=lambda m: m.chat.id in ADMIN_IDS and m.text in ["➕ إضافة ملف", "📁 إضافة مجلد/خيار", "✏️ تعديل اسم", "🗑️ حذف خيار/ملف", "الغاء الأمر ❌"])
def admin_action(message):
    chat_id = message.chat.id
    if message.text == "الغاء الأمر ❌":
        upload_mode[chat_id] = False
        show_menu(chat_id)
    elif message.text == "➕ إضافة ملف":
        upload_mode[chat_id] = True
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("🛑 إنهاء إضافة الملفات")
        bot.send_message(chat_id, "📥 وضع الرفع المتعدد مُفعّل وبأعلى كفاءة الآن!\nأرسل ملفاتك دفعة واحدة (6 ملفات أو أكثر معاً).\n\nعند الانتهاء تماماً اضغط على الزر أدناه 👇", reply_markup=markup)
    elif message.text == "📁 إضافة مجلد/خيار":
        msg = bot.send_message(chat_id, "📥 أرسل اسم المجلد أو الخيار الجديد:")
        bot.register_next_step_handler(msg, receive_folder)
    elif message.text == "✏️ تعديل اسم":
        msg = bot.send_message(chat_id, "✏️ أرسل التعديل بالصيغة التالية تماماً:\nالاسم القديم, الاسم الجديد")
        bot.register_next_step_handler(msg, receive_rename)
    elif message.text == "🗑️ حذف خيار/ملف":
        msg = bot.send_message(chat_id, "🗑️ أرسل بدقة اسم الملف أو المجلد الذي تريد حذفه بشكل نهائي من هذه القائمة:")
        bot.register_next_step_handler(msg, receive_delete)

@bot.message_handler(content_types=['document'], func=lambda m: m.chat.id in ADMIN_IDS and upload_mode.get(m.chat.id) == True)
def receive_multiple_files(message):
    parent_id = get_current_parent(message.chat.id)
    file_name = message.caption if message.caption else message.document.file_name
    file_id = message.document.file_id
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO items (name, type, file_id, parent_id) VALUES (%s, \'ملف\', %s, %s)', (file_name, file_id, parent_id))
        conn.commit()
        cursor.close()
        bot.send_message(message.chat.id, f"✅ تم حفظ '{file_name}' بنجاح!")
    except Exception as e:
        print(f"Database error during file save: {e}")
        conn.rollback()
    finally:
        release_db_connection(conn)

def receive_folder(message):
    parent_id = get_current_parent(message.chat.id)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (%s, \'مجلد\', %s)', (message.text, parent_id))
    conn.commit()
    cursor.close()
    release_db_connection(conn)
    bot.send_message(message.chat.id, f"✅ تم إضافة '{message.text}' بنجاح!")
    show_menu(message.chat.id)

def receive_rename(message):
    try:
        old, new = message.text.split(", ")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE items SET name = %s WHERE name = %s AND parent_id = %s', (new, old, get_current_parent(message.chat.id)))
        conn.commit()
        cursor.close()
        release_db_connection(conn)
        bot.send_message(message.chat.id, "✅ تم التعديل بنجاح!")
        show_menu(message.chat.id)
    except:
        bot.send_message(message.chat.id, "❌ خطأ في الصيغة. تأكد من وضع فاصلة بين الاسمين.")
        show_menu(message.chat.id)

def receive_delete(message):
    parent_id = get_current_parent(message.chat.id)
    name_to_delete = message.text
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute('SELECT id FROM items WHERE name = %s AND parent_id = %s', (name_to_delete, parent_id))
    item = cursor.fetchone()
    if item:
        cursor.execute('DELETE FROM items WHERE name = %s AND parent_id = %s', (name_to_delete, parent_id))
        conn.commit()
        bot.send_message(message.chat.id, f"✅ تم حذف '{name_to_delete}' بنجاح!")
    else:
        bot.send_message(message.chat.id, "❌ لم يتم العثور على هذا الاسم.")
    cursor.close()
    release_db_connection(conn)
    show_menu(message.chat.id)

@bot.message_handler(func=lambda message: True)
def handle_nav(message):
    chat_id = message.chat.id
    text = message.text
    
    if text == "🛑 إنهاء إضافة الملفات" and chat_id in ADMIN_IDS:
        upload_mode[chat_id] = False
        bot.send_message(chat_id, "🔒 تم إغلاق وضع الرفع بنجاح والعودة للقائمة.")
        show_menu(chat_id)
        return
    
    if text == "🛑 إنهاء التجربة والعودة للإشراف":
        testing_mode[chat_id] = False
        show_menu(chat_id)
        return
    elif text == "👤 تجربة كمستخدم":
        testing_mode[chat_id] = True
        show_menu(chat_id)
        return
        
    if text == "🔝 القائمة الرئيسية":
        user_history[chat_id] = [0]
        show_menu(chat_id)
        return
    elif text == "🔙 الرجوع للقائمة السابقة":
        if len(user_history.get(chat_id, [])) > 1:
            user_history[chat_id].pop()
        show_menu(chat_id)
        return
        
    if text == "👨‍💻 تواصل مع المطور":
        msg_dev = (
            "مرحباً بك في ركن الدعم الفني والاستقبال الخاص بالمنصة.\n\n"
            "نسعد بتلقي استفساراتكم ومقترحاتكم البنّاءة، كما نرحب بمساهماتكم العلمية التي تثري المحتوى وتفيد الجميع.\n\n"
            "👥 طاقم الإشراف والدعم الفني الحالي:\n"
            "🔹 المشرف المندوب: الواثق بالله عساج (@AlwatheqAssag)\n"
            "🔹 مشرف المنصة: جلال المهدي (@jalal_almahdy)\n"
            "🔹 مشرف المنصة: براء حسن (@br44ai)\n\n"
            "معاً.. نصنع تجربة أكاديمية أسهل وأكثر فائدة. نحن بانتظار رسائلكم!"
        )
        bot.send_message(chat_id, msg_dev)
        return

    parent_id = get_current_parent(chat_id)
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=DictCursor)
    cursor.execute('SELECT id, type, file_id FROM items WHERE name = %s AND parent_id = %s', (text, parent_id))
    item = cursor.fetchone()
    cursor.close()
    release_db_connection(conn)
    
    if item:
        if item['type'] == "مجلد":
            user_history[chat_id].append(item['id'])
            show_menu(chat_id)
        else:
            bot.send_document(chat_id, item['file_id'])

# --- نقطة استقبال الـ Webhook الفورية الخاصة بـ Flask ---
@app.route('/' + API_TOKEN, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook():
    bot.remove_webhook()
    return "Bot is running via Webhook & Supabase!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
            
        calc_sub = ["محاضرات نظري", "محاضرات تمارين", "نماذج اختبارات نظري", "نماذج تمارين", "مراجع خارجية"]
        for c in calc_sub: cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (?, "مجلد", 16)', (c,))
        
        data_sub = ["محاضرات المهندس", "ملخص محاضرات", "محاضرات العملي", "نماذج اختبارات نظري"]
        for d in data_sub: cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (?, "مجلد", 17)', (d,))
        
        prog_sub = ["محاضرات نظري", "محاضرات العملي", "نماذج اختبارات", "التمارين والمشاريع العملية"]
        for p in prog_sub: cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (?, "مجلد", 18)', (p,))
        
        math_sub = ["محاضرات نظري", "محاضرات تمارين", "نماذج اختبارات", "مراجع خارجية"]
        for m in math_sub: cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (?, "مجلد", 19)', (m,))
        
        conn.commit()

build_initial_tree()

testing_mode = {}
user_history = {}
upload_mode = {}

def get_current_parent(chat_id):
    if chat_id not in user_history or not user_history[chat_id]:
        user_history[chat_id] = [0]
    return user_history[chat_id][-1]

def show_menu(chat_id):
    parent_id = get_current_parent(chat_id)
    cursor.execute('SELECT name, type, file_id FROM items WHERE parent_id = ?', (parent_id,))
    items = cursor.fetchall()
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    files_count = 0
    for item in items:
        markup.add(KeyboardButton(item[0]))
        if item[1] == "ملف": files_count += 1
    
    if parent_id == 0:
        markup.add("👨‍💻 تواصل مع المطور")
    
    if parent_id != 0:
        markup.add("🔙 الرجوع للقائمة السابقة", "🔝 القائمة الرئيسية")
    
    if testing_mode.get(chat_id):
        markup.add("🛑 إنهاء التجربة والعودة للإشراف")
    elif chat_id in ADMIN_IDS:
        markup.add("👤 تجربة كمستخدم")
        markup.add("⚙️ إدارة هذه القائمة")
            
    if parent_id == 0:
        msg_text = (
            "مرحباً بك في المنصة الأكاديمية لقسم الذكاء الاصطناعي وعلوم البيانات (الدفعة الثانية) 🎓\n\n"
            "نضع بين يديك هذا البوت ليكون دليلك الشامل ومكتبتك المتكاملة؛ حيث يوفر لك وصولاً سهلاً وسريعاً لكافة المحاضرات، الملخصات، النماذج، والاختبارات، بالإضافة إلى التمارين والمراجعات.\n\n"
            "👇 فضلاً، اختر مستواك الدراسي من القائمة أدناه للبدء:"
        )
    else:
        msg_text = "اختر من القائمة أدناه:"
        if files_count > 0: msg_text += "\n(يوجد ملفات جاهزة للتحميل)"
        
    bot.send_message(chat_id, msg_text, reply_markup=markup)

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    cursor.execute('INSERT OR IGNORE INTO users (chat_id) VALUES (?)', (chat_id,))
    conn.commit()
    user_history[chat_id] = [0]
    testing_mode[chat_id] = False
    upload_mode[chat_id] = False
    show_menu(chat_id)

@bot.message_handler(commands=['users'])
def list_users(message):
    if message.chat.id in ADMIN_IDS:
        cursor.execute('SELECT chat_id FROM users')
        users = cursor.fetchall()
        if users:
            user_list = "\n".join([str(u[0]) for u in users])
            bot.send_message(message.chat.id, f"عدد المشتركين: {len(users)}\n\nقائمة أرقام التعريف (IDs):\n{user_list}")
        else:
            bot.send_message(message.chat.id, "لا يوجد مستخدمون حالياً.")

@bot.message_handler(func=lambda m: m.text == "⚙️ إدارة هذه القائمة" and m.chat.id in ADMIN_IDS and not testing_mode.get(m.chat.id))
def manage_current_menu(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("➕ إضافة ملف", "📁 إضافة مجلد/خيار")
    markup.add("✏️ تعديل اسم", "🗑️ حذف خيار/ملف")
    markup.add("الغاء الأمر ❌")
    bot.send_message(message.chat.id, "أنت تتحكم الآن في هذه القائمة، ماذا تريد أن تفعل؟", reply_markup=markup)

@bot.message_handler(func=lambda m: m.chat.id in ADMIN_IDS and m.text in ["➕ إضافة ملف", "📁 إضافة مجلد/خيار", "✏️ تعديل اسم", "🗑️ حذف خيار/ملف", "الغاء الأمر ❌"])
def admin_action(message):
    chat_id = message.chat.id
    if message.text == "الغاء الأمر ❌":
        upload_mode[chat_id] = False
        show_menu(chat_id)
    elif message.text == "➕ إضافة ملف":
        upload_mode[chat_id] = True
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("🛑 إنهاء إضافة الملفات")
        bot.send_message(chat_id, "📥 وضع الرفع المتعدد مُفعّل الآن!\nأرسل ملفاتك (واحد تلو الآخر أو دفعة واحدة).\nسيأخذ البوت اسم الملف الأصلي، أو التسمية المكتوبة في الـ Caption.\n\nعند الانتهاء تماماً اضغط على الزر أدناه 👇", reply_markup=markup)
    elif message.text == "📁 إضافة مجلد/خيار":
        msg = bot.send_message(chat_id, "أرسل اسم المجلد أو الخيار الجديد:")
        bot.register_next_step_handler(msg, receive_folder)
    elif message.text == "✏️ تعديل اسم":
        msg = bot.send_message(chat_id, "أرسل التعديل بالصيغة التالية تماماً:\nالاسم القديم, الاسم الجديد")
        bot.register_next_step_handler(msg, receive_rename)
    elif message.text == "🗑️ حذف خيار/ملف":
        msg = bot.send_message(chat_id, "أرسل بدقة اسم الملف أو المجلد الذي تريد حذفه بشكل نهائي من هذه القائمة:")
        bot.register_next_step_handler(msg, receive_delete)

@bot.message_handler(content_types=['document'], func=lambda m: m.chat.id in ADMIN_IDS and upload_mode.get(m.chat.id) == True)
def receive_multiple_files(message):
    parent_id = get_current_parent(message.chat.id)
    file_name = message.caption if message.caption else message.document.file_name
    file_id = message.document.file_id
    
    cursor.execute('INSERT INTO items (name, type, file_id, parent_id) VALUES (?, "ملف", ?, ?)', (file_name, file_id, parent_id))
    conn.commit()
    bot.send_message(message.chat.id, f"✅ تم حفظ '{file_name}' في الخلفية!")

def receive_folder(message):
    parent_id = get_current_parent(message.chat.id)
    cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (?, "مجلد", ?)', (message.text, parent_id))
    conn.commit()
    bot.send_message(message.chat.id, f"✅ تم إضافة '{message.text}' بنجاح!")
    show_menu(message.chat.id)

def receive_rename(message):
    try:
        old, new = message.text.split(", ")
        cursor.execute('UPDATE items SET name = ? WHERE name = ? AND parent_id = ?', (new, old, get_current_parent(message.chat.id)))
        conn.commit()
        bot.send_message(message.chat.id, "✅ تم التعديل بنجاح!")
        show_menu(message.chat.id)
    except:
        bot.send_message(message.chat.id, "❌ خطأ في الصيغة. تأكد من وضع فاصلة بين الاسمين.")
        show_menu(message.chat.id)

def receive_delete(message):
    parent_id = get_current_parent(message.chat.id)
    name_to_delete = message.text
    cursor.execute('SELECT id FROM items WHERE name = ? AND parent_id = ?', (name_to_delete, parent_id))
    if cursor.fetchone():
        cursor.execute('DELETE FROM items WHERE name = ? AND parent_id = ?', (name_to_delete, parent_id))
        conn.commit()
        bot.send_message(message.chat.id, f"✅ تم حذف '{name_to_delete}' بنجاح!")
        show_menu(message.chat.id)
    else:
        bot.send_message(message.chat.id, "❌ لم يتم العثور على هذا الاسم، تأكد من كتابة الاسم بدقة كما يظهر في الزر.")
        show_menu(message.chat.id)

@bot.message_handler(func=lambda message: True)
def handle_nav(message):
    chat_id = message.chat.id
    text = message.text
    
    if text == "🛑 إنهاء إضافة الملفات" and chat_id in ADMIN_IDS:
        upload_mode[chat_id] = False
        bot.send_message(chat_id, "🔒 تم إغلاق وضع الرفع بنجاح والعودة للقائمة.")
        show_menu(chat_id)
        return
    
    if text == "🛑 إنهاء التجربة والعودة للإشراف":
        testing_mode[chat_id] = False
        show_menu(chat_id)
        return
    elif text == "👤 تجربة كمستخدم":
        testing_mode[chat_id] = True
        show_menu(chat_id)
        return
        
    if text == "🔝 القائمة الرئيسية":
        user_history[chat_id] = [0]
        show_menu(chat_id)
        return
    elif text == "🔙 الرجوع للقائمة السابقة":
        if len(user_history.get(chat_id, [])) > 1:
            user_history[chat_id].pop()
        show_menu(chat_id)
        return
        
    if text == "👨‍💻 تواصل مع المطور":
        msg_dev = (
            "مرحباً بك في ركن الدعم الفني والاستقبال الخاص بالمنصة.\n\n"
            "نسعد بتلقي استفساراتكم ومقترحاتكم البنّاءة، كما نرحب بمساهماتكم العلمية التي تثري المحتوى وتفيد الجميع.\n\n"
            "👥 طاقم الإشراف والدعم الفني الحالي:\n"
            "🔹 المشرف المندوب: الواثق بالله عساج (@AlwatheqAssag)\n"
            "🔹 مشرف المنصة: جلال المهدي (@jalal_almahdy)\n"
            "🔹 مشرف المنصة: براء حسن (@br44ai)\n\n"
            "معاً.. نصنع تجربة أكاديمية أسهل وأكثر فائدة. نحن بانتظار رسائلكم!"
        )
        bot.send_message(chat_id, msg_dev)
        return

    parent_id = get_current_parent(chat_id)
    cursor.execute('SELECT id, type, file_id FROM items WHERE name = ? AND parent_id = ?', (text, parent_id))
    item = cursor.fetchone()
    
    if item:
        item_id, item_type, file_id = item
        if item_type == "مجلد":
            user_history[chat_id].append(item_id)
            show_menu(chat_id)
        else:
            bot.send_document(chat_id, file_id)

# --- نقطة استقبال الـ Webhook الفورية الخاصة بـ Flask ---
@app.route('/' + API_TOKEN, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook():
    bot.remove_webhook()
    # يتم استبدال الرابط أدناه برابط السيرفر المستضيف فور الحصول عليه ليتم ربطه بتيليجرام تلقائياً
    # bot.set_webhook(url='https://your-server-url.vercel.app/' + API_TOKEN)
    return "Bot is running via Webhook!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
