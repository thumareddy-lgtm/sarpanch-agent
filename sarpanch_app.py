In your production script, the issue occurs inside the `bot_reply` function. Under the fallback condition of the `if state == "idle":` statement, any unrecognized message triggers the `else:` branch, which automatically drops the user context and returns the main menu via `get_menu({"lang": lang})`.

```python
    if state == "idle":
        if ml == "1":
            # ...
        # ... Other menu options (2-7)
        else:
            return get_menu({"lang": lang}), {"state": "idle", "lang": lang}

```

To update this behavior so the bot selectively greets citizens when they start a fresh conversation instead of abruptly pushing the menu options, we can implement a greeting check. If a citizen types a custom phrase or random sentence, the bot will gently say **"Hi"** or **"Hello"**, and *then* present the main menu.

Here is the fully analyzed, corrected, and ready-to-deploy production Python file:

```python
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

# ── BOT REPLY FUNCTION ───────────────────────────────────────
def bot_reply(user_msg, ctx, media_info=None):
    msg = user_msg.strip() if user_msg else ""
    ml = msg.lower()
    state = ctx.get("state", "idle")
    lang = ctx.get("lang", "en")
   
    print(f"🔍 DEBUG: state={state}, msg={msg[:30] if msg else 'empty'}, lang={lang}")
   
    if ml == "telugu":
        return MENU_TE, {"state": "idle", "lang": "te"}
    if ml == "english":
        return MENU_EN, {"state": "idle", "lang": "en"}
   
    if ml in ("menu", "home", "back", "hi", "hello", "start", "help"):
        greeting = "Hi, " if lang == "en" else "హలో, "
        return greeting + get_menu({"lang": lang}), {"state": "idle", "lang": lang}
   
    # Handle voice message
    if media_info and media_info.get("type") == "voice":
        ctx["media_type"] = "voice"
        ctx["media_url"] = media_info.get("url", "")
        ctx["temp_audio_id"] = media_info.get("audio_id", "")
        ctx["state"] = "waiting_for_location"
        if lang == "te":
            return "🎤 వాయిస్ మెసేజ్ అందుకుంది!\n\n📍 దయచేసి మీ లొకేషన్ షేర్ చేయండి (📎 → Location):", ctx
        return "🎤 Voice received! Please share your location (📎 → Location):", ctx
   
    if state == "idle":
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
        else:
            # Instead of blindly loading the menu, format it with a friendly greeting first!
            greeting = "Hello! " if lang == "en" else "నమస్కారం! "
            return greeting + get_menu({"lang": lang}), {"state": "idle", "lang": lang}
   
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
            send_whatsapp_message(sender, reply)
       
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
                display_location = village_name if village_name else location_text
                if not display_location:
                    display_location = 'Not specified'
                problem_text = x.get('description', '')
                if not problem_text:
                    problem_text = 'No description'
                c = {
                    'id': x.get('id', ''),
                    'name': x.get('name', ''),
                    'phone': x.get('phone', ''),
                    'category': x.get('category', ''),
                    'description': problem_text,
                    'location': display_location,
                    'priority': priority,
                    'status': status,
                    'filed_at': x.get('filed_at', ''),
                    'maps_link': x.get('maps_link', ''),
                    'media_type': x.get('media_type', ''),
                    'media_url': x.get('media_url', '')
                }
            else:
                status = x[7] if len(x) > 7 else 'pending'
                priority = x[6] if len(x) > 6 else 'medium'
                village_name = x[17] if len(x) > 17 else ''
                location_text = x[5] if len(x) > 5 else ''
                display_location = village_name if village_name else location_text
                if not display_location:
                    display_location = 'Not specified'
                problem_text = x[4] if len(x) > 4 else ''
                if not problem_text:
                    problem_text = 'No description'
                c = {
                    'id': x[0],
                    'name': x[1],
                    'phone': x[2],
                    'category': x[3],
                    'description': problem_text,
                    'location': display_location,
                    'priority': priority,
                    'status': status,
                    'filed_at': x[8],
                    'maps_link': x[13] if len(x) > 13 else '',
                    'media_type': x[15] if len(x) > 15 else '',
                    'media_url': x[16] if len(x) > 16 else ''
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
        ready_certs = []
        for y in ce:
            if isinstance(y, dict):
                cstatus = y.get('status', 'pending')
                cert = {
                    'id': y.get('id', ''),
                    'type': y.get('type', ''),
                    'name': y.get('name', ''),
                    'father': y.get('father', ''),
                    'phone': y.get('phone', ''),
                    'purpose': y.get('purpose', ''),
                    'status': cstatus,
                    'filed_at': y.get('filed_at', '')
                }
            else:
                cstatus = y[6] if len(y) > 6 else 'pending'
                cert = {
                    'id': y[0],
                    'type': y[1],
                    'name': y[2],
                    'father': y[3],
                    'phone': y[4],
                    'purpose': y[5],
                    'status': cstatus,
                    'filed_at': y[7]
                }
            if cstatus == 'pending':
                pending_certs.append(cert)
            elif cstatus == 'processing':
                processing_certs.append(cert)
            elif cstatus in ('ready', 'collected'):
                ready_certs.append(cert)
        return render_template_string(DASHBOARD_TEMPLATE,
            village=village, username=username, photo=photo,
            complaints=filtered_complaints,
            pending_count=len(pending_complaints),
            review_count=len(in_review_complaints),
            progress_count=len(in_progress_complaints),
            resolved_count=len(resolved_complaints),
            high_count=len(high_priority_complaints),
            pending_certs=pending_certs,
            processing_certs=processing_certs,
            ready_certs=ready_certs,
            works=wo, announcements=an,
            filter_status=filter_status, filter_priority=filter_priority)
    except Exception as e:
        print(f"Dashboard error: {e}")
        return f"Dashboard processing error: {str(e)}"

@app.route("/update_complaint", methods=["POST"])
def update_complaint_route():
    if 'sarpanch_username' not in session:
        return redirect(url_for('login'))
    ticket_id = request.form.get("ticket_id")
    status = request.form.get("status")
    notes = request.form.get("notes", "")
    conn, db_type = get_db()
    cur = conn.cursor()
    p = get_placeholder(db_type)
    u = "updated" if db_type == "pg" else "updated_at"
    cur.execute(f"UPDATE complaints SET status = {p}, notes = {p}, {u} = {p} WHERE id = {p}", (status, notes, now_str(), ticket_id))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route("/update_certificate", methods=["POST"])
def update_certificate_route():
    if 'sarpanch_username' not in session:
        return redirect(url_for('login'))
    ticket_id = request.form.get("ticket_id")
    status = request.form.get("status")
    notes = request.form.get("notes", "")
    conn, db_type = get_db()
    cur = conn.cursor()
    p = get_placeholder(db_type)
    u = "updated" if db_type == "pg" else "updated_at"
    cur.execute(f"UPDATE certificates SET status = {p}, notes = {p}, {u} = {p} WHERE id = {p}", (status, notes, now_str(), ticket_id))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route("/add_work", methods=["POST"])
def add_work_route():
    if 'sarpanch_username' not in session:
        return redirect(url_for('login'))
    title = request.form.get("title")
    if title:
        insert_work(title)
    return redirect(url_for('dashboard'))

@app.route("/update_work", methods=["POST"])
def update_work_route():
    if 'sarpanch_username' not in session:
        return redirect(url_for('login'))
    work_id = request.form.get("work_id")
    status = request.form.get("status")
    conn, db_type = get_db()
    cur = conn.cursor()
    p = get_placeholder(db_type)
    u = "updated" if db_type == "pg" else "updated_at"
    cur.execute(f"UPDATE works SET status = {p}, {u} = {p} WHERE id = {p}", (status, now_str(), work_id))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route("/add_announcement", methods=["POST"])
def add_announcement_route():
    if 'sarpanch_username' not in session:
        return redirect(url_for('login'))
    title = request.form.get("title")
    body = request.form.get("body")
    if title and body:
        insert_announcement(title, body)
    return redirect(url_for('dashboard'))

@app.route("/send_reply", methods=["POST"])
def send_reply_route():
    if 'sarpanch_username' not in session:
        return redirect(url_for('login'))
    ticket_id = request.form.get("ticket_id")
    reply_message = request.form.get("reply_message")
    rec = get_record(ticket_id)
    if rec and reply_message:
        phone = rec.get("phone")
        formatted_message = f"💬 *Message from Sarpanch regarding Ticket {ticket_id}:*\n\n{reply_message}"
        send_whatsapp_message(phone, formatted_message)
    return redirect(url_for('dashboard'))

# ── TEMPLATES ─────────────────────────────────────────────────
LOGIN_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<title>Sarpanch Portal Login</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body { font-family: 'Segoe UI', system-ui, sans-serif; background: #f0f2f5; display: flex; justify-content: center; align-items: center; height: 100vh; margin:0; }
.card { background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.08); width: 100%; max-width: 400px; text-align: center; box-sizing: border-box; }
h2 { color: #1a73e8; margin-bottom: 24px; }
input { width: 100%; padding: 12px; margin: 8px 0; border: 1px solid #ddd; border-radius: 6px; box-sizing: border-box; font-size: 15px; }
button { width: 100%; padding: 12px; background: #1a73e8; color: white; border: none; border-radius: 6px; font-size: 16px; cursor: pointer; font-weight: bold; margin-top: 16px; }
button:hover { background: #1557b0; }
.error { color: #d93025; background: #fce8e6; padding: 10px; border-radius: 4px; margin-bottom: 16px; font-size: 14px; }
</style>
</head>
<body>
<div class="card">
<h2>Sarpanch Dashboard Login</h2>
{% if error %}<div class="error">{{ error }}</div>{% endif %}
<form method="POST">
<input type="text" name="username" placeholder="Username" required autofocus>
<input type="password" name="password" placeholder="Password" required>
<button type="submit">Sign In</button>
</form>
</div>
</body>
</html>"""

PROFILE_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<title>Sarpanch Profile</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body { font-family: 'Segoe UI', sans-serif; background: #f0f2f5; margin:0; padding:20px; }
.container { max-width: 600px; margin: 40px auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
.avatar-section { text-align: center; margin-bottom: 30px; position: relative; }
.avatar { width: 130px; height: 130px; border-radius: 50%; object-fit: cover; border: 4px solid #1a73e8; background: #eee; }
input[type=text], input[type=email], input[type=file] { width:100%; padding:10px; margin:10px 0; border:1px solid #ccc; border-radius:6px; box-sizing: border-box; }
button { background: #1a73e8; color:white; border:none; padding:12px 20px; border-radius:6px; cursor:pointer; font-weight:bold; }
.back-link { display: inline-block; margin-top: 15px; color: #1a73e8; text-decoration: none; font-weight: bold; }
</style>
</head>
<body>
<div class="container">
<h2>Edit Sarpanch Profile</h2>
<form method="POST" enctype="multipart/form-data">
<div class="avatar-section">
<img src="{{ user.get('photo') or '/static/uploads/default.png' }}" class="avatar" alt="Profile">
<br><br>
<label>Change Profile Photo:</label>
<input type="file" name="photo" accept="image/*">
</div>
<label>Phone Number:</label>
<input type="text" name="phone" value="{{ user.get('phone','') }}">
<label>Email Address:</label>
<input type="email" name="email" value="{{ user.get('email','') }}">
<button type="submit">Save Changes</button>
</form>
<a href="/dashboard" class="back-link">← Back to Dashboard</a>
</div>
</body>
</html>"""

DASHBOARD_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<title>{{ village }} Dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body { font-family: 'Segoe UI', system-ui, sans-serif; background: #f4f6f9; margin: 0; display: flex; }
.sidebar { width: 260px; background: #1e293b; color: white; height: 100vh; position: fixed; padding: 20px; box-sizing: border-box; display: flex; flex-direction: column; }
.sidebar h2 { margin-top: 0; color: #38bdf8; font-size: 22px; border-bottom: 1px solid #334155; padding-bottom: 15px; }
.profile-box { display: flex; align-items: center; gap: 12px; margin: 20px 0; padding-bottom: 20px; border-bottom: 1px solid #334155; }
.profile-box img { width: 50px; height: 50px; border-radius: 50%; object-fit: cover; background: #475569; }
.profile-box div h4 { margin: 0; font-size: 15px; }
.profile-box div p { margin: 0; font-size: 12px; color: #94a3b8; }
.sidebar a { color: #cbd5e1; text-decoration: none; padding: 12px; border-radius: 6px; display: block; margin: 4px 0; font-weight: 500; }
.sidebar a:hover, .sidebar a.active { background: #334155; color: white; }
.main-content { margin-left: 260px; padding: 40px; width: calc(100% - 260px); box-sizing: border-box; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }
.header h1 { margin: 0; color: #0f172a; font-size: 28px; }
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 20px; margin-bottom: 40px; }
.stat-card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.03); border-left: 5px solid #cbd5e1; }
.stat-card h3 { margin: 0; color: #64748b; font-size: 14px; text-transform: uppercase; }
.stat-card p { margin: 10px 0 0 0; font-size: 28px; font-weight: bold; color: #1e293b; }
.stat-card.pending { border-left-color: #f59e0b; }
.stat-card.review { border-left-color: #3b82f6; }
.stat-card.progress { border-left-color: #8b5cf6; }
.stat-card.resolved { border-left-color: #10b981; }
.stat-card.high { border-left-color: #ef4444; }
.section-card { background: white; padding: 25px; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.04); margin-bottom: 40px; }
.section-card h2 { margin-top: 0; color: #1e293b; font-size: 20px; margin-bottom: 20px; border-bottom: 2px solid #f1f5f9; padding-bottom: 10px; }
.filter-bar { display: flex; gap: 15px; margin-bottom: 20px; align-items: center; background: #f8fafc; padding: 12px; border-radius: 8px; }
.filter-bar select { padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; background: white; font-size: 14px; }
.filter-bar button { padding: 8px 16px; background: #1e293b; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 500; }
table { width: 100%; border-collapse: collapse; text-align: left; }
th { background: #f8fafc; padding: 14px; color: #475569; font-weight: 600; border-bottom: 2px solid #e2e8f0; }
td { padding: 14px; border-bottom: 1px solid #f1f5f9; color: #334155; font-size: 15px; vertical-align: top; }
tr:hover { background: #f8fafc; }
.badge { padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; text-transform: uppercase; display: inline-block; }
.badge.pending { background: #fef3c7; color: #d97706; }
.badge.in_review { background: #dbeafe; color: #2563eb; }
.badge.in_progress { background: #ede9fe; color: #7c3aed; }
.badge.resolved { background: #d1fae5; color: #059669; }
.badge.rejected { background: #fee2e2; color: #dc2626; }
.badge.high { background: #fee2e2; color: #dc2626; }
.badge.medium { background: #fef3c7; color: #d97706; }
.badge.low { background: #e2e8f0; color: #475569; }
.action-box { display: flex; flex-direction: column; gap: 8px; }
.action-box select, .action-box textarea { width: 100%; padding: 6px; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 13px; box-sizing: border-box; }
.action-box button { padding: 6px 12px; background: #10b981; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: 600; font-size: 13px; }
.reply-box { width: 100%; padding: 8px; border: 1px solid #cbd5e1; border-radius: 6px; box-sizing: border-box; margin-bottom: 8px; font-family: inherit; resize: vertical; }
.btn-reply { padding: 6px 12px; background: #3b82f6; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: 600; font-size: 13px; }
.form-inline { display: flex; gap: 10px; margin-bottom: 20px; }
.form-inline input, .form-inline textarea { padding: 10px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 14px; }
.form-inline button { padding: 10px 20px; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; }
.audio-player { width: 100%; max-width: 240px; margin-top: 5px; display: block; }
</style>
</head>
<body>
<div class="sidebar">
<h2>GP Management</h2>
<div class="profile-box">
<img src="{{ photo if photo else '/static/uploads/default.png' }}" alt="Sarpanch">
<div>
<h4>{{ username }}</h4>
<p>{{ village }}</p>
</div>
</div>
<a href="/dashboard" class="active">📋 Complaints</a>
<a href="/profile">⚙️ Edit Profile</a>
<a href="/logout" style="margin-top: auto; color: #f87171;">🚪 Logout</a>
</div>
<div class="main-content">
<div class="header">
<h1>{{ village }} Portal Dashboard</h1>
</div>
<div class="stats-grid">
<div class="stat-card pending"><h3>Pending</h3><p>{{ pending_count }}</p></div>
<div class="stat-card review"><h3>In Review</h3><p>{{ review_count }}</p></div>
<div class="stat-card progress"><h3>In Progress</h3><p>{{ progress_count }}</p></div>
<div class="stat-card resolved"><h3>Resolved</h3><p>{{ resolved_count }}</p></div>
<div class="stat-card high"><h3>Urgent/High</h3><p>{{ high_count }}</p></div>
</div>
<div class="section-card">
<h2>Citizen Complaints Loop</h2>
<div class="filter-bar">
<form method="GET" action="/dashboard" style="display:flex; gap:15px; align-items:center; width:100%;">
<label>Status:</label>
<select name="filter_status">
<option value="ALL" {% if filter_status == 'ALL' %}selected{% endif %}>All Statuses</option>
<option value="pending" {% if filter_status == 'pending' %}selected{% endif %}>Pending</option>
<option value="in_review" {% if filter_status == 'in_review' %}selected{% endif %}>In Review</option>
<option value="in_progress" {% if filter_status == 'in_progress' %}selected{% endif %}>In Progress</option>
<option value="resolved" {% if filter_status == 'resolved' %}selected{% endif %}>Resolved</option>
<option value="rejected" {% if filter_status == 'rejected' %}selected{% endif %}>Rejected</option>
</select>
<label>Priority:</label>
<select name="filter_priority">
<option value="ALL" {% if filter_priority == 'ALL' %}selected{% endif %}>All Priorities</option>
<option value="low" {% if filter_priority == 'low' %}selected{% endif %}>Low</option>
<option value="medium" {% if filter_priority == 'medium' %}selected{% endif %}>Medium</option>
<option value="high" {% if filter_priority == 'high' %}selected{% endif %}>High</option>
</select>
<button type="submit">Apply Filters</button>
<a href="/dashboard" style="text-decoration:none; color:#64748b; font-size:14px;">Clear</a>
</form>
</div>
<div style="overflow-x:auto;">
<table>
<thead>
<tr>
<th>ID / Date</th>
<th>Citizen & Contact</th>
<th>Category & Problem Statement</th>
<th>Geospatial Location</th>
<th>Priority</th>
<th>Status</th>
<th>Action Control Panel</th>
</tr>
</thead>
<tbody>
{% for complaint in complaints %}
<tr>
<td>
<strong>{{ complaint.id }}</strong><br>
<span style="font-size:12px; color:#64748b;">{{ complaint.filed_at }}</span>
</td>
<td>
<strong>{{ complaint.name }}</strong><br>
<span style="font-size:13px; color:#475569;">{{ complaint.phone }}</span>
</td>
<td>
<span style="font-weight:600; color:#0f172a;">{{ complaint.category }}</span><br>
<p style="margin:6px 0; color:#334155; font-size:14px; max-width:300px;">{{ complaint.description }}</p>
{% if complaint.media_type == 'voice' and complaint.media_url %}
<audio controls class="audio-player">
<source src="{{ complaint.media_url }}" type="audio/ogg">
Your browser does not support audio playback.
</audio>
{% endif %}
</td>
<td>
{{ complaint.location }}
{% if complaint.maps_link %}
<br><a href="{{ complaint.maps_link }}" target="_blank" style="color:#2563eb; font-size:13px; font-weight:500;">🗺️ Open Live Map</a>
{% endif %}
</td>
<td><span class="badge {{ complaint.priority }}">{{ complaint.priority }}</span></td>
<td><span class="badge {{ complaint.status }}">{{ complaint.status }}</span></td>
<td>
<div class="action-box">
<form method="POST" action="/update_complaint">
<input type="hidden" name="ticket_id" value="{{ complaint.id }}">
<select name="status">
<option value="pending" {% if complaint.status=='pending' %}selected{% endif %}>Pending</option>
<option value="in_review" {% if complaint.status=='in_review' %}selected{% endif %}>In Review</option>
<option value="in_progress" {% if complaint.status=='in_progress' %}selected{% endif %}>In Progress</option>
<option value="resolved" {% if complaint.status=='resolved' %}selected{% endif %}>Resolved</option>
<option value="rejected" {% if complaint.status=='rejected' %}selected{% endif %}>Rejected</option>
</select>
<button type="submit" style="margin-top:4px;">Update Status</button>
</form>
<hr style="border:0; border-top:1px solid #f1f5f9; margin:4px 0;">
<form method="POST" action="/send_reply">
<input type="hidden" name="ticket_id" value="{{ complaint.id }}">
<textarea name="reply_message" class="reply-box" rows="2" placeholder="Reply via WhatsApp..."></textarea>
<button type="submit" class="btn-reply">Send Reply</button>
</form>
</div>
</td>
</tr>
{% else %}
<tr><td colspan="7" style="text-align:center; color:#94a3b8; padding:30px;">No complaints match the current filter selection.</td></tr>
{% endfor %}
</tbody>
</table>
</div>
</div>
<div class="section-card">
<h2>Official Documentation Requests (Certificates)</h2>
<div style="overflow-x:auto;">
<table>
<thead>
<tr>
<th>ID / Date</th>
<th>Applicant</th>
<th>Certificate Type</th>
<th>Purpose Details</th>
<th>Status</th>
<th>Control Action</th>
</tr>
</thead>
<tbody>
{% for cert in pending_certs + processing_certs + ready_certs %}
<tr>
<td><strong>{{ cert.id }}</strong><br><span style="font-size:12px; color:#64748b;">{{ cert.filed_at }}</span></td>
<td><strong>{{ cert.name }}</strong><br><span style="font-size:13px; color:#64748b;">S/o or W/o: {{ cert.father }}</span><br><span style="font-size:13px;">{{ cert.phone }}</span></td>
<td><span style="font-weight:600;">{{ cert.type }}</span></td>
<td><p style="margin:0; font-size:14px; color:#475569;">{{ cert.purpose }}</p></td>
<td><span class="badge {{ cert.status }}">{{ cert.status }}</span></td>
<td>
<form method="POST" action="/update_certificate" class="action-box">
<input type="hidden" name="ticket_id" value="{{ cert.id }}">
<select name="status">
<option value="pending" {% if cert.status=='pending' %}selected{% endif %}>Pending</option>
<option value="processing" {% if cert.status=='processing' %}selected{% endif %}>Processing</option>
<option value="ready" {% if cert.status=='ready' %}selected{% endif %}>Ready to Collect</option>
<option value="collected" {% if cert.status=='collected' %}selected{% endif %}>Collected / Closed</option>
</select>
<button type="submit">Update</button>
</form>
</td>
</tr>
{% endfor %}
</tbody>
</table>
</div>
</div>
<div style="display:grid; grid-template-columns: 1fr 1fr; gap:30px;">
<div class="section-card">
<h2>Public Announcements Broadcaster</h2>
<form method="POST" action="/add_announcement" style="display:flex; flex-direction:column; gap:10px; margin-bottom:20px;">
<input type="text" name="title" placeholder="Announcement Title (e.g., Pulse Polio Drive)" required>
<textarea name="body" rows="3" placeholder="Write full details here..." required style="padding:10px; border:1px solid #cbd5e1; border-radius:6px; font-family:inherit;"></textarea>
<button type="submit" style="padding:10px; background:#3b82f6; color:white; border:none; border-radius:6px; font-weight:bold; cursor:pointer;">Publish Now</button>
</form>
<h3>Recent Broadcasts</h3>
<ul style="padding-left:20px; color:#334155;">
{% for a in announcements %}
<li style="margin-bottom:12px;"><strong>{{ a.title }}</strong> ({{ a.date }})<br><span style="font-size:14px; color:#64748b;">{{ a.body }}</span></li>
{% endfor %}
</ul>
</div>
<div class="section-card">
<h2>Development Infrastructure Works Log</h2>
<form method="POST" action="/add_work" class="form-inline">
<input type="text" name="title" placeholder="New Work Item (e.g., CC Road Construction)" required style="flex:1;">
<button type="submit">Log Project</button>
</form>
<h3>Infrastructure Tracker</h3>
<table>
<thead>
<tr>
<th>Project Scope</th>
<th>Current Status</th>
<th>Actions</th>
</tr>
</thead>
<tbody>
{% for w in works %}
<tr>
<td><strong>{{ w.title }}</strong></td>
<td><span class="badge {{ w.status }}">{{ w.status }}</span></td>
<td>
<form method="POST" action="/update_work" style="display:flex; gap:6px;">
<input type="hidden" name="work_id" value="{{ w.id }}">
<select name="status" style="padding:4px; font-size:12px;">
<option value="pending" {% if w.status=='pending' %}selected{% endif %}>Pending</option>
<option value="in_progress" {% if w.status=='in_progress' %}selected{% endif %}>In Progress</option>
<option value="resolved" {% if w.status=='resolved' %}selected{% endif %}>Resolved</option>
</select>
<button type="submit" style="padding:4px 8px; font-size:12px; background:#1e293b; color:white; border:none; border-radius:4px; cursor:pointer;">Set</button>
</form>
</td>
</tr>
{% endfor %}
</tbody>
</table>
</div>
</div>
</div>
</body>
</html>"""

# ── RUN ──────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

```