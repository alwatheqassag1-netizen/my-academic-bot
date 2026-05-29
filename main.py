import telebot
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import DictCursor
from flask import Flask, request
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
import sys

if sys.version_info >= (3, 0):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_TOKEN = '7524289470:AAGkeX96s1s6saxGP3uy14MN9it19nKn10A'
ADMIN_IDS = [6842543527, 5585934059, 1084564343] 
DATABASE_URL = "postgresql://postgres:alwatheq733@db.jknojabyblhpoudaowzr.supabase.co:5432/postgres"

bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)

try:
    db_pool = ThreadedConnectionPool(1, 10, DATABASE_URL)
except Exception as e:
    print(f"Pool error: {e}")
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
            
            for parent_level_id in [1, 2, 3, 4]:
                cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (\'📅 ترم أول\', \'مجلد\', %s)', (parent_level_id,))
                cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (\'📅 ترم ثاني\', \'مجلد\', %s)', (parent_level_id,))
            conn.commit()
            
            subjects = ["📖 الثقافة الإسلامية", "🌙 لغة عربية 2", "🇬🇧 لغة إنجليزية 2", "📈 تفاضل وتكامل 2", "📊 مقدمة في علوم البيانات", "💻 برمجة حاسوب", "🗂️ رياضيات متقطعة"]
            for s in subjects: 
                cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (%s, \'مجلد\', 6)', (s,))
            conn.commit()
            
            for i in [13, 14, 15]:
                cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (\'📂 محاضرات وملخصات\', \'مجلد\', %s)', (i,))
                cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (\'📝 نماذج اختبارات\', \'مجلد\', %s)', (i,))
                
            calc_sub = ["📂 محاضرات نظري", "📐 محاضرات تمارين", "📝 نماذج اختبارات نظري", "✍️ نماذج تمارين", "📚 مراجع خارجية"]
            for c in calc_sub: 
                cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (%s, \'مجلد\', 16)', (c,))
            
            data_sub = ["👨‍🏫 محاضرات المهندس", "📜 ملخص محاضرات", "⚙️ محاضرات العملي", "📝 نماذج اختبارات نظري"]
            for d in data_sub: 
                cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (%s, \'مجلد\', 17)', (d,))
            
            prog_sub = ["📂 محاضرات نظري", "🖥️ محاضرات العملي", "📝 نماذج اختبارات", "🚀 التمارين والمشاريع العملية"]
            for p in prog_sub: 
                cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (%s, \'مجلد\', 18)', (p,))
            
            math_sub = ["📂 محاضرات نظري", "✏️ محاضرات تمارين", "📝 نماذج اختبارات", "📚 مراجع خارجية"]
            for m in math_sub: 
                cursor.execute('INSERT INTO items (name, type, parent_id) VALUES (%s, \'مجلد\', 19)', (m,))
            
            conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Init error: {e}")

init_db()

testing_mode, user_history, upload_mode = {}, {}, {}

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
        markup.add("👤 تجربة كمستخدم", "⚙️ إدارة هذه القائمة")
            
    msg_text = "مرحباً بك في المنصة الأكاديمية لقسم الذكاء الاصطناعي وعلوم البيانات (الدفعة الثانية) 🎓\n\n👇 اختر من القائمة:" if parent_id == 0 else "اختر من القائمة أدناه:"
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
    testing_mode[chat_id] = upload_mode[chat_id] = False
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
            bot.send_message(message.chat.id, f"👥 المشتركين: {len(users)}")

