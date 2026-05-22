import os, uuid, sqlite3, requests, re, hashlib, json
from datetime import datetime
from flask import Flask, request, render_template_string, redirect, session, url_for
from werkzeug.utils import secure_filename

# ── Config ───────────────────────────────────────────────────
VILLAGE_NAME  = os.environ.get("VILLAGE_NAME",  "Kolukonda Village")
SARPANCH_NAME = os.environ.get("SARPANCH_NAME", "Kothi Sravanthi Praveen")
MANDAL        = os.environ.get("MANDAL",        "Jangaon Mandal")
DISTRICT      = os.environ.get("DISTRICT",      "Nalgonda District, Telangana")
DATABASE_URL  = os.environ.get("DATABASE_URL",  "")

# WhatsApp Business API Configuration
META_TOKEN     = os.environ.get("META_TOKEN", "")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID", "1173815852473279")
VERIFY_TOKEN   = os.environ.get("VERIFY_TOKEN", "kolukonda2024")

# File upload config
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('static/voices', exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "sarpanch_secret_2024")
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

whatsapp_sessions = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ── FORCE ADD VILLAGE COLUMN ON STARTUP ──────────────────────
def force_add_village_column():
    print("🔧 Checking village column...")
    try:
        if DATABASE_URL:
            import psycopg2
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            cur.execute("ALTER TABLE complaints ADD COLUMN IF NOT EXISTS village TEXT DEFAULT ''")
            conn.commit()
            conn.close()
            print("✅ Village column verified")
        else:
            conn = sqlite3.connect("sarpanch.db")
            cur = conn.cursor()
            try:
                cur.execute("ALTER TABLE complaints ADD COLUMN village TEXT DEFAULT ''")
                print("✅ Village column added")
            except:
                print("✅ Village column already exists")
            conn.commit()
            conn.close()
    except Exception as e:
        print(f"⚠️ Village column: {e}")

force_add_village_column()

# ── Helper Functions ─────────────────────────────────────────
def now_str():
    return datetime.now().strftime("%d-%b-%Y %H:%M")

def fmt_time():
    return datetime.now().strftime("%H:%M")

def new_id(prefix=""):
    return f"{prefix}{str(uuid.uuid4())[:6].upper()}"

def get_placeholder(db_type):
    return "%s" if db_type == "pg" else "?"

