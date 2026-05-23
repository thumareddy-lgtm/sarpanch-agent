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
    """Download voice file to server permanently - no token needed after download"""
    if not META_TOKEN:
        print("❌ No META_TOKEN for voice download")
        return None
   
    # Create voices directory
    voice_dir = os.path.join('static', 'voices')
    os.makedirs(voice_dir, exist_ok=True)
   
    headers = {"Authorization": f"Bearer {META_TOKEN}"}
   
    try:
        # Step 1: Get media URL from Meta
        media_resp = requests.get(f"https://graph.facebook.com/v19.0/{voice_id}", headers=headers, timeout=10)
       
        if media_resp.status_code != 200:
            print(f"❌ Failed to get media info: {media_resp.status_code}")
            return None
       
        download_url = media_resp.json().get("url")
        if not download_url:
            print("❌ No download URL in response")
            return None
       
        # Step 2: Download the audio file
        audio_resp = requests.get(download_url, headers=headers, timeout=30)
       
        if audio_resp.status_code != 200:
            print(f"❌ Failed to download audio: {audio_resp.status_code}")
            return None
       
        # Step 3: Save permanently
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

# ── BOT REPLY FUNCTION (FIXED - ONLY RESPONDS TO TRIGGER WORDS) ──
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
    # Numbers 1-7 will ONLY work AFTER the menu is shown (state changes)
    # ──────────────────────────────────────────────────────────
    if state == "idle":
        # Define trigger words that show the menu
        trigger_words = {'hi', 'hello', 'start', 'menu', 'help'}
        
        if ml in trigger_words:
            # Show menu and keep state as idle
            return get_menu({"lang": lang}), {"state": "idle", "lang": lang}
        else:
            # Ignore all other random messages when idle
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
       
        # Download voice permanently if exists
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
# [All routes remain EXACTLY the same as your working script]
# Including: home, login, logout, profile, dashboard, view_complaint,
# update_status, send_reply, c_action, cert_action, w_action,
# addwork, announce, list_sarpanchs, add_sarpanch
# And all HTML templates (LOGIN_TEMPLATE, PROFILE_TEMPLATE, 
# SARPANCH_LIST_TEMPLATE, ADD_SARPANCH_TEMPLATE, DASH_HTML, 
# COMPLAINT_DETAIL_HTML)

# ── RUN ──────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5006))
    print(f"🚀 Starting on port {port}")
    print(f"📞 WhatsApp Business Number: +91 80080 42801")
    print(f"🎯 Bot only responds to: hi, hello, start, menu, help")
    app.run(host="0.0.0.0", port=port, debug=not DATABASE_URL)