@bot.message_handler(func=lambda m: m.text == "⚙️ إدارة هذه القائمة" and m.chat.id in ADMIN_IDS and not testing_mode.get(m.chat.id))
def manage_current_menu(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("➕ إضافة ملف", "📁 إدارة خيار جديد", "✏️ تعديل اسم", "🗑️ حذف خيار/ملف", "الغاء الأمر ❌")
    bot.send_message(message.chat.id, "🛠️ خيارات التحكم الإداري:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.chat.id in ADMIN_IDS and m.text in ["➕ إضافة ملف", "📁 إدارة خيار جديد", "✏️ تعديل اسم", "🗑️ حذف خيار/ملف", "الغاء الأمر ❌"])
def admin_action(message):
    chat_id = message.chat.id
    if message.text == "الغاء الأمر ❌":
        upload_mode[chat_id] = False
        show_menu(chat_id)
    elif message.text == "➕ إضافة ملف":
        upload_mode[chat_id] = True
        markup = ReplyKeyboardMarkup(resize_keyboard=True).add("🛑 إنهاء إضافة الملفات")
        bot.send_message(chat_id, "📥 وضع الرفع المتعدد فعال! أرسل ملفاتك دفعة واحدة:", reply_markup=markup)
    elif message.text == "📁 إدارة خيار جديد":
        bot.register_next_step_handler(bot.send_message(chat_id, "📥 أرسل اسم المجلد الجديد:"), receive_folder)
    elif message.text == "✏️ تعديل اسم":
        bot.register_next_step_handler(bot.send_message(chat_id, "✏️ أرسل بالصيغة: الاسم القديم, الاسم الجديد"), receive_rename)
    elif message.text == "🗑️ حذف خيار/ملف":
        bot.register_next_step_handler(bot.send_message(chat_id, "🗑️ أرسل اسم الملف أو المجلد لحذفه:"), receive_delete)

@bot.message_handler(content_types=['document'], func=lambda m: m.chat.id in ADMIN_IDS and upload_mode.get(m.chat.id))
def receive_multiple_files(message):
    parent_id = get_current_parent(message.chat.id)
    file_name = message.caption if message.caption else message.document.file_name
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO items (name, type, file_id, parent_id) VALUES (%s, \'ملف\', %s, %s)', (file_name, message.document.file_id, parent_id))
        conn.commit()
        cursor.close()
        bot.send_message(message.chat.id, f"✅ تم حفظ '{file_name}'!")
    except:
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
    bot.send_message(message.chat.id, "✅ تم الإضافة!")
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
        bot.send_message(message.chat.id, "✅ تم التعديل!")
    except:
        bot.send_message(message.chat.id, "❌ خطأ صيغة.")
    show_menu(message.chat.id)

def receive_delete(message):
    parent_id = get_current_parent(message.chat.id)
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM items WHERE name = %s AND parent_id = %s', (message.text, parent_id))
        conn.commit()
        cursor.close()
    finally:
        release_db_connection(conn)
    bot.send_message(message.chat.id, "✅ تم الحذف!")
    show_menu(message.chat.id)

@bot.message_handler(func=lambda message: True)
def handle_nav(message):
    chat_id, text = message.chat.id, message.text
    if text == "🛑 إنهاء إضافة الملفات" and chat_id in ADMIN_IDS:
        upload_mode[chat_id] = False
        show_menu(chat_id)
        return
    if text == "🛑 إنهاء التجربة والعودة للإشراف":
        testing_mode[chat_id] = False
        show_menu(chat_id)
        return
    if text == "👤 تجربة كمستخدم":
        testing_mode[chat_id] = True
        show_menu(chat_id)
        return
    if text == "🔝 القائمة الرئيسية":
        user_history[chat_id] = [0]
        show_menu(chat_id)
        return
    if text == "🔙 الرجوع للقائمة السابقة":
        if len(user_history.get(chat_id, [])) > 1: user_history[chat_id].pop()
        show_menu(chat_id)
        return
    if text == "👨‍💻 تواصل مع المطور":
        bot.send_message(chat_id, "👥 طاقم الإشراف والدعم الفني الحالي:\n🔹 المندوب: الواثق بالله عساج (@AlwatheqAssag)\n🔹 جلال المهدي (@jalal_almahdy)\n🔹 براء حسن (@br44ai)")
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

@app.route('/' + API_TOKEN, methods=['POST'])
def getMessage():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "!", 200

@app.route("/")
def webhook():
    bot.remove_webhook()
    return "Bot is running perfectly via Webhook & Supabase!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
    