def get_db():
    if DATABASE_URL:
        try:
            import psycopg2, psycopg2.extras
            conn = psycopg2.connect(DATABASE_URL)
            conn.cursor_factory = psycopg2.extras.RealDictCursor
            return conn, "pg"
        except Exception as e:
            print(f"PG error: {e}")
    conn = sqlite3.connect("sarpanch.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn, "sqlite"

def init_db():
    conn, db_type = get_db()
    cur = conn.cursor()
    p = get_placeholder(db_type)
    u = "updated" if db_type == "pg" else "updated_at"
    ai = "SERIAL" if db_type == "pg" else "INTEGER"
    autoincrement = "" if db_type == "pg" else "AUTOINCREMENT"
   
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS complaints (
            id TEXT PRIMARY KEY, name TEXT, phone TEXT, category TEXT,
            description TEXT, location TEXT, priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'pending', filed_at TEXT, {u} TEXT, notes TEXT DEFAULT '',
            location_lat REAL, location_lng REAL, location_address TEXT,
            maps_link TEXT, media_type TEXT, media_url TEXT, village TEXT DEFAULT ''
        )
    """)
   
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS certificates (
            id TEXT PRIMARY KEY, type TEXT, name TEXT, father TEXT, phone TEXT,
            purpose TEXT, status TEXT DEFAULT 'pending', filed_at TEXT, {u} TEXT, notes TEXT DEFAULT ''
        )
    """)
   
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS works (
            id TEXT PRIMARY KEY, title TEXT, status TEXT DEFAULT 'pending', {u} TEXT
        )
    """)
   
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS announcements (
            id {ai} PRIMARY KEY {autoincrement}, title TEXT, body TEXT, date TEXT
        )
    """)
   
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS sarpanch_users (
            id {ai} PRIMARY KEY {autoincrement}, username TEXT UNIQUE, password TEXT,
            village_name TEXT, phone TEXT, email TEXT, photo TEXT, created_at TEXT
        )
    """)
   
    default_password = hashlib.sha256("sarpanch123".encode()).hexdigest()
    cur.execute(f"SELECT * FROM sarpanch_users WHERE username = 'kolukonda_sarpanch'")
    if not cur.fetchone():
        cur.execute(f"""
            INSERT INTO sarpanch_users (username, password, village_name, phone, email, created_at)
            VALUES ({p},{p},{p},{p},{p},{p})
        """, ('kolukonda_sarpanch', default_password, 'Kolukonda', '9999999999', 'sarpanch@kolukonda.in', now_str()))
   
    conn.commit()
    conn.close()
    print(f"✅ Database ready ({db_type})")

def insert_complaint(c):
    conn, db_type = get_db()
    cur = conn.cursor()
    p = get_placeholder(db_type)
    u = "updated" if db_type == "pg" else "updated_at"
    cur.execute(f"""
        INSERT INTO complaints (id,name,phone,category,description,location,priority,status,filed_at,{u},notes,
        location_lat,location_lng,location_address,maps_link,media_type,media_url,village)
        VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p})
    """,
        (c["id"],c["name"],c["phone"],c["category"],c["desc"],c.get("location",""),c["priority"],"pending",c["filed_at"],c["filed_at"],"",
         c.get("location_lat"),c.get("location_lng"),c.get("location_address",""),c.get("maps_link",""),
         c.get("media_type",""),c.get("media_url",""), c.get("village","")))
    conn.commit()
    conn.close()

def insert_certificate(c):
    conn, db_type = get_db()
    cur = conn.cursor()
    p = get_placeholder(db_type)
    u = "updated" if db_type == "pg" else "updated_at"
    cur.execute(f"""
        INSERT INTO certificates (id,type,name,father,phone,purpose,status,filed_at,{u},notes)
        VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p})
    """,
        (c["id"],c["type"],c["name"],c["father"],c["phone"],c["purpose"],"pending",c["filed_at"],c["filed_at"],""))
    conn.commit()
    conn.close()

def get_record(ref_id):
    conn, db_type = get_db()
    cur = conn.cursor()
    p = get_placeholder(db_type)
    tbl = "complaints" if ref_id.startswith("CMP") else "certificates"
    cur.execute(f"SELECT * FROM {tbl} WHERE id = {p}", (ref_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def update_status(table, ref_id, status):
    conn, db_type = get_db()
    cur = conn.cursor()
    p = get_placeholder(db_type)
    u = "updated" if db_type == "pg" else "updated_at"
    cur.execute(f"UPDATE {table} SET status = {p}, {u} = {p} WHERE id = {p}", (status, now_str(), ref_id))
    conn.commit()
    conn.close()

def all_complaints():
    conn, db_type = get_db()
    cur = conn.cursor()
    u = "updated" if db_type == "pg" else "updated_at"
    cur.execute(f"SELECT *,{u} as updated FROM complaints ORDER BY filed_at DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def all_certs():
    conn, db_type = get_db()
    cur = conn.cursor()
    u = "updated" if db_type == "pg" else "updated_at"
    cur.execute(f"SELECT *,{u} as updated FROM certificates ORDER BY filed_at DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def all_works():
    conn, db_type = get_db()
    cur = conn.cursor()
    u = "updated" if db_type == "pg" else "updated_at"
    cur.execute(f"SELECT *,{u} as updated FROM works ORDER BY {u} DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def active_works():
    conn, db_type = get_db()
    cur = conn.cursor()
    p = get_placeholder(db_type)
    cur.execute(f"SELECT * FROM works WHERE status IN ({p},{p})", ("pending","in_progress"))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def all_announcements():
    conn, _ = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM announcements ORDER BY id DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def insert_work(title):
    conn, db_type = get_db()
    cur = conn.cursor()
    p = get_placeholder(db_type)
    u = "updated" if db_type == "pg" else "updated_at"
    cur.execute(f"INSERT INTO works (id,title,status,{u}) VALUES ({p},{p},{p},{p})",
                (new_id("WORK-"), title, "pending", now_str()))
    conn.commit()
    conn.close()

def insert_announcement(title, body):
    conn, db_type = get_db()
    cur = conn.cursor()
    p = get_placeholder(db_type)
    cur.execute(f"INSERT INTO announcements (title,body,date) VALUES ({p},{p},{p})", (title, body, now_str()))
    conn.commit()
    conn.close()

def get_sarpanch_by_username(username):
    conn, db_type = get_db()
    cur = conn.cursor()
    p = get_placeholder(db_type)
    cur.execute(f"SELECT * FROM sarpanch_users WHERE username = {p}", (username,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_sarpanchs():
    conn, db_type = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, village_name, phone, email, photo, created_at FROM sarpanch_users ORDER BY village_name")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def update_sarpanch_photo(username, photo_path):
    conn, db_type = get_db()
    cur = conn.cursor()
    p = get_placeholder(db_type)
    cur.execute(f"UPDATE sarpanch_users SET photo = {p} WHERE username = {p}", (photo_path, username))
    conn.commit()
    conn.close()

# ── VOICE PERMANENT STORAGE FUNCTION ─────────────────────────
def download_voice_permanently(voice_id, complaint_id):
    if not META_TOKEN:
        print("❌ No META_TOKEN for voice download")
        return None
   
    voice_dir = os.path.join('static', 'voices')
    os.makedirs(voice_dir, exist_ok=True)
   
    headers = {"Authorization": f"Bearer {META_TOKEN}"}
   
    try:
        media_resp = requests.get(f"https://graph.facebook.com/v19.0/{voice_id}", headers=headers, timeout=10)
        if media_resp.status_code != 200:
            print(f"❌ Failed to get media info: {media_resp.status_code}")
            return None
       
        download_url = media_resp.json().get("url")
        if not download_url:
            print("❌ No download URL in response")
            return None
       
        audio_resp = requests.get(download_url, headers=headers, timeout=30)
        if audio_resp.status_code != 200:
            print(f"❌ Failed to download audio: {audio_resp.status_code}")
            return None
       
        filename = f"voice_{complaint_id}_{int(datetime.now().timestamp())}.ogg"
        filepath = os.path.join(voice_dir, filename)
       
        with open(filepath, 'wb') as f:
            f.write(audio_resp.content)
       
        print(f"✅ Voice saved permanently: {filename}")
        return f"/static/voices/{filename}"
       
    except Exception as e:
        print(f"❌ Voice download error: {e}")
        return None

# ── Helper Functions ─────────────────────────────────────────
def detect_village_from_coords(lat, lng):
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lng}&format=json"
        response = requests.get(url, headers={"User-Agent": "SarpanchBot/1.0"}, timeout=5)
        if response.status_code == 200:
            data = response.json()
            address = data.get("address", {})
            village = address.get("village") or address.get("town") or address.get("city") or address.get("hamlet")
            return village
    except Exception as e:
        print(f"Geocoding error: {e}")
    return None

def detect_village_from_text(text):
    villages = ['kolukonda', 'keesara', 'ghatkesar', 'pocharam', 'jangaon', 'hyderabad']
    text_lower = text.lower()
    for village in villages:
        if village in text_lower:
            return village.title()
    return None

# ── WhatsApp API Function ────────────────────────────────────
def send_whatsapp_message(to_number, message):
    if not META_TOKEN:
        print(" META_TOKEN not set")
        return False
   
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": message}
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            print(f"📨 Message sent to {to_number}")
            return True
        else:
            print(f"❌ Failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

# ── Menus and Constants ──────────────────────────────────────
MENU_EN = ("Namaskaram! Welcome to *{v}* Gram Panchayat\nSarpanch: *{s}*\n\n"
    "1️⃣ Register Complaint\n2️⃣ Request Certificate\n3️⃣ Track Status\n"
    "4️⃣ Government Schemes\n5️⃣ Development Works\n6️⃣ Announcements\n7️⃣ Office Info\n\n"
    "📍 You can share your location or 🎤 send voice message\n"
    "తెలుగు కావాలంటే *telugu* టైప్ చేయండి.").format(v=VILLAGE_NAME,s=SARPANCH_NAME)

MENU_TE = ("నమస్కారం! *{v}* గ్రామ పంచాయతీకి స్వాగతం\nసర్పంచ్: *{s}*\n\n"
    "1️⃣ ఫిర్యాదు నమోదు చేయండి\n2️⃣ సర్టిఫికెట్ అభ్యర్థించండి\n3️⃣ ఫిర్యాదు స్థితి తెలుసుకోండి\n"
    "4️⃣ ప్రభుత్వ పథకాలు\n5️⃣ అభివృద్ధి పనులు\n6️⃣ ప్రకటనలు\n7️⃣ కార్యాలయ సమాచారం\n\n"
    "📍 మీ లొకేషన్ షేర్ చేయండి లేదా 🎤 వాయిస్ మెసేజ్ పంపండి\n"
    "For English type *english*").format(v=VILLAGE_NAME,s=SARPANCH_NAME)

COMPLAINT_CATS = {"1":"Road / Pothole","2":"Water Supply","3":"Electricity","4":"Drainage","5":"Ration Shop","6":"Land Dispute","7":"Other"}
CERT_TYPES = {"1":"Income Certificate","2":"Caste Certificate","3":"Residence Certificate","4":"Birth Certificate","5":"Death Certificate","6":"Agriculture Land Certificate"}
SCHEMES = [("Rythu Bandhu","₹5000/acre/season for farmers"),("PM Awas Yojana","Free house for BPL families"),
    ("Aarogyasri","Free medical up to ₹5L/year"),("Kalyana Lakshmi","₹1 lakh for girl marriage"),
    ("PM Kisan","₹6000/year for farmers"),("NREGA","100 days employment"),("Bhadratha","Free LPG for BPL")]
STATUS_MAP = {"pending":"Pending","in_review":"In Review","in_progress":"In Progress","resolved":"Resolved","rejected":"Rejected","ready":"Ready to Collect","processing":"Processing"}
PRI_MAP = {"low":"Low","medium":"Medium","high":"High"}

def get_menu(ctx):
    return MENU_TE if ctx.get("lang")=="te" else MENU_EN

# ── BOT REPLY FUNCTION (FIXED - ONLY RESPONDS TO HI/HELLO) ───
def bot_reply(user_msg, ctx, media_info=None):
    msg = user_msg.strip() if user_msg else ""
    ml = msg.lower()
    state = ctx.get("state", "idle")
    lang = ctx.get("lang", "en")
   
    print(f"🔍 DEBUG: state={state}, msg={msg[:30] if msg else 'empty'}, lang={lang}")
   
    # Language switching (always allowed)
    if ml == "telugu":
        return MENU_TE, {"state": "idle", "lang": "te"}
    if ml == "english":
        return MENU_EN, {"state": "idle", "lang": "en"}
   
    # Handle voice message
    if media_info and media_info.get("type") == "voice":
        ctx["media_type"] = "voice"
        ctx["media_url"] = media_info.get("url", "")
        ctx["temp_audio_id"] = media_info.get("audio_id", "")
        ctx["state"] = "waiting_for_location"
        if lang == "te":
            return "🎤 వాయిస్ మెసేజ్ అందుకుంది!\n\n📍 దయచేసి మీ లొకేషన్ షేర్ చేయండి (📎 → Location):", ctx
        return "🎤 Voice received! Please share your location (📎 → Location):", ctx
   
    # ──────────────────────────────────────────────────────────
    # IDLE STATE - ONLY RESPOND TO TRIGGER WORDS
    # ──────────────────────────────────────────────────────────
    if state == "idle":
        # Define trigger words that show the menu
        trigger_words = {'hi', 'hello', 'start', 'menu', 'help'}
        
        if ml in trigger_words:
            return get_menu({"lang": lang}), {"state": "idle", "lang": lang}
        else:
            # Ignore all other random messages
            print(f"🚫 Ignoring non-trigger message in idle: {msg}")
            return None, ctx
   
    # ──────────────────────────────────────────────────────────
    # ONCE USER HAS STARTED A FLOW (state is not idle), 
    # HANDLE ALL INPUTS NORMALLY
    # ──────────────────────────────────────────────────────────
   
    # Handle menu options 1-7 when user is in active state (after menu shown)
    if ml in ("1", "2", "3", "4", "5", "6", "7"):
        if ml == "1":
            ctx["state"] = "c_name"
            if lang == "te":
                return "📝 ఫిర్యాదు నమోదు\n\nమీ పూర్తి పేరు టైప్ చేయండి:", ctx
            return "📝 Enter your full name:", {"state": "c_name", "lang": lang}
        elif ml == "2":
            cats = "\n".join(f"{k}. {v}" for k, v in CERT_TYPES.items())
            ctx["state"] = "cert_type"
            if lang == "te":
                return f"📋 సర్టిఫికెట్ రకం:\n{cats}", ctx
            return f"📋 Certificate Type:\n{cats}", ctx
        elif ml == "3":
            ctx["state"] = "track_id"
            if lang == "te":
                return "🔍 మీ రిఫరెన్స్ ID టైప్ చేయండి:", ctx
            return "🔍 Enter your Reference ID:", ctx
        elif ml == "4":
            lines = [f"{n}: {d}" for n, d in SCHEMES]
            if lang == "te":
                return "📋 ప్రభుత్వ పథకాలు\n\n" + "\n".join(lines) + "\n\nమెనూ కోసం *menu* టైప్ చేయండి", {"state": "idle", "lang": lang}
            return "📋 Government Schemes\n\n" + "\n".join(lines) + "\n\nType *menu* for main menu", {"state": "idle", "lang": lang}
        elif ml == "5":
            rows = active_works()
            if not rows:
                if lang == "te":
                    return "🛠️ ప్రస్తుతం పనులు లేవు.\n\nమెనూ కోసం *menu* టైప్ చేయండి", {"state": "idle", "lang": lang}
                return "🛠️ No active works.\n\nType *menu* for main menu", {"state": "idle", "lang": lang}
            lines = [f"• {w['title']}" for w in rows[:5]]
            if lang == "te":
                return "🛠️ అభివృద్ధి పనులు:\n" + "\n".join(lines) + "\n\nమెనూ కోసం *menu* టైప్ చేయండి", {"state": "idle", "lang": lang}
            return "🛠️ Development Works:\n" + "\n".join(lines) + "\n\nType *menu* for main menu", {"state": "idle", "lang": lang}
        elif ml == "6":
            rows = all_announcements()[:3]
            if not rows:
                if lang == "te":
                    return "📢 ప్రకటనలు లేవు.\n\nమెనూ కోసం *menu* టైప్ చేయండి", {"state": "idle", "lang": lang}
                return "📢 No announcements.\n\nType *menu* for main menu", {"state": "idle", "lang": lang}
            if lang == "te":
                return "📢 ప్రకటనలు:\n" + "\n".join([f"• {a['title']}: {a['body']}" for a in rows]) + "\n\nమెనూ కోసం *menu* టైప్ చేయండి", {"state": "idle", "lang": lang}
            return "📢 Announcements:\n" + "\n".join([f"• {a['title']}: {a['body']}" for a in rows]) + "\n\nType *menu* for main menu", {"state": "idle", "lang": lang}
        elif ml == "7":
            if lang == "te":
                return f"🏛️ {VILLAGE_NAME} పంచాయతీ\nసర్పంచ్: {SARPANCH_NAME}\nమండలం: {MANDAL}\nకార్యాలయ సమయాలు: సోమ-శని 10AM-5PM", {"state": "idle", "lang": lang}
            return f"🏛️ {VILLAGE_NAME} Panchayat\nSarpanch: {SARPANCH_NAME}\nMandal: {MANDAL}\nOffice Hours: Mon-Sat 10AM-5PM", {"state": "idle", "lang": lang}
   
    # COMPLAINT FLOW
    if state == "c_name":
        if len(msg) < 2:
            if lang == "te":
                return "దయచేసి సరైన పేరు టైప్ చేయండి (కనీసం 2 అక్షరాలు):", ctx
            return "Please enter valid name (min 2 chars):", ctx
        ctx["c_name"] = msg.title()
        ctx["state"] = "c_phone"
        if lang == "te":
            return f"నమస్కారం {ctx['c_name']}!\n\nమొబైల్ నంబర్ (10 అంకెలు):", ctx
        return f"Hello {ctx['c_name']}!\n\nMobile number (10 digits):", ctx
   
    if state == "c_phone":
        if not (msg.isdigit() and len(msg) >= 10):
            if lang == "te":
                return "దయచేసి సరైన 10-అంకెల మొబైల్ నంబర్ టైప్ చేయండి:", ctx
            return "Please enter 10-digit number:", ctx
        ctx["c_phone"] = msg
        ctx["state"] = "c_cat"
        cats = "\n".join(f"{k}. {v}" for k, v in COMPLAINT_CATS.items())
        if lang == "te":
            return f"📂 వర్గం ఎంచుకోండి:\n{cats}", ctx
        return f"📂 Select complaint category:\n{cats}", ctx
   
    if state == "c_cat":
        if msg not in COMPLAINT_CATS:
            if lang == "te":
                return "దయచేసి 1-7 మధ్య సంఖ్య ఎంచుకోండి:", ctx
            return "Please choose 1-7:", ctx
        ctx["c_cat"] = COMPLAINT_CATS[msg]
        ctx["state"] = "c_desc"
        if lang == "te":
            return f"📝 వర్గం: {ctx['c_cat']}\n\nసమస్య వివరించండి:", ctx
        return f"📝 Category: {ctx['c_cat']}\n\nDescribe the problem:", ctx
   
    if state == "c_desc":
        if len(msg) < 5:
            if lang == "te":
                return "దయచేసి మరింత వివరంగా టైప్ చేయండి (కనీసం 5 అక్షరాలు):", ctx
            return "More details please (min 5 chars):", ctx
        ctx["c_desc"] = msg
        ctx["state"] = "waiting_for_location"
        if lang == "te":
            return "📍 దయచేసి మీ లొకేషన్ షేర్ చేయండి (📎 → Location) లేదా ఊరి పేరు టైప్ చేయండి:", ctx
        return "📍 Share your location (📎 → Location) or type village name:", ctx
   
    if state == "waiting_for_location":
        detected_village = detect_village_from_text(msg)
        if detected_village:
            ctx["village"] = detected_village
            print(f"✅ Village detected from text: {detected_village}")
        elif not ctx.get("location_lat"):
            ctx["location_text"] = msg
            print(f"📍 Location text saved: {msg}")
        else:
            print(f"📍 Village from GPS: {ctx.get('village')}")
       
        ctx["state"] = "c_pri"
        if lang == "te":
            return "⚡ ఎంత అత్యవసరం?\n1️⃣ తక్కువ\n2️⃣ మధ్యస్థం\n3️⃣ ఎక్కువ", ctx
        return "⚡ How urgent?\n1️⃣ Low\n2️⃣ Medium\n3️⃣ High", ctx
   
    if state == "c_pri":
        print(f"🔍 c_pri received: msg={msg}")
        print(f"🔍 Current ctx: village={ctx.get('village')}, location_text={ctx.get('location_text')}")
       
        pmap = {"1": "low", "2": "medium", "3": "high"}
        if msg not in pmap:
            if lang == "te":
                return "⚡ దయచేసి 1, 2, లేదా 3 టైప్ చేయండి:", ctx
            return "⚡ Please reply with 1, 2, or 3:", ctx
       
        ref = new_id("CMP-")
        maps_link = ctx.get("maps_link", "")
       
        village = ctx.get("village")
        if not village or village == "Unknown":
            village = ctx.get("location_text", "")
        if not village or village == "":
            village = VILLAGE_NAME
       
        print(f"✅ Final village for complaint: {village}")
       
        lat = ctx.get("location_lat")
        lng = ctx.get("location_lng")
       
        media_url = ctx.get("media_url", "")
        if ctx.get("temp_audio_id"):
            permanent_url = download_voice_permanently(ctx["temp_audio_id"], ref)
            if permanent_url:
                media_url = permanent_url
                print(f"✅ Voice saved to: {permanent_url}")
       
        rec = {
            "id": ref,
            "name": ctx.get("c_name", "Unknown"),
            "phone": ctx.get("c_phone", "Unknown"),
            "category": ctx.get("c_cat", "Unknown"),
            "desc": ctx.get("c_desc", "Unknown"),
            "location": village,
            "priority": pmap[msg],
            "filed_at": now_str(),
            "location_lat": lat,
            "location_lng": lng,
            "location_address": ctx.get("location_address", ""),
            "maps_link": maps_link,
            "media_type": "voice" if ctx.get("temp_audio_id") else "",
            "media_url": media_url,
            "village": village
        }
       
        print(f"🔍 Saving complaint: {rec}")
        insert_complaint(rec)
       
        if lang == "te":
            reply = f"✅ *ఫిర్యాదు నమోదు చేయబడింది!*\n\n📋 టిక్కెట్ ID: {ref}\n👤 పేరు: {rec['name']}\n📂 వర్గం: {rec['category']}\n📍 లొకేషన్: {rec['location']}\n⚡ ప్రాధాన్యత: {PRI_MAP[rec['priority']]}\n📅 తేదీ: {rec['filed_at']}"
        else:
            reply = f"✅ *Complaint Registered!*\n\n📋 Ticket ID: {ref}\n👤 Name: {rec['name']}\n📂 Category: {rec['category']}\n📍 Location: {rec['location']}\n⚡ Priority: {PRI_MAP[rec['priority']]}\n📅 Date: {rec['filed_at']}"
       
        if maps_link:
            reply += f"\n🗺️ Map: {maps_link}"
       
        reply += "\n\nType *menu* for main menu"
        return reply, {"state": "idle", "lang": ctx.get("lang", "en")}
   
    # CERTIFICATE FLOW
    if state == "cert_type":
        if msg not in CERT_TYPES:
            if lang == "te":
                return "దయచేసి 1-6 మధ్య సంఖ్య ఎంచుకోండి:", ctx
            return "Choose 1-6:", ctx
        ctx["cert_type"] = CERT_TYPES[msg]
        ctx["state"] = "cert_name"
        if lang == "te":
            return "📄 అప్లికెంట్ పూర్తి పేరు:", ctx
        return "📄 Applicant full name:", ctx
   
    if state == "cert_name":
        if len(msg) < 2:
            if lang == "te":
                return "దయచేసి సరైన పేరు టైప్ చేయండి:", ctx
            return "Please enter valid name:", ctx
        ctx["cert_name"] = msg.title()
        ctx["state"] = "cert_father"
        if lang == "te":
            return "👨 తండ్రి/భర్త పేరు:", ctx
        return "👨 Father's/Husband's name:", ctx
   
    if state == "cert_father":
        if len(msg) < 2:
            if lang == "te":
                return "దయచేసి సరైన పేరు టైప్ చేయండి:", ctx
            return "Please enter valid name:", ctx
        ctx["cert_father"] = msg.title()
        ctx["state"] = "cert_phone"
        if lang == "te":
            return "📱 మొబైల్ నంబర్ (10 అంకెలు):", ctx
        return "📱 Mobile number (10 digits):", ctx
   
    if state == "cert_phone":
        if not (msg.isdigit() and len(msg) >= 10):
            if lang == "te":
                return "దయచేసి సరైన 10-అంకెల మొబైల్ నంబర్ టైప్ చేయండి:", ctx
            return "Enter 10-digit number:", ctx
        ctx["cert_phone"] = msg
        ctx["state"] = "cert_purpose"
        if lang == "te":
            return "📝 ప్రయోజనం (ఉదా: బ్యాంక్ లోన్, కళాశాల ప్రవేశం):", ctx
        return "📝 Purpose (e.g., Bank loan, College admission):", ctx
   
    if state == "cert_purpose":
        if len(msg) < 3:
            if lang == "te":
                return "దయచేసి ప్రయోజనం టైప్ చేయండి:", ctx
            return "Please provide purpose:", ctx
        ref = new_id("CERT-")
        rec = {
            "id": ref, "type": ctx["cert_type"], "name": ctx["cert_name"],
            "father": ctx["cert_father"], "phone": ctx["cert_phone"],
            "purpose": msg, "filed_at": now_str()
        }
        insert_certificate(rec)
        if lang == "te":
            return f"✅ *సర్టిఫికెట్ అభ్యర్థన నమోదు చేయబడింది!*\n\n📋 ID: {ref}\n👤 పేరు: {rec['name']}\n📄 రకం: {rec['type']}\n\nప్రాసెస్ చేయడానికి 5-7 రోజులు పడుతుంది.\n\nమెనూ కోసం *menu* టైప్ చేయండి", {"state": "idle", "lang": lang}
        return f"✅ *Certificate Request Submitted!*\n\n📋 ID: {ref}\n👤 Name: {rec['name']}\n📄 Type: {rec['type']}\n\nProcessing takes 5-7 days.\n\nType *menu* for main menu", {"state": "idle", "lang": lang}
   
    # TRACK STATUS FLOW
    if state == "track_id":
        if len(msg) < 5:
            if lang == "te":
                return "దయచేసి సరైన రిఫరెన్స్ ID టైప్ చేయండి (ఉదా: CMP-XXXXX):", ctx
            return "Please enter valid Reference ID (e.g., CMP-XXXXX):", ctx
        ref = msg.upper().strip()
        rec = get_record(ref)
        if not rec:
            if lang == "te":
                return f"❌ ID {ref} కనుగొనబడలేదు.\n\nదయచేసి సరైన ID టైప్ చేయండి.\n\nమెనూ కోసం *menu* టైప్ చేయండి", {"state": "idle", "lang": lang}
            return f"❌ ID {ref} not found.\n\nPlease check and try again.\n\nType *menu* for main menu", {"state": "idle", "lang": lang}
       
        st = STATUS_MAP.get(rec.get("status", ""), rec.get("status", ""))
        if ref.startswith("CMP"):
            if lang == "te":
                return f"🔍 *ఫిర్యాదు స్థితి*\n\n📋 ID: {ref}\n👤 పేరు: {rec.get('name', '')}\n📂 వర్గం: {rec.get('category', '')}\n📍 లొకేషన్: {rec.get('location', '')}\n📌 స్థితి: {st}\n📅 నమోదు: {rec.get('filed_at', '')}\n\nమెనూ కోసం *menu* టైప్ చేయండి", {"state": "idle", "lang": lang}
            return f"🔍 *Complaint Status*\n\n📋 ID: {ref}\n👤 Name: {rec.get('name', '')}\n📂 Category: {rec.get('category', '')}\n📍 Location: {rec.get('location', '')}\n📌 Status: {st}\n📅 Filed: {rec.get('filed_at', '')}\n\nType *menu* for main menu", {"state": "idle", "lang": lang}
       
        if lang == "te":
            return f"🔍 *సర్టిఫికెట్ స్థితి*\n\n📋 ID: {ref}\n👤 పేరు: {rec.get('name', '')}\n📄 రకం: {rec.get('type', '')}\n📌 స్థితి: {st}\n📅 నమోదు: {rec.get('filed_at', '')}\n\nమెనూ కోసం *menu* టైప్ చేయండి", {"state": "idle", "lang": lang}
        return f"🔍 *Certificate Status*\n\n📋 ID: {ref}\n👤 Name: {rec.get('name', '')}\n📄 Type: {rec.get('type', '')}\n📌 Status: {st}\n📅 Filed: {rec.get('filed_at', '')}\n\nType *menu* for main menu", {"state": "idle", "lang": lang}
   
    return get_menu({"lang": lang}), {"state": "idle", "lang": lang}

# ── WHATSAPP WEBHOOK ─────────────────────────────────────────
@app.route("/whatsapp", methods=["GET", "POST"])
def whatsapp_webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge", "")
        return "Invalid token", 403
   
    try:
        data = request.json
        print(f"📨 Webhook received")
       
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
       
        if not messages:
            return "OK", 200
       
        msg = messages[0]
        sender = msg.get("from", "")
        msg_type = msg.get("type", "")
       
        if sender not in whatsapp_sessions:
            whatsapp_sessions[sender] = {"state": "idle", "lang": "en"}
       
        session_data = whatsapp_sessions[sender]
       
        if msg_type == "text":
            user_msg = msg["text"]["body"].strip()
            print(f"📝 Text from {sender}: {user_msg}")
            reply, session_data = bot_reply(user_msg, session_data)
            if reply is not None:
                send_whatsapp_message(sender, reply)
            else:
                print(f"🔇 No response sent (ignored message)")
       
        elif msg_type == "location":
            lat = msg["location"]["latitude"]
            lng = msg["location"]["longitude"]
            name = msg["location"].get("name", "")
            address = msg["location"].get("address", "")
            maps_link = f"https://maps.google.com/?q={lat},{lng}"
            detected_village = detect_village_from_coords(lat, lng) or name or "Unknown"
            print(f"📍 Location from {sender}: {detected_village}")
            session_data["location_lat"] = lat
            session_data["location_lng"] = lng
            session_data["location_address"] = address or name
            session_data["maps_link"] = maps_link
            session_data["village"] = detected_village
            if session_data.get("state") == "waiting_for_location":
                session_data["state"] = "c_pri"
                lang = session_data.get("lang", "en")
                if lang == "te":
                    reply = f"📍 లొకేషన్ అందుకుంది!\n\nగ్రామం: {detected_village}\n\n⚡ ఎంత అత్యవసరం?\n1️⃣ తక్కువ\n2️⃣ మధ్యస్థం\n3️⃣ ఎక్కువ"
                else:
                    reply = f"📍 Location received!\n\nVillage: {detected_village}\n\n⚡ How urgent?\n1️⃣ Low\n2️⃣ Medium\n3️⃣ High"
                send_whatsapp_message(sender, reply)
            else:
                if session_data.get("lang", "en") == "te":
                    reply = f"📍 లొకేషన్ అందుకుంది!\n\nగ్రామం: {detected_village}\n\nమీ ఫిర్యాదును కొనసాగించండి"
                else:
                    reply = f"📍 Location received!\n\nVillage: {detected_village}\n\nContinue with your complaint"
                send_whatsapp_message(sender, reply)
       
        elif msg_type == "audio" or msg_type == "voice":
            audio_id = msg.get("audio", {}).get("id") or msg.get("voice", {}).get("id")
            if audio_id:
                print(f"🎤 Audio/Voice from {sender}: {audio_id}")
                media_info = {"type": "voice", "url": None, "audio_id": audio_id}
                reply, session_data = bot_reply("", session_data, media_info)
                if reply is not None:
                    send_whatsapp_message(sender, reply)
            else:
                if session_data.get("lang", "en") == "te":
                    send_whatsapp_message(sender, "దయచేసి టెక్స్ట్, లొకేషన్ లేదా వాయిస్ మెసేజ్ పంపండి.")
                else:
                    send_whatsapp_message(sender, "Please send text, location, or voice message.")
       
        else:
            if session_data.get("lang", "en") == "te":
                send_whatsapp_message(sender, "దయచేసి టెక్స్ట్, లొకేషన్ లేదా వాయిస్ మెసేజ్ పంపండి.")
            else:
                send_whatsapp_message(sender, "Please send text, location, or voice message.")
       
        whatsapp_sessions[sender] = session_data
       
    except Exception as e:
        print(f"❌ Webhook error: {e}")
   
    return "OK", 200

# ── ROUTES ────────────────────────────────────────────────────
@app.route("/")
def home():
    if 'sarpanch_username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
       
        try:
            conn, db_type = get_db()
            cur = conn.cursor()
            p = get_placeholder(db_type)
           
            cur.execute(f"SELECT * FROM sarpanch_users WHERE username = {p} AND password = {p}", (username, hashed_password))
            user = cur.fetchone()
            conn.close()
           
            if user:
                if isinstance(user, dict):
                    session['sarpanch_username'] = user['username']
                    session['sarpanch_village'] = user['village_name']
                    session['sarpanch_photo'] = user.get('photo', '')
                else:
                    session['sarpanch_username'] = user[1]
                    session['sarpanch_village'] = user[3]
                    session['sarpanch_photo'] = user[6] if len(user) > 6 else ''
                return redirect(url_for('dashboard'))
            else:
                error = "Invalid username or password"
        except Exception as e:
            print(f"Login error: {e}")
            error = f"Login error: {str(e)}"
   
    return render_template_string(LOGIN_TEMPLATE, error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route("/profile", methods=["GET", "POST"])
def profile():
    if 'sarpanch_username' not in session:
        return redirect(url_for('login'))
   
    username = session['sarpanch_username']
    user = get_sarpanch_by_username(username)
   
    if request.method == "POST":
        if 'photo' in request.files:
            file = request.files['photo']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{username}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                update_sarpanch_photo(username, f"/static/uploads/{filename}")
                session['sarpanch_photo'] = f"/static/uploads/{filename}"
       
        phone = request.form.get("phone", "")
        email = request.form.get("email", "")
       
        conn, db_type = get_db()
        cur = conn.cursor()
        p = get_placeholder(db_type)
        cur.execute(f"UPDATE sarpanch_users SET phone = {p}, email = {p} WHERE username = {p}", (phone, email, username))
        conn.commit()
        conn.close()
       
        return redirect(url_for('profile'))
   
    return render_template_string(PROFILE_TEMPLATE, user=user)

# ── DASHBOARD ────────────────────────────────────────────────
@app.route("/dashboard")
def dashboard():
    if 'sarpanch_username' not in session:
        return redirect(url_for('login'))
   
    village = session.get('sarpanch_village', 'Kolukonda')
    username = session.get('sarpanch_username', 'Sarpanch')
    photo = session.get('sarpanch_photo', '')
   
    filter_status = request.args.get('filter_status', 'ALL')
    filter_priority = request.args.get('filter_priority', 'ALL')
   
    try:
        ac = all_complaints()
        ce = all_certs()
        wo = all_works()
        an = all_announcements()
       
        filtered_complaints = []
        pending_complaints = []
        in_review_complaints = []
        in_progress_complaints = []
        resolved_complaints = []
        high_priority_complaints = []
       
        for x in ac:
            if isinstance(x, dict):
                status = x.get('status', 'pending')
                priority = x.get('priority', 'medium')
                village_name = x.get('village', '')
                location_text = x.get('location', '')
                filed_at = x.get('filed_at', '')
                display_location = village_name if village_name else location_text
                if not display_location:
                    display_location = 'Not specified'
                problem_text = x.get('description', '')
                if not problem_text:
                    problem_text = 'No description'
               
                c = {
                    'id': x.get('id', ''), 'name': x.get('name', ''), 'phone': x.get('phone', ''),
                    'category': x.get('category', ''), 'description': problem_text,
                    'location': display_location, 'priority': priority,
                    'status': status, 'filed_at': filed_at, 'maps_link': x.get('maps_link', ''),
                    'media_type': x.get('media_type', ''), 'media_url': x.get('media_url', '')
                }
            else:
                status = x[7] if len(x) > 7 else 'pending'
                priority = x[6] if len(x) > 6 else 'medium'
                village_name = x[17] if len(x) > 17 else ''
                location_text = x[5] if len(x) > 5 else ''
                filed_at = x[8] if len(x) > 8 else ''
                display_location = village_name if village_name else location_text
                if not display_location:
                    display_location = 'Not specified'
                problem_text = x[4] if len(x) > 4 else ''
                if not problem_text:
                    problem_text = 'No description'
               
                c = {
                    'id': x[0], 'name': x[1], 'phone': x[2], 'category': x[3],
                    'description': problem_text, 'location': display_location, 'priority': priority,
                    'status': status, 'filed_at': filed_at, 'maps_link': x[13] if len(x) > 13 else '',
                    'media_type': x[15] if len(x) > 15 else '', 'media_url': x[16] if len(x) > 16 else ''
                }
           
            status_match = (filter_status == 'ALL' or status == filter_status)
            priority_match = (filter_priority == 'ALL' or priority == filter_priority)
           
            if status_match and priority_match:
                filtered_complaints.append(c)
           
            if status == 'pending':
                pending_complaints.append(c)
            elif status == 'in_review':
                in_review_complaints.append(c)
            elif status == 'in_progress':
                in_progress_complaints.append(c)
            elif status in ('resolved', 'rejected'):
                resolved_complaints.append(c)
           
            if priority == 'high':
                high_priority_complaints.append(c)
       
        pending_certs = []
        processing_certs = []
       
        for x in ce:
            if isinstance(x, dict):
                status = x.get('status', 'pending')
                cert = {
                    'id': x.get('id', ''), 'type': x.get('type', ''), 'name': x.get('name', ''),
                    'phone': x.get('phone', ''), 'purpose': x.get('purpose', ''),
                    'status': status, 'filed_at': x.get('filed_at', '')
                }
            else:
                status = x[6] if len(x) > 6 else 'pending'
                cert = {
                    'id': x[0], 'type': x[1], 'name': x[2],
                    'phone': x[4] if len(x) > 4 else '', 'purpose': x[5] if len(x) > 5 else '',
                    'status': status, 'filed_at': x[7] if len(x) > 7 else ''
                }
           
            if status == 'pending':
                pending_certs.append(cert)
            elif status == 'processing':
                processing_certs.append(cert)
       
        works = []
        for w in wo:
            if isinstance(w, dict):
                works.append({
                    'id': w.get('id', ''), 'title': w.get('title', ''),
                    'status': w.get('status', 'pending'), 'updated': w.get('updated', '')
                })
            else:
                works.append({
                    'id': w[0], 'title': w[1], 'status': w[2] if len(w) > 2 else 'pending',
                    'updated': w[3] if len(w) > 3 else ''
                })
       
        announcements = []
        for a in an:
            if isinstance(a, dict):
                announcements.append({
                    'id': a.get('id', ''), 'title': a.get('title', ''),
                    'body': a.get('body', ''), 'date': a.get('date', '')
                })
            else:
                announcements.append({
                    'id': a[0], 'title': a[1], 'body': a[2], 'date': a[3] if len(a) > 3 else ''
                })
       
        counts = {
            'total_pending': len(pending_complaints) + len(in_review_complaints) + len(in_progress_complaints),
            'cert_pending': len(pending_certs) + len(processing_certs),
            'resolved': len(resolved_complaints),
            'works': len([w for w in works if w.get('status') in ('pending', 'in_progress')]),
            'high': len(high_priority_complaints)
        }
       
        return render_template_string(DASH_HTML,
            filtered_complaints=filtered_complaints,
            resolved_complaints=resolved_complaints,
            pending_certs=pending_certs,
            processing_certs=processing_certs,
            works=works,
            announcements=announcements,
            village=village,
            username=username,
            photo=photo,
            mandal=MANDAL,
            now=datetime.now().strftime("%d %b %Y, %H:%M"),
            c=counts,
            filter_status=filter_status,
            filter_priority=filter_priority)
    except Exception as e:
        print(f"Dashboard error: {e}")
        return f"Dashboard error: {str(e)}", 500

@app.route("/complaint/<cid>")
def view_complaint(cid):
    if 'sarpanch_username' not in session:
        return redirect(url_for('login'))
   
    try:
        conn, db_type = get_db()
        cur = conn.cursor()
        p = get_placeholder(db_type)
        cur.execute(f"SELECT * FROM complaints WHERE id = {p}", (cid,))
        row = cur.fetchone()
        conn.close()
       
        if not row:
            return "Complaint not found", 404
       
        if isinstance(row, dict):
            complaint_dict = row
        else:
            complaint_dict = {
                'id': row[0], 'name': row[1], 'phone': row[2], 'category': row[3],
                'description': row[4], 'location': row[5] or (row[17] if len(row) > 17 else ''),
                'priority': row[6], 'status': row[7], 'filed_at': row[8],
                'maps_link': row[13] if len(row) > 13 else '',
                'location_lat': row[11] if len(row) > 11 else '',
                'location_lng': row[12] if len(row) > 12 else '',
                'media_type': row[15] if len(row) > 15 else '',
                'media_url': row[16] if len(row) > 16 else ''
            }
       
        return render_template_string(COMPLAINT_DETAIL_HTML, complaint=complaint_dict)
    except Exception as e:
        print(f"Error viewing complaint: {e}")
        return f"Error: {e}", 500

@app.route("/update_status", methods=["POST"])
def update_status_route():
    if 'sarpanch_username' not in session:
        return redirect(url_for('login'))
   
    try:
        ticket_id = request.form.get("ticket_id")
        new_status = request.form.get("status")
        notes = request.form.get("notes", "")
        conn, db_type = get_db()
        cur = conn.cursor()
        p = get_placeholder(db_type)
        cur.execute(f"UPDATE complaints SET status = {p}, notes = {p} WHERE id = {p}", (new_status, notes, ticket_id))
        conn.commit()
        conn.close()
        return redirect(url_for('view_complaint', cid=ticket_id))
    except Exception as e:
        print(f"Error updating status: {e}")
        return f"Error: {e}", 500

@app.route("/send_reply", methods=["POST"])
def send_reply_route():
    if 'sarpanch_username' not in session:
        return redirect(url_for('login'))
   
    ticket_id = request.form.get("ticket_id")
    reply_message = request.form.get("reply_message")
    conn, db_type = get_db()
    cur = conn.cursor()
    p = get_placeholder(db_type)
    cur.execute(f"SELECT phone FROM complaints WHERE id = {p}", (ticket_id,))
    result = cur.fetchone()
    conn.close()
    if result:
        citizen_number = result[0] if not isinstance(result, dict) else result.get('phone')
        send_whatsapp_message(citizen_number, f"📢 Update on Ticket {ticket_id}\n\n{reply_message}\n\n- Sarpanch, {session.get('sarpanch_village', '')}")
    return redirect(url_for('view_complaint', cid=ticket_id))

@app.route("/caction/<rid>/<action>")
def c_action(rid, action):
    if 'sarpanch_username' not in session:
        return redirect(url_for('login'))
    update_status("complaints", rid.upper(), action)
    return redirect(url_for('dashboard'))

@app.route("/certaction/<rid>/<action>")
def cert_action(rid, action):
    if 'sarpanch_username' not in session:
        return redirect(url_for('login'))
    update_status("certificates", rid.upper(), action)
    return redirect(url_for('dashboard'))

@app.route("/waction/<rid>/<action>")
def w_action(rid, action):
    if 'sarpanch_username' not in session:
        return redirect(url_for('login'))
    update_status("works", rid.upper(), action)
    return redirect(url_for('dashboard'))

@app.route("/addwork", methods=["POST"])
def add_work():
    if 'sarpanch_username' not in session:
        return redirect(url_for('login'))
    t = request.form.get("title", "").strip()
    if t:
        insert_work(t)
    return redirect(url_for('dashboard'))

@app.route("/announce", methods=["POST"])
def announce():
    if 'sarpanch_username' not in session:
        return redirect(url_for('login'))
    t = request.form.get("title", "").strip()
    b = request.form.get("body", "").strip()
    if t and b:
        insert_announcement(t, b)
    return redirect(url_for('dashboard'))

@app.route("/sarpanchs")
def list_sarpanchs():
    if 'sarpanch_username' not in session:
        return redirect(url_for('login'))
    sarpanchs = get_all_sarpanchs()
    return render_template_string(SARPANCH_LIST_TEMPLATE, sarpanchs=sarpanchs)

@app.route("/add_sarpanch", methods=["GET", "POST"])
def add_sarpanch():
    if 'sarpanch_username' not in session:
        return redirect(url_for('login'))
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        village_name = request.form.get("village_name")
        phone = request.form.get("phone")
        email = request.form.get("email")
       
        if not all([username, password, village_name]):
            error = "Username, Password, and Village Name are required"
        else:
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            conn, db_type = get_db()
            cur = conn.cursor()
            p = get_placeholder(db_type)
            try:
                cur.execute(f"INSERT INTO sarpanch_users (username, password, village_name, phone, email, created_at) VALUES ({p},{p},{p},{p},{p},{p})",
                           (username, hashed_password, village_name, phone, email, now_str()))
                conn.commit()
                return redirect(url_for('list_sarpanchs'))
            except Exception as e:
                error = f"Username already exists: {e}"
            finally:
                conn.close()
   
    return render_template_string(ADD_SARPANCH_TEMPLATE, error=error)

# ── HTML TEMPLATES ────────────────────────────────────────────
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>Sarpanch Login</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}
body{font-family:Arial;display:flex;justify-content:center;align-items:center;height:100vh;background:#f0f2f5;margin:0;padding:15px}
.login-container{background:white;padding:30px;border-radius:10px;width:100%;max-width:350px;box-shadow:0 2px 10px rgba(0,0,0,0.1)}
h2{color:#4a7c59;text-align:center;margin:0 0 10px 0}
h3{text-align:center;margin:0 0 20px 0;color:#333}
input{width:100%;padding:12px;margin:10px 0;border:1px solid #ddd;border-radius:5px;font-size:16px}
button{width:100%;padding:12px;background:#4a7c59;color:white;border:none;border-radius:5px;cursor:pointer;font-size:16px}
.error{color:red;text-align:center}
</style>
</head>
<body>
<div class="login-container">
<h2>🏘️ Gram Panchayat</h2>
<h3>Sarpanch Login</h3>
{% if error %}<p class="error">{{ error }}</p>{% endif %}
<form method="POST">
<input type="text" name="username" placeholder="Username" required>
<input type="password" name="password" placeholder="Password" required>
<button type="submit">Login</button>
</form>
<p style="text-align:center;font-size:12px;margin-top:15px">Contact administrator for credentials</p>
</div>
</body></html>
"""

PROFILE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>My Profile</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}
body{font-family:Arial;margin:0;background:#f0f2f5}
.header{background:#4a7c59;color:white;padding:15px 20px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap}
.container{max-width:600px;margin:30px auto;background:white;padding:25px;border-radius:10px}
.photo-preview{width:360px;height:360px;object-fit:cover;margin:0 auto 15px auto;display:block;border:3px solid #4a7c59}
.field{margin-bottom:15px}
.label{font-weight:bold;display:block;margin-bottom:5px}
input{width:100%;padding:10px;border:1px solid #ddd;border-radius:5px;font-size:14px}
button{background:#4a7c59;color:white;border:none;padding:12px 20px;border-radius:5px;cursor:pointer;font-size:16px}
.btn-back{background:#666;text-decoration:none;color:white;padding:8px 15px;border-radius:5px;display:inline-block}
@media (max-width:600px){.photo-preview{width:200px;height:200px}}
</style>
</head>
<body>
<div class="header">
<h2>My Profile</h2>
<a href="/dashboard" class="btn-back">← Dashboard</a>
</div>
<div class="container">
<form method="POST" enctype="multipart/form-data">
<div style="text-align:center">
{% if user and user.photo %}
<img src="{{ user.photo }}" class="photo-preview" alt="Profile Photo">
{% else %}
<div class="photo-preview" style="background:#ddd;display:flex;align-items:center;justify-content:center">No Photo</div>
{% endif %}
<input type="file" name="photo" accept="image/*">
</div>
<div class="field">
<label class="label">Username</label>
<input type="text" value="{{ user.username if user else '' }}" disabled>
</div>
<div class="field">
<label class="label">Village Name</label>
<input type="text" value="{{ user.village_name if user else '' }}" disabled>
</div>
<div class="field">
<label class="label">Phone Number</label>
<input type="tel" name="phone" value="{{ user.phone if user else '' }}">
</div>
<div class="field">
<label class="label">Email</label>
<input type="email" name="email" value="{{ user.email if user else '' }}">
</div>
<button type="submit">Update Profile</button>
</form>
</div>
</body></html>
"""

SARPANCH_LIST_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>Sarpanch Users</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}
body{font-family:Arial;margin:0;background:#f0f2f5}
.header{background:#4a7c59;color:white;padding:15px 20px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap}
.container{max-width:100%;margin:20px;background:white;padding:20px;border-radius:10px;overflow-x:auto}
table{width:100%;border-collapse:collapse;min-width:600px}
th,td{padding:12px;text-align:left;border-bottom:1px solid #ddd}
th{background:#f4f5f7}
.photo{width:50px;height:50px;object-fit:cover;border-radius:50%}
.btn{background:#4a7c59;color:white;padding:8px 15px;text-decoration:none;border-radius:5px;display:inline-block}
.btn-back{background:#666}
@media (max-width:768px){th,td{padding:8px;font-size:12px}}
</style>
</head>
<body>
<div class="header">
<h2>Sarpanch Users</h2>
<div>
<a href="/add_sarpanch" class="btn">+ Add</a>
<a href="/dashboard" class="btn btn-back">← Back</a>
</div>
</div>
<div class="container">
<table>
<thead>
<tr>
<th>Photo</th><th>Username</th><th>Village</th><th>Phone</th><th>Email</th><th>Joined</th>
</tr>
</thead>
<tbody>
{% for s in sarpanchs %}
<tr>
<td style="text-align:center">{% if s.photo %}<img src="{{ s.photo }}" class="photo">{% else %}📷{% endif %}</td>
<td style="text-align:center">{{ s.username }}</td>
<td style="text-align:center">{{ s.village_name }}</td>
<td style="text-align:center">{{ s.phone or '-' }}</td>
<td style="text-align:center">{{ s.email or '-' }}</td>
<td style="text-align:center">{{ s.created_at[:16] if s.created_at else '-' }}</td>
</tr>
{% endfor %}
</tbody>
</table>
</div>
</body></html>
"""

ADD_SARPANCH_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>Add Sarpanch</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}
body{font-family:Arial;margin:0;background:#f0f2f5}
.header{background:#4a7c59;color:white;padding:15px 20px}
.container{max-width:500px;margin:30px auto;background:white;padding:25px;border-radius:10px}
.field{margin-bottom:15px}
.label{font-weight:bold;display:block;margin-bottom:5px}
input{width:100%;padding:10px;border:1px solid #ddd;border-radius:5px}
button{background:#4a7c59;color:white;border:none;padding:12px;border-radius:5px;cursor:pointer;width:100%}
.error{color:red}
.btn-back{background:#666;text-decoration:none;color:white;padding:8px 15px;border-radius:5px;display:inline-block;margin-bottom:20px}
</style>
</head>
<body>
<div class="header"><h2>Add New Sarpanch</h2></div>
<div class="container">
<a href="/sarpanchs" class="btn-back">← Back</a>
{% if error %}<p class="error">{{ error }}</p>{% endif %}
<form method="POST">
<div class="field"><label class="label">Username *</label><input type="text" name="username" required></div>
<div class="field"><label class="label">Password *</label><input type="password" name="password" required></div>
<div class="field"><label class="label">Village Name *</label><input type="text" name="village_name" required></div>
<div class="field"><label class="label">Phone Number</label><input type="tel" name="phone"></div>
<div class="field"><label class="label">Email</label><input type="email" name="email"></div>
<button type="submit">Add Sarpanch</button>
</form>
</div>
</body></html>
"""

DASH_HTML = r"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>{{ village }} Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--green:#4a7c59;--red:#c0392b;--blue:#0070f3;--amber:#e07b00;--border:#dfe1e6;--text:#172b4d;--sub:#6b778c}
body{font-family:'DM Sans',sans-serif;background:#f0f2f5;color:var(--text)}
.tb{background:var(--green);color:#fff;padding:15px 20px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap}
.tl{display:flex;flex-direction:column;align-items:center;gap:10px;flex:1}
.avatar{width:360px;height:360px;object-fit:cover;border:3px solid rgba(255,255,255,.4)}
.village-info{text-align:center}
.village-info h1{font-size:18px}
.village-info .ts{font-size:12px;opacity:.75}
.nav-links{display:flex;gap:15px;flex-wrap:wrap}
.nav-links a{color:white;text-decoration:none;padding:5px 10px;background:rgba(255,255,255,0.15);border-radius:5px}
.stats{display:flex;gap:12px;padding:18px 20px;flex-wrap:wrap}
.sc{background:#fff;border-radius:10px;padding:14px 20px;flex:1;min-width:100px;text-align:center;cursor:pointer;transition:transform 0.2s,box-shadow 0.2s;box-shadow:0 1px 4px rgba(0,0,0,.06)}
.sc:hover{transform:translateY(-2px);box-shadow:0 4px 12px rgba(0,0,0,.1)}
.sc .val{font-size:24px;font-weight:700}
.sc .lbl{font-size:11px;color:var(--sub);margin-top:2px}
.sc.c1 .val{color:var(--amber)}.sc.c2 .val{color:var(--blue)}.sc.c3 .val{color:var(--green)}.sc.c4 .val{color:#7b2d8b}.sc.c5 .val{color:var(--red)}
.filter-bar{display:flex;gap:10px;padding:0 20px 15px 20px;flex-wrap:wrap}
.filter-btn{padding:6px 12px;border-radius:20px;border:none;cursor:pointer;background:#e0e0e0;font-size:12px}
.filter-btn.active{background:var(--green);color:white}
.sec{margin:18px 20px;background:#fff;border-radius:12px;box-shadow:0 1px 4px rgba(0,0,0,.06);overflow-x:auto}
.sh{padding:12px 18px;border-bottom:1px solid var(--border);font-weight:600;font-size:14px;background:#f4f5f7}
table{width:100%;border-collapse:collapse;min-width:700px}
th{padding:10px 12px;font-size:11px;color:var(--sub);text-align:left;background:#f4f5f7;border-bottom:1px solid var(--border)}
td{padding:10px 12px;font-size:12px;border-bottom:1px solid var(--border);vertical-align:middle}
.sortable{cursor:pointer;user-select:none}
.sortable:hover{background:#e8e8e8}
.badge{display:inline-block;padding:2px 8px;border-radius:20px;font-size:10px;font-weight:600}
.badge.pending{background:#fff4e0;color:var(--amber)}
.badge.in_review{background:#dbeafe;color:var(--blue)}
.badge.in_progress{background:#e0e7ff;color:#4338ca}
.badge.resolved{background:#dcfce7;color:var(--green)}
.badge.rejected{background:#fee2e2;color:var(--red)}
.acts{display:flex;gap:5px;flex-wrap:wrap}
.btn{padding:3px 8px;border-radius:4px;font-size:10px;font-weight:600;text-decoration:none;display:inline-block}
.bb{background:var(--blue);color:#fff}.bg{background:var(--green);color:#fff}
.br{background:var(--red);color:#fff}.ba{background:var(--amber);color:#fff}
.empty{text-align:center;padding:28px;color:var(--sub);font-size:13px}
.map-link{color:#1a73e8;text-decoration:none}
.audio-player{width:100%;margin-top:5px}
@media (max-width:768px){
.avatar{width:200px;height:200px}
.stats{gap:8px}.sc{padding:10px 12px;min-width:70px}.sc .val{font-size:18px}
.tb{flex-direction:column;gap:15px;text-align:center}
.nav-links{justify-content:center}
.tl{align-items:center}
}
</style>
</head>
<body>
<div class="tb">
<div class="tl">
{% if photo %}<img src="{{ photo }}" class="avatar">{% else %}<div class="avatar" style="background:#ccc;display:flex;align-items:center;justify-content:center">👤</div>{% endif %}
<div class="village-info"><h1>{{ village }}</h1><div class="ts">{{ username }} · {{ mandal }}</div></div>
</div>
<div class="nav-links">
<a href="/profile">Profile</a>
<a href="/sarpanchs">Sarpanchs</a>
<a href="/logout">Logout</a>
</div>
</div>
<div class="stats">
<div class="sc c1" onclick="window.location.href='?filter_status=ALL&filter_priority=ALL'"><div class="val">{{ c.total_pending }}</div><div class="lbl">Pending Complaints</div></div>
<div class="sc c2" onclick="window.location.href='?filter_status=ALL&filter_priority=ALL'"><div class="val">{{ c.cert_pending }}</div><div class="lbl">Cert Requests</div></div>
<div class="sc c3" onclick="window.location.href='?filter_status=resolved&filter_priority=ALL'"><div class="val">{{ c.resolved }}</div><div class="lbl">Resolved</div></div>
<div class="sc c4" onclick="window.location.href='?filter_status=ALL&filter_priority=ALL'"><div class="val">{{ c.works }}</div><div class="lbl">Active Works</div></div>
<div class="sc c5" onclick="window.location.href='?filter_status=ALL&filter_priority=high'"><div class="val">{{ c.high }}</div><div class="lbl">High Priority</div></div>
</div>
<div class="filter-bar">
<span style="font-size:12px;color:#666">Filter by Status:</span>
<a href="?filter_status=ALL&filter_priority={{ filter_priority }}"><button class="filter-btn {% if filter_status == 'ALL' %}active{% endif %}">All</button></a>
<a href="?filter_status=pending&filter_priority={{ filter_priority }}"><button class="filter-btn {% if filter_status == 'pending' %}active{% endif %}">Pending</button></a>
<a href="?filter_status=in_review&filter_priority={{ filter_priority }}"><button class="filter-btn {% if filter_status == 'in_review' %}active{% endif %}">In Review</button></a>
<a href="?filter_status=in_progress&filter_priority={{ filter_priority }}"><button class="filter-btn {% if filter_status == 'in_progress' %}active{% endif %}">In Progress</button></a>
<a href="?filter_status=resolved&filter_priority={{ filter_priority }}"><button class="filter-btn {% if filter_status == 'resolved' %}active{% endif %}">Resolved</button></a>
</div>
<div class="filter-bar">
<span style="font-size:12px;color:#666">Filter by Priority:</span>
<a href="?filter_status={{ filter_status }}&filter_priority=ALL"><button class="filter-btn {% if filter_priority == 'ALL' %}active{% endif %}">All</button></a>
<a href="?filter_status={{ filter_status }}&filter_priority=low"><button class="filter-btn {% if filter_priority == 'low' %}active{% endif %}">Low</button></a>
<a href="?filter_status={{ filter_status }}&filter_priority=medium"><button class="filter-btn {% if filter_priority == 'medium' %}active{% endif %}">Medium</button></a>
<a href="?filter_status={{ filter_status }}&filter_priority=high"><button class="filter-btn {% if filter_priority == 'high' %}active{% endif %}">High</button></a>
</div>
<div class="sec">
<div class="sh">📋 Complaints</div>
{% if filtered_complaints %}
<table id="complaintTable">
<thead>
<tr>
<th class="sortable" onclick="sortTable(0)">ID</th>
<th class="sortable" onclick="sortTable(1)">Name</th>
<th class="sortable" onclick="sortTable(2)">Category</th>
<th>Problem</th>
<th>Location</th>
<th class="sortable" onclick="sortTable(5)">Priority</th>
<th class="sortable" onclick="sortTable(6)">Status</th>
<th class="sortable" onclick="sortTable(7)">📅 Reported On</th>
<th>Actions</th>
</tr>
</thead>
<tbody>
{% for x in filtered_complaints %}
<tr>
<td><strong>{{ x.id }}</strong></td>
<td>{{ x.name }}<br><small>{{ x.phone }}</small></td>
<td>{{ x.category }}</td>
<td><small>{{ x.description[:50] }}{% if x.description|length > 50 %}...{% endif %}</small></td>
<td>{% if x.maps_link %}<a href="{{ x.maps_link }}" target="_blank" class="map-link">📍 {{ x.location }}</a>{% else %}{{ x.location }}{% endif %}</td>
<td class="p{{ x.priority[0] }}">{{ x.priority|upper }}</td>
<td><span class="badge {{ x.status }}">{{ x.status.replace('_',' ').title() }}</span></td>
<td><small>{{ x.filed_at }}</small></td>
<td class="acts">
{% if x.status=='pending' %}<a href="/caction/{{ x.id }}/in_review" class="btn bb">Review</a>{% endif %}
{% if x.status=='in_review' %}<a href="/caction/{{ x.id }}/in_progress" class="btn ba">Start</a>{% endif %}
{% if x.status=='in_progress' %}<a href="/caction/{{ x.id }}/resolved" class="btn bg">Done</a>{% endif %}
<a href="/caction/{{ x.id }}/rejected" class="btn br">X</a>
<a href="/complaint/{{ x.id }}" class="btn bb" style="background:#666">View</a>
</div></td>
</tr>
{% endfor %}
</tbody>
</table>
{% else %}<div class="empty">No complaints found.</div>{% endif %}
</div>
<div class="sec">
<div class="sh">📋 Certificate Requests</div>
{% if pending_certs or processing_certs %}
<table>
<thead><tr><th>ID</th><th>Name</th><th>Type</th><th>Purpose</th><th>Status</th><th>Actions</th></tr></thead>
<tbody>
{% for x in pending_certs %}
<tr><td>{{ x.id }}</td><td>{{ x.name }}</td><td>{{ x.type }}</td><td>{{ x.purpose }}</td><td><span class="badge pending">Pending</span></td>
<td><a href="/certaction/{{ x.id }}/processing" class="btn bb">Process</a> <a href="/certaction/{{ x.id }}/rejected" class="btn br">X</a></td>
</tr>
{% endfor %}
{% for x in processing_certs %}
<tr><td>{{ x.id }}</td><td>{{ x.name }}</td><td>{{ x.type }}</td><td>{{ x.purpose }}</td><td><span class="badge processing">Processing</span></td>
<td><a href="/certaction/{{ x.id }}/ready" class="btn bg">Ready</a> <a href="/certaction/{{ x.id }}/rejected" class="btn br">X</a></td>
</tr>
{% endfor %}
</tbody>
</table>
{% else %}<div class="empty">No pending certificate requests.</div>{% endif %}
</div>
<div class="sec">
<div class="sh">🛠️ Development Works</div>
{% if works %}
<table>
<thead><tr><th>ID</th><th>Title</th><th>Status</th><th>Updated</th><th>Actions</th></tr></thead>
<tbody>
{% for w in works %}
<tr><td>{{ w.id }}</td><td>{{ w.title }}</td><td><span class="badge {{ w.status }}">{{ w.status.replace('_',' ').title() }}</span></td><td>{{ w.updated }}</td>
<td class="acts">
{% if w.status=='pending' %}<a href="/waction/{{ w.id }}/in_progress" class="btn bb">Start</a>{% endif %}
{% if w.status=='in_progress' %}<a href="/waction/{{ w.id }}/resolved" class="btn bg">Done</a>{% endif %}
<a href="/waction/{{ w.id }}/rejected" class="btn br">X</a>
</td>
</tr>
{% endfor %}
</tbody>
</table>
{% else %}<div class="empty">No works added.</div>{% endif %}
<form method="post" action="/addwork" style="padding:14px 18px;border-top:1px solid var(--border);display:flex;gap:8px;flex-wrap:wrap">
<input type="text" name="title" placeholder="Add new work" required style="flex:1;border:1px solid var(--border);border-radius:6px;padding:8px 12px">
<button type="submit" style="background:var(--green);color:#fff;border:none;border-radius:6px;padding:8px 16px">+ Add Work</button>
</form>
</div>
<div class="sec">
<div class="sh">📢 Announcements</div>
{% if announcements %}
<table><thead><tr><th>Title</th><th>Message</th><th>Date</th></tr></thead><tbody>
{% for a in announcements %}
<tr><td><strong>{{ a.title }}</strong></td><td>{{ a.body }}</td><td style="font-size:11px;color:#888">{{ a.date }}</td>
</tr>
{% endfor %}
</tbody></table>
{% else %}<div class="empty">No announcements.</div>{% endif %}
<form method="post" action="/announce" style="padding:14px 18px;border-top:1px solid var(--border);display:flex;gap:8px;flex-wrap:wrap">
<input type="text" name="title" placeholder="Title" required style="flex:1;border:1px solid var(--border);border-radius:6px;padding:8px 12px">
<input type="text" name="body" placeholder="Message..." required style="flex:2;border:1px solid var(--border);border-radius:6px;padding:8px 12px">
<button type="submit" style="background:var(--green);color:#fff;border:none;border-radius:6px;padding:8px 16px">Post</button>
</form>
</div>
<div class="sec">
<div class="sh">✅ Resolved / Closed Items</div>
{% if resolved_complaints %}
<table><thead><tr><th>ID</th><th>Name</th><th>Category</th><th>Status</th><th>Action</th></tr></thead>
<tbody>
{% for x in resolved_complaints %}
<tr><td>{{ x.id }}</td><td>{{ x.name }}</td><td>{{ x.category }}</td><td><span class="badge {{ x.status }}">{{ x.status.title() }}</span></td>
<td><a href="/complaint/{{ x.id }}" class="btn bb" style="background:#666">View</a></td>
</tr>
{% endfor %}
</tbody></table>
{% else %}<div class="empty">No resolved items.</div>{% endif %}
</div>
<script>
function sortTable(colIndex) {
    var table = document.querySelector('#complaintTable');
    if (!table) return;
    var tbody = table.querySelector('tbody');
    var rows = Array.from(tbody.querySelectorAll('tr'));
    var ascending = table.getAttribute('data-sort-asc') === colIndex.toString() ? false : true;
    rows.sort(function(a, b) {
        var aVal = a.cells[colIndex].innerText.trim();
        var bVal = b.cells[colIndex].innerText.trim();
        if (colIndex === 5) {
            var pOrder = {LOW: 1, MEDIUM: 2, HIGH: 3};
            aVal = pOrder[aVal] || 0;
            bVal = pOrder[bVal] || 0;
        } else if (colIndex === 6) {
            var sOrder = {PENDING: 1, 'IN REVIEW': 2, 'IN PROGRESS': 3, RESOLVED: 4, REJECTED: 5};
            aVal = sOrder[aVal] || 0;
            bVal = sOrder[bVal] || 0;
        }
        if (aVal < bVal) return ascending ? -1 : 1;
        if (aVal > bVal) return ascending ? 1 : -1;
        return 0;
    });
    rows.forEach(function(row) { tbody.appendChild(row); });
    table.setAttribute('data-sort-asc', ascending ? colIndex : '');
}
</script>
</body></html>
"""

COMPLAINT_DETAIL_HTML = r"""<!DOCTYPE html>
<html>
<head><title>Complaint Details</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}
body{font-family:Arial;margin:0;background:#f5f5f5}
.header{background:#4a7c59;color:white;padding:15px 20px}
.container{max-width:800px;margin:30px auto;background:white;padding:25px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.1)}
.field{margin-bottom:15px}
.label{font-weight:bold;width:150px;display:inline-block}
button{background:#1a73e8;color:white;border:none;padding:10px 20px;border-radius:5px;cursor:pointer}
.reply-box{width:100%;padding:10px;margin:10px 0;border:1px solid #ddd;border-radius:5px}
.back-btn{background:#666;color:white;padding:8px 15px;text-decoration:none;display:inline-block;margin-bottom:20px;border-radius:5px}
hr{margin:20px 0}
.map-link{color:#1a73e8;text-decoration:none}
.audio-player{width:100%;margin-top:5px}
@media (max-width:600px){.label{width:100%;display:block;margin-bottom:5px}}
</style>
</head>
<body>
<div class="header"><h2>Complaint Details</h2></div>
<div class="container">
<a href="/dashboard" class="back-btn">← Back to Dashboard</a>
<div class="field"><span class="label">Ticket ID:</span> {{ complaint.get('id', 'N/A') }}</div>
<div class="field"><span class="label">Citizen Name:</span> {{ complaint.get('name', 'Unknown') }}</div>
<div class="field"><span class="label">Phone:</span> {{ complaint.get('phone', 'N/A') }}</div>
<div class="field"><span class="label">Category:</span> {{ complaint.get('category', 'General') }}</div>
<div class="field"><span class="label">Problem/Complaint:</span><br><div style="background:#f8f9fa;padding:15px;border-radius:5px;margin-top:5px">{{ complaint.get('description', 'No description') }}</div></div>
<div class="field"><span class="label">Location/Village:</span> {{ complaint.get('location', 'Not provided') }}</div>
<div class="field"><span class="label">Priority:</span> {{ complaint.get('priority', 'medium')|upper }}</div>
<div class="field"><span class="label">Status:</span> {{ complaint.get('status', 'pending').replace('_',' ').title() }}</div>
<div class="field"><span class="label">Filed:</span> {{ complaint.get('filed_at', 'Unknown') }}</div>
{% if complaint.get('maps_link') %}
<div class="field"><span class="label">🗺️ Map Location:</span> <a href="{{ complaint.get('maps_link') }}" target="_blank" class="map-link">Click to view on Google Maps</a><br><small>Coordinates: {{ complaint.get('location_lat', 'N/A') }}, {{ complaint.get('location_lng', 'N/A') }}</small></div>
{% endif %}
{% if complaint.get('media_type') == 'voice' and complaint.get('media_url') %}
<div class="field"><span class="label">🎤 Voice Message:</span><br>
<audio controls class="audio-player">
<source src="{{ complaint.get('media_url') }}" type="audio/ogg">
Your browser does not support the audio element.
</audio>
</div>
{% endif %}
<hr>
<h3>Update Status</h3>
<form method="POST" action="/update_status">
<input type="hidden" name="ticket_id" value="{{ complaint.get('id') }}">
<select name="status">
<option value="pending" {% if complaint.get('status')=='pending' %}selected{% endif %}>Pending</option>
<option value="in_review" {% if complaint.get('status')=='in_review' %}selected{% endif %}>In Review</option>
<option value="in_progress" {% if complaint.get('status')=='in_progress' %}selected{% endif %}>In Progress</option>
<option value="resolved" {% if complaint.get('status')=='resolved' %}selected{% endif %}>Resolved</option>
<option value="rejected" {% if complaint.get('status')=='rejected' %}selected{% endif %}>Rejected</option>
</select>
<textarea name="notes" placeholder="Add internal notes..." rows="2" style="width:100%;margin:10px 0"></textarea>
<button type="submit">Update Status</button>
</form>
<hr>
<h3>Send Reply to Citizen</h3>
<form method="POST" action="/send_reply">
<input type="hidden" name="ticket_id" value="{{ complaint.get('id') }}">
<textarea name="reply_message" class="reply-box" rows="4" placeholder="Type your reply... Citizen will receive this on WhatsApp"></textarea>
<button type="submit">Send Reply</button>
</form>
</div>
</body></html>
"""

# ── RUN ──────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5006))
    print(f"🚀 Starting on port {port}")
    print(f"📞 WhatsApp Business Number: +91 80080 42801")
    print(f"🎯 Bot only responds to: hi, hello, start, menu, help")
    app.run(host="0.0.0.0", port=port, debug=not DATABASE_URL)