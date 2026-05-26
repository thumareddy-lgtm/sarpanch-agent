import os, uuid, sqlite3, requests, re, hashlib, json, base64
import cloudinary
import cloudinary.uploader
from datetime import datetime
from flask import Flask, request, render_template, redirect, session, url_for
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

# ── Cloudinary Config (Permanent Voice Storage) ──────────────
CLOUD_NAME    = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
CLOUD_API_KEY = os.environ.get("CLOUDINARY_API_KEY", "")
CLOUD_SECRET  = os.environ.get("CLOUDINARY_API_SECRET", "")

if CLOUD_NAME and CLOUD_API_KEY and CLOUD_SECRET:
    cloudinary.config(
        cloud_name = CLOUD_NAME,
        api_key    = CLOUD_API_KEY,
        api_secret = CLOUD_SECRET,
        secure     = True
    )
    print("✅ Cloudinary configured for permanent voice storage")
else:
    print("⚠️  Cloudinary not configured — voices will use local storage (temporary on Render)")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "sarpanch_secret_2024")
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

def get_whatsapp_session(sender):
    try:
        conn, db_type = get_db()
        cur = conn.cursor()
        p = get_placeholder(db_type)
        cur.execute(f"SELECT session_data FROM whatsapp_sessions WHERE phone = {p}", (sender,))
        row = cur.fetchone()
        conn.close()
        if row:
            # Extract session data string with absolute robustness
            val = None
            try:
                val = row['session_data']
            except:
                try:
                    val = row.get('session_data')
                except:
                    val = row[0]
            if val:
                return json.loads(val)
    except Exception as e:
        print(f"Error fetching session: {e}")
    return {"state": "idle", "lang": "en"}


def save_whatsapp_session(sender, session_data):
    try:
        conn, db_type = get_db()
        cur = conn.cursor()
        p = get_placeholder(db_type)
        if db_type == "pg":
            cur.execute("""
                INSERT INTO whatsapp_sessions (phone, session_data) VALUES (%s, %s)
                ON CONFLICT (phone) DO UPDATE SET session_data = EXCLUDED.session_data
            """, (sender, json.dumps(session_data)))
        else:
            cur.execute("""
                INSERT INTO whatsapp_sessions (phone, session_data) VALUES (?, ?)
                ON CONFLICT(phone) DO UPDATE SET session_data = excluded.session_data
            """, (sender, json.dumps(session_data)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error saving session: {e}")


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
            purpose TEXT, status TEXT DEFAULT 'pending', filed_at TEXT, {u} TEXT, notes TEXT DEFAULT '', village TEXT DEFAULT ''
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
   
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS whatsapp_sessions (
            phone TEXT PRIMARY KEY,
            session_data TEXT
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
    
    conn2, db_type2 = get_db()
    cur2 = conn2.cursor()
    try:
        if db_type2 == "pg":
            cur2.execute("ALTER TABLE complaints ADD COLUMN IF NOT EXISTS voice_data TEXT;")
            cur2.execute("ALTER TABLE certificates ADD COLUMN IF NOT EXISTS village TEXT DEFAULT '';")
        else:
            # Check complaints
            cur2.execute("PRAGMA table_info(complaints)")
            cols = [row[1] if isinstance(row, tuple) else row['name'] for row in cur2.fetchall()]
            if 'voice_data' not in cols:
                cur2.execute("ALTER TABLE complaints ADD COLUMN voice_data TEXT DEFAULT ''")
            
            # Check certificates
            cur2.execute("PRAGMA table_info(certificates)")
            cert_cols = [row[1] if isinstance(row, tuple) else row['name'] for row in cur2.fetchall()]
            if 'village' not in cert_cols:
                cur2.execute("ALTER TABLE certificates ADD COLUMN village TEXT DEFAULT ''")
        conn2.commit()
        print("✅ DB migrations ready")
    except Exception as e:
        print(f"⚠️ DB migrations error: {e}")
    finally:
        conn2.close()
    print(f"✅ Database ready ({db_type})")

init_db()


def insert_complaint(c):
    conn, db_type = get_db()
    cur = conn.cursor()
    p = get_placeholder(db_type)
    u = "updated" if db_type == "pg" else "updated_at"
    cur.execute(f"""
        INSERT INTO complaints (id,name,phone,category,description,location,priority,status,filed_at,{u},notes,
        location_lat,location_lng,location_address,maps_link,media_type,media_url,village,voice_data)
        VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p})
    """,
        (c["id"],c["name"],c["phone"],c["category"],c["desc"],c.get("location",""),c["priority"],"pending",c["filed_at"],c["filed_at"],"",
         c.get("location_lat"),c.get("location_lng"),c.get("location_address",""),c.get("maps_link",""),
         c.get("media_type",""),c.get("media_url",""), c.get("village",""), c.get("voice_data","")))
    conn.commit()
    conn.close()

def insert_certificate(c):
    conn, db_type = get_db()
    cur = conn.cursor()
    p = get_placeholder(db_type)
    u = "updated" if db_type == "pg" else "updated_at"
    cur.execute(f"""
        INSERT INTO certificates (id,type,name,father,phone,purpose,status,filed_at,{u},notes,village)
        VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p})
    """,
        (c["id"],c["type"],c["name"],c["father"],c["phone"],c["purpose"],"pending",c["filed_at"],c["filed_at"],"",c.get("village","")))
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

# ── OGG → MP3 CONVERSION (for universal mobile support) ─────
def convert_ogg_to_mp3(ogg_bytes):
    """
    Convert OGG/Opus bytes to MP3 using ffmpeg.
    MP3 plays on ALL devices including iPhone/iOS Safari.
    Returns MP3 bytes, or None if ffmpeg not available.
    """
    import subprocess, tempfile
    try:
        # Write OGG to a temp file
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as f:
            f.write(ogg_bytes)
            ogg_path = f.name
        mp3_path = ogg_path.replace('.ogg', '.mp3')
        # Run ffmpeg conversion
        result = subprocess.run(
            ['ffmpeg', '-y', '-i', ogg_path,
             '-codec:a', 'libmp3lame', '-qscale:a', '4',
             mp3_path],
            capture_output=True, timeout=30
        )
        if result.returncode == 0 and os.path.exists(mp3_path):
            with open(mp3_path, 'rb') as f:
                mp3_bytes = f.read()
            os.unlink(ogg_path)
            os.unlink(mp3_path)
            print(f"\u2705 OGG converted to MP3 ({len(mp3_bytes)} bytes)")
            return mp3_bytes
        else:
            print(f"\u26a0\ufe0f  ffmpeg failed: {result.stderr.decode()[:200]}")
            if os.path.exists(ogg_path): os.unlink(ogg_path)
            if os.path.exists(mp3_path): os.unlink(mp3_path)
            return None
    except FileNotFoundError:
        print("\u26a0\ufe0f  ffmpeg not found on this server")
        return None
    except Exception as e:
        print(f"\u26a0\ufe0f  OGG→MP3 conversion error: {e}")
        return None

# ── VOICE PERMANENT STORAGE FUNCTION ─────────────────────────
def download_voice_permanently(voice_id, complaint_id):
    """
    Download voice from WhatsApp.
    Returns (media_url, base64_audio_data) tuple.
    """
    if not META_TOKEN:
        print("❌ No META_TOKEN for voice download")
        return None, None

    headers = {"Authorization": f"Bearer {META_TOKEN}"}

    try:
        media_resp = requests.get(
            f"https://graph.facebook.com/v19.0/{voice_id}",
            headers=headers, timeout=10
        )
        if media_resp.status_code != 200:
            print(f"❌ Failed to get media info: {media_resp.status_code}")
            return None, None

        download_url = media_resp.json().get("url")
        if not download_url:
            print("❌ No download URL in response")
            return None, None

        audio_resp = requests.get(download_url, headers=headers, timeout=30)
        if audio_resp.status_code != 200:
            print(f"❌ Failed to download audio: {audio_resp.status_code}")
            return None, None

        audio_bytes = audio_resp.content

        # ── Try OGG → MP3 conversion for iPhone/mobile support ──
        mp3_bytes = convert_ogg_to_mp3(audio_bytes)
        if mp3_bytes:
            store_bytes  = mp3_bytes
            mime_prefix  = "mp3:"     # plays on ALL devices including iPhone
        else:
            store_bytes  = audio_bytes
            mime_prefix  = "ogg:"     # fallback: works on desktop/Android only

        if CLOUD_NAME and CLOUD_API_KEY and CLOUD_SECRET:
            try:
                import io
                result = cloudinary.uploader.upload(
                    io.BytesIO(store_bytes),
                    resource_type="video",
                    public_id=f"sarpanch_voices/{complaint_id}_{int(datetime.now().timestamp())}",
                    overwrite=True,
                    format="mp3"
                )
                cloud_url = result.get("secure_url", "")
                if cloud_url:
                    print(f"\u2705 Voice uploaded to Cloudinary: {cloud_url}")
                    return cloud_url, None
            except Exception as e:
                print(f"⚠️  Cloudinary upload failed: {e}, falling back to DB storage")

        # Store in DB with mime prefix so serve route knows format
        audio_b64 = mime_prefix + base64.b64encode(store_bytes).decode("utf-8")
        db_url = f"/voice/{complaint_id}"
        print(f"✅ Voice stored in database permanently for complaint {complaint_id}")
        return db_url, audio_b64

    except Exception as e:
        print(f"❌ Voice download error: {e}")
        return None, None

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

def get_all_registered_villages():
    try:
        conn, db_type = get_db()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT village_name FROM sarpanch_users")
        rows = cur.fetchall()
        conn.close()
        villages = []
        for r in rows:
            v = r['village_name'] if isinstance(r, dict) else r[0]
            if v:
                villages.append(v.strip().lower())
        return villages
    except Exception as e:
        print(f"Error fetching registered villages: {e}")
        return ['kolukonda', 'keesara', 'ghatkesar', 'pocharam', 'jangaon', 'hyderabad'] # fallback

def detect_village_from_text(text):
    if not text:
        return None
    import difflib
    registered_villages = get_all_registered_villages()
    text_lower = text.lower().strip()
    
    # 1. Direct substring match (e.g. if text is "i live in kolukonda village")
    for village in registered_villages:
        if village in text_lower:
            return village.title()
            
    # 2. Split words and find fuzzy match (handles mistypes like "kolkonda" or "kollukonda")
    words = re.findall(r'\b\w+\b', text_lower)
    for word in words:
        matches = difflib.get_close_matches(word, registered_villages, n=1, cutoff=0.7)
        if matches:
            return matches[0].title()
            
    # 3. Try to fuzzy match the entire text (in case they typed just the village name with a typo)
    matches = difflib.get_close_matches(text_lower, registered_villages, n=1, cutoff=0.6)
    if matches:
        return matches[0].title()
        
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
WELCOME_MENU = (
    "Welcome to Kolukonda Gram Panchayat Portal! 🙏\n"
    "Sarpanch: Kothi Sravanthi Praveen\n"
    "[Telugu: కొలుకొండ గ్రామ పంచాయతీకి స్వాగతం! సర్పంచ్: కోతి స్రవంతి ప్రవీణ్]\n\n"
    "1. Register Complaint [Telugu: ఫిర్యాదు నమోదు చేయండి]\n"
    "2. Request Certificate [Telugu: సర్టిఫికేట్ అభ్యర్థించండి]\n"
    "3. Track Status [Telugu: ఫిర్యాదు స్థితి తెలుసుకోండి]\n"
    "4. Government Schemes [Telugu: ప్రభుత్వ పథకాలు]\n"
    "5. Development Works [Telugu: అభివృద్ధి పనులు]\n"
    "6. Announcements [Telugu: ప్రకటనలు]\n"
    "7. Office Info [Telugu: కార్యాలయ సమాచారం]"
)

MENU_EN = WELCOME_MENU
MENU_TE = WELCOME_MENU

COMPLAINT_CATS = {
    "1": "Road / Pothole [రోడ్లు / గుంతలు]",
    "2": "Water Supply [నీటి సరఫరా]",
    "3": "Electricity [విద్యుత్ సమస్య]",
    "4": "Drainage [డ్రైనేజీ]",
    "5": "Ration Shop [రేషన్ షాప్]",
    "6": "Land Dispute [భూ వివాదాలు]",
    "7": "Other [ఇతరములు]"
}

CERT_TYPES = {
    "1": "Income Certificate [ఆదాయ ధృవీకరణ పత్రం]",
    "2": "Caste Certificate [కుల ధృవీకరణ పత్రం]",
    "3": "Residence Certificate [నివాస ధృవీకరణ పత్రం]",
    "4": "Birth Certificate [జనన ధృవీకరణ పత్రం]",
    "5": "Death Certificate [మరణ ధృవీకరణ పత్రం]",
    "6": "Agriculture Land Certificate [వ్యవసాయ భూమి ధృవీకరణ పత్రం]"
}

STATUS_MAP = {"pending":"Pending","in_review":"In Review","in_progress":"In Progress","resolved":"Resolved","rejected":"Rejected","ready":"Ready to Collect","processing":"Processing"}
PRI_MAP = {"low":"Low","medium":"Medium","high":"High"}

def get_menu(ctx):
    return WELCOME_MENU

# ── BOT REPLY FUNCTION ───────────────────────────────────────
def bot_reply(user_msg, ctx, media_info=None):
    msg = user_msg.strip() if user_msg else ""
    ml = msg.lower()
    state = ctx.get("state", "idle")
    lang = ctx.get("lang", "en")
   
    print(f"🔍 DEBUG: state={state}, msg={msg[:30] if msg else 'empty'}, lang={lang}")
   
    if ml in ("menu", "home", "back", "hi", "hello", "start", "help", "telugu", "english"):
        return WELCOME_MENU, {"state": "idle", "lang": lang}
   
    if media_info and media_info.get("type") == "voice":
        ctx["media_type"] = "voice"
        ctx["temp_audio_id"] = media_info.get("audio_id", "")
        ctx["state"] = "waiting_for_location"
        return "🎤 *Voice received [వాయిస్ మెసేజ్ అందుకుంది]*!\n\n📍 Please share your location (📎 → Location) or type your village name [దయచేసి మీ లొకేషన్ షేర్ చేయండి లేదా మీ గ్రామం పేరు టైప్ చేయండి]:", ctx
   
    if state == "idle":
        if ml == "1":
            ctx["state"] = "c_name"
            return "📝 *Register Complaint [ఫిర్యాదు నమోదు చేయండి]*\n\nPlease enter your full name [దయచేసి మీ పూర్తి పేరు టైప్ చేయండి]:", ctx
        elif ml == "2":
            cats = "\n".join(f"{k}. {v}" for k, v in CERT_TYPES.items())
            ctx["state"] = "cert_type"
            return f"📋 *Select Certificate Type [ధృవీకరణ పత్రం రకం ఎంచుకోండి]*:\n\n{cats}", ctx
        elif ml == "3":
            ctx["state"] = "track_id"
            return "🔍 *Track Status [ఫిర్యాదు స్థితి తెలుసుకోండి]*\n\nPlease enter your Reference ID (e.g., CMP-XXXXX or CERT-XXXXX) [దయచేసి మీ రిఫరెన్స్ ID టైప్ చేయండి]:", ctx
        elif ml == "4":
            schemes_list = [
                "• *Mahalakshmi Scheme [మహాలక్ష్మి పథకం]*: ₹2500/month financial assistance to women [మహిళా కుటుంబ అధినేతలకు నెలకు ₹2500 ఆర్థిక సహాయం]",
                "• *Gruha Jyothi [గృహజ్యోతి]*: 200 units free electricity [అర్హులైన కుటుంబాలకు 200 యూనిట్ల ఉచిత విద్యుత్]",
                "• *Anna Bhagya [అన్నభాగ్య]*: 10kg free rice for BPL families [బీపీఎల్ కుటుంబాలకు ప్రతి వ్యక్తికి నెలకు 10 కేజీల ఉచిత బియ్యం]",
                "• *Rythu Bharosa [రైతు భరోసా]*: ₹13,500/acre annual investment support [రైతులకు ఎకరానికి ₹13,500 వార్షిక పెట్టుబడి సహాయం]",
                "• *Aarogyasri [ఆరోగ్యశ్రీ]*: Free medical up to ₹5L/year [సంవత్సరానికి ₹5 లక్షల వరకు ఉచిత వైద్యం]"
            ]
            schemes_text = "\n\n".join(schemes_list)
            return f"📋 *Government Schemes [ప్రభుత్వ పథకాలు]*:\n\n{schemes_text}\n\nType *menu* for main menu [మెనూ కోసం *menu* టైప్ చేయండి]", {"state": "idle", "lang": lang}
        elif ml == "5":
            works_list = active_works()
            if works_list:
                items = []
                for w in works_list:
                    status_te = "ప్రగతిలో ఉంది" if w.get('status') == "in_progress" else "ప్రారంభం కాలేదు"
                    items.append(f"• *{w['title']}* - {w['status'].title()} [{status_te}]")
                works_text = "\n".join(items)
            else:
                works_text = (
                    "• *CC Road Construction [సీసీ రోడ్డు నిర్మాణం]* - In Progress [ప్రగతిలో ఉంది]\n"
                    "• *Gram Panchayat Building Painting [గ్రామ పంచాయతీ భవనం రంగులు వేయడం]* - In Progress [ప్రగతిలో ఉంది]\n"
                    "• *Overhead Water Tank Repair [ఓవర్ హెడ్ వాటర్ ట్యాంక్ మరమ్మతు]* - Pending [ప్రారంభం కాలేదు]"
                )
            return (
                f"🏗️ *Development Works [అభివృద్ధి పనులు]*:\n\n"
                f"{works_text}\n\n"
                f"Type *menu* for main menu [మెనూ కోసం *menu* టైప్ చేయండి]."
            ), {"state": "idle", "lang": lang}
        elif ml == "6":
            anns = all_announcements()
            if anns:
                items = []
                for a in anns[:5]:
                    items.append(f"📢 *{a['title']}* ({a['date']})\n{a['body']}")
                anns_text = "\n\n".join(items)
            else:
                anns_text = (
                    "📢 *Gram Sabha Meeting [గ్రామ సభ సమావేశం]* (2026-05-20)\n"
                    "All citizens are requested to attend the Gram Sabha meeting on 25th May at 10 AM at GP Office.\n"
                    "[గ్రామస్తులందరూ మే 25న ఉదయం 10 గంటలకు గ్రామ పంచాయతీ కార్యాలయంలో జరిగే గ్రామ సభ సమావేశానికి హాజరుకావలసిందిగా ప్రార్థన.]\n\n"
                    "📢 *Drinking Water Supply Timings [త్రాగునీటి సరఫరా వేళలు]* (2026-05-18)\n"
                    "Water supply will be provided from 6 AM to 8 AM daily. Please cooperate.\n"
                    "[ప్రтиరోజూ ఉదయం 6 నుండి 8 గంటల వరకు నీటి సరఫరా చేయబడుతుంది. దయచేసి సహకరించండి.]"
                )
            return (
                f"📢 *Announcements [ప్రకటనలు]*:\n\n"
                f"{anns_text}\n\n"
                f"Type *menu* for main menu [మెనూ కోసం *menu* టైప్ చేయండి]."
            ), {"state": "idle", "lang": lang}
        elif ml == "7":
            return (
                "📞 *Office Info & Contacts [కార్యాలయ సమాచారం & సంప్రదింపులు]*:\n\n"
                "• *Sarpanch [సర్పంచ్]*: Kothi Sravanthi Praveen (+91 95001 78059)\n"
                "• *Gram Panchayat Secretary [గ్రామ పంచాయతీ కార్యదర్శి]*: Srikanth (+91 98480 22338)\n"
                "• *MRO Office (Jangaon) [MRO కార్యాలయం (జనగామ)]*: +91 94910 22334\n"
                "• *Panchayat Office Address [పంచాయతీ కార్యాలయం చిరునామా]*: Main Road, Kolukonda Village, Jangaon Mandal, Jangaon Dist, Telangana - 506167\n\n"
                "Type *menu* for main menu [మెనూ కోసం *menu* టైప్ చేయండి]."
            ), {"state": "idle", "lang": lang}
        else:
            print(f"🚫 Ignoring non-trigger message: {msg}")
            return None, ctx
   
    if state == "c_name":
        if len(msg) < 2:
            return "❌ Please enter a valid name (min 2 chars) [దయచేసి కనీసం 2 అక్షరాల సరైన పేరు టైప్ చేయండి]:", ctx
        ctx["c_name"] = msg.title()
        ctx["state"] = "c_phone"
        return f"👋 Namaskaram *{ctx['c_name']}*!\n\nEnter your 10-digit mobile number [మీ 10 అంకెల మొబైల్ నంబర్ టైప్ చేయండి]:", ctx
   
    if state == "c_phone":
        clean_num = re.sub(r"\D", "", msg)
        if len(clean_num) < 10:
            return "❌ Please enter a valid 10-digit mobile number [దయచేసి సరైన 10 అంకెల మొబైల్ నంబర్ టైప్ చేయండి]:", ctx
        ctx["c_phone"] = clean_num
        ctx["state"] = "c_cat"
        cats = "\n".join(f"{k}. {v}" for k, v in COMPLAINT_CATS.items())
        return f"📂 *Select Complaint Category [ఫిర్యాదు వర్గాన్ని ఎంచుకోండి]*:\n\n{cats}", ctx
   
    if state == "c_cat":
        if msg not in COMPLAINT_CATS:
            return "❌ Please select a number between 1 and 7 [దయచేసి 1 నుండి 7 మధ్య సంఖ్యను ఎంచుకోండి]:", ctx
        ctx["c_cat"] = COMPLAINT_CATS[msg]
        ctx["state"] = "c_desc"
        return f"📝 *Category [వర్గం]*: {ctx['c_cat']}\n\nDescribe your problem [మీ समस्याను వివరించండి]:", ctx
   
    if state == "c_desc":
        if len(msg) < 5:
            return "❌ Please provide more details (min 5 characters) [దయచేసి సమస్యను వివరంగా వివరించండి (కనీసం 5 అక్షరాలు)]:", ctx
        ctx["c_desc"] = msg
        ctx["state"] = "waiting_for_location"
        return "📍 *Location [లొకేషన్]*\n\nPlease share your location (📎 → Location) or type your village name [దయచేసి మీ లొకేషన్ షేర్ చేయండి లేదా మీ గ్రామం పేరు టైప్ చేయండి]:", ctx
   
    if state == "waiting_for_location":
        detected_village = detect_village_from_text(msg)
        if detected_village:
            ctx["village"] = detected_village
            ctx["state"] = "c_pri"
            return (
                "⚡ *How urgent? [ఎంత అత్యవసరం?]*\n\n"
                "1. Low [తక్కువ]\n"
                "2. Medium [మధ్యస్థం]\n"
                "3. High [ఎక్కువ]\n\n"
                "Please select 1, 2, or 3 [దయచేసి 1, 2, లేదా 3 టైప్ చేయండి]:"
            ), ctx
        else:
            registered = get_all_registered_villages()
            registered_list = ", ".join([v.title() for v in registered])
            return (
                f"❌ *Village not recognized [గ్రామం గుర్తించబడలేదు]*.\n\n"
                f"Please type one of our active registered villages: *{registered_list}* [దయచేసి సక్రియ గ్రామాల నుండి ఎంచుకోండి]:"
            ), ctx
   
    if state == "c_pri":
        pmap = {"1": "low", "2": "medium", "3": "high"}
        if msg not in pmap:
            return "⚡ Please reply with 1, 2, or 3 [దయచేసి 1, 2, లేదా 3 టైప్ చేయండి]:", ctx
       
        ref = new_id("CMP-")
        maps_link = ctx.get("maps_link", "")
       
        village = ctx.get("village") or ctx.get("location_text") or "Unknown"
       
        lat = ctx.get("location_lat")
        lng = ctx.get("location_lng")
       
        media_url = ""
        voice_data = ""
        if ctx.get("temp_audio_id"):
            voice_url, voice_b64 = download_voice_permanently(ctx["temp_audio_id"], ref)
            if voice_url:
                media_url = voice_url
                voice_data = voice_b64 or ""
                print(f"✅ Voice ready: {voice_url} (db_stored={bool(voice_b64)})")
       
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
            "village": village,
            "voice_data": voice_data
        }
       
        print(f"🔍 Saving complaint: {rec}")
        insert_complaint(rec)
       
        reply = (
            f"✅ *Complaint Registered [ఫిర్యాదు నమోదు చేయబడింది]*!\n\n"
            f"📋 Ticket ID: {ref}\n"
            f"👤 Name [పేరు]: {rec['name']}\n"
            f"📂 Category [వర్గం]: {rec['category']}\n"
            f"📍 Location [లొకేషన్]: {rec['location']}\n"
            f"⚡ Priority [ప్రాధాన్యత]: {PRI_MAP[rec['priority']]} [{ 'తక్కువ' if rec['priority']=='low' else 'మధ్యస్థం' if rec['priority']=='medium' else 'ఎక్కువ' }]\n"
            f"📅 Date [తేదీ]: {rec['filed_at']}"
        )
       
        if maps_link:
            reply += f"\n🗺️ Map: {maps_link}"
       
        reply += "\n\nType *menu* for main menu [మెనూ కోసం *menu* టైప్ చేయండి]"
        return reply, {"state": "idle", "lang": ctx.get("lang", "en")}
   
    if state == "cert_type":
        if msg not in CERT_TYPES:
            return "❌ Please select a number between 1 and 6 [దయచేసి 1 నుండి 6 మధ్య సంఖ్యను ఎంచుకోండి]:", ctx
        ctx["cert_type"] = CERT_TYPES[msg]
        ctx["state"] = "cert_name"
        return "📄 *Applicant Full Name [అప్లికెంట్ పూర్తి పేరు]*\n\nPlease enter applicant's full name [దయచేసి దరఖాస్తుదారుడి పూర్తి పేరు టైప్ చేయండి]:", ctx
   
    if state == "cert_name":
        if len(msg) < 2:
            return "❌ Please enter a valid name (min 2 chars) [దయచేసి సరైన పేరు టైప్ చేయండి]:", ctx
        ctx["cert_name"] = msg.title()
        ctx["state"] = "cert_father"
        return "👨 *Father's/Husband's Name [తండ్రి/భర్త పేరు]*\n\nPlease enter Father's or Husband's name [దయచేసి తండ్రి లేదా భర్త పేరు టైప్ చేయండి]:", ctx
   
    if state == "cert_father":
        if len(msg) < 2:
            return "❌ Please enter a valid name [దయచేసి సరైన పేరు టైప్ చేయండి]:", ctx
        ctx["cert_father"] = msg.title()
        ctx["state"] = "cert_phone"
        return "📱 *Mobile Number [మొబైల్ నంబర్]*\n\nPlease enter 10-digit mobile number [దయచేసి 10 అంకెల మొబైల్ నంబర్ టైప్ చేయండి]:", ctx
   
    if state == "cert_phone":
        clean_num = re.sub(r"\D", "", msg)
        if len(clean_num) < 10:
            return "❌ Please enter a valid 10-digit mobile number [దయచేసి 10 అంకెల మొబైల్ నంబర్ టైప్ చేయండి]:", ctx
        ctx["cert_phone"] = clean_num
        ctx["state"] = "cert_purpose"
        return "📝 *Purpose [ప్రయోజనం]*\n\nPlease enter the purpose of certificate (e.g. Bank Loan, College Admission) [దయచేసి ధృవీకరణ పత్రం యొక్క ప్రయోజనాన్ని టైప్ చేయండి]:", ctx
   
    if state == "cert_purpose":
        if len(msg) < 3:
            return "❌ Please enter a valid purpose [దయచేసి ప్రయోజనాన్ని టైప్ చేయండి]:", ctx
        ctx["cert_purpose"] = msg
        ctx["state"] = "cert_village"
        registered = get_all_registered_villages()
        registered_list = ", ".join([v.title() for v in registered])
        return (
            f"📍 *Village Name [గ్రామం పేరు]*\n\n"
            f"Please type your village name (choose from active: *{registered_list}*) [దయచేసి మీ గ్రామం పేరు టైప్ చేయండి]:"
        ), ctx
        
    if state == "cert_village":
        detected_village = detect_village_from_text(msg)
        if detected_village:
            ref = new_id("CERT-")
            rec = {
                "id": ref, "type": ctx["cert_type"], "name": ctx["cert_name"],
                "father": ctx["cert_father"], "phone": ctx["cert_phone"],
                "purpose": ctx["cert_purpose"], "filed_at": now_str(),
                "village": detected_village
            }
            insert_certificate(rec)
            return (
                f"✅ *Certificate Request Submitted [సర్టిఫికెట్ అభ్యర్థన నమోదు చేయబడింది]*!\n\n"
                f"📋 ID: {ref}\n"
                f"👤 Name [పేరు]: {rec['name']}\n"
                f"📄 Type [రకం]: {rec['type']}\n"
                f"📍 Village [గ్రామం]: {rec['village']}\n\n"
                f"Processing takes 5-7 days [ప్రాసెస్ చేయడానికి 5-7 రోజులు పడుతుంది].\n\n"
                f"Type *menu* for main menu [మెనూ కోసం *menu* టైప్ చేయండి]"
            ), {"state": "idle", "lang": lang}
        else:
            registered = get_all_registered_villages()
            registered_list = ", ".join([v.title() for v in registered])
            return (
                f"❌ *Village not recognized [గ్రామం గుర్తించబడలేదు]*.\n\n"
                f"Please type one of our active registered villages: *{registered_list}* [దయచేసి సక్రియ గ్రామాల నుండి ఎంచుకోండి]:"
            ), ctx
   
    if state == "track_id":
        if len(msg) < 5:
            return "❌ Please enter a valid Reference ID (e.g., CMP-XXXXX) [దయచేసి సరైన రిఫరెన్స్ ID టైప్ చేయండి]:", ctx
        ref = msg.upper().strip()
        rec = get_record(ref)
        if not rec:
            return f"❌ ID *{ref}* not found [కనుగొనబడలేదు].\n\nPlease check and try again [దయచేసి సరైన ID టైప్ చేయండి].\n\nType *menu* for main menu [మెనూ కోసం *menu* టైప్ చేయండి]", {"state": "idle", "lang": lang}
       
        st = STATUS_MAP.get(rec.get("status", ""), rec.get("status", ""))
        status_te = {
            "Pending": "పెండింగ్", "In Review": "సమీక్షలో ఉంది", "In Progress": "ప్రక్రియలో ఉంది",
            "Resolved": "పరిష్కరించబడింది", "Rejected": "తిరస్కరించబడింది", "Ready to Collect": "సేకరణకు సిద్ధంగా ఉంది",
            "Processing": "ప్రాసెసింగ్"
        }.get(st, st)
       
        if ref.startswith("CMP"):
            return (
                f"🔍 *Complaint Status [ఫిర్యాదు స్థితి]*\n\n"
                f"📋 Ticket ID: {ref}\n"
                f"👤 Name [పేరు]: {rec.get('name', '')}\n"
                f"📂 Category [వర్గం]: {rec.get('category', '')}\n"
                f"📍 Location [లొకేషన్]: {rec.get('location', '')}\n"
                f"📌 Status [స్థితి]: {st} [{status_te}]\n"
                f"📅 Filed [నమోదు]: {rec.get('filed_at', '')}\n\n"
                f"Type *menu* for main menu [మెనూ కోసం *menu* టైప్ చేయండి]"
            ), {"state": "idle", "lang": lang}
        else:
            return (
                f"🔍 *Certificate Status [సర్టిఫికెట్ స్థితి]*\n\n"
                f"📋 Request ID: {ref}\n"
                f"👤 Name [పేరు]: {rec.get('name', '')}\n"
                f"📄 Type [రకం]: {rec.get('type', '')}\n"
                f"📌 Status [స్థితి]: {st} [{status_te}]\n"
                f"📅 Filed [నమోదు]: {rec.get('filed_at', '')}\n\n"
                f"Type *menu* for main menu [మెనూ కోసం *menu* టైప్ చేయండి]"
            ), {"state": "idle", "lang": lang}
   
    return WELCOME_MENU, {"state": "idle", "lang": lang}

# ── WHATSAPP WEBHOOK ─────────────────────────────────────────
@app.route("/whatsapp", methods=["GET", "POST"])
def whatsapp_webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge", "")
        return "Invalid token", 403
   
    is_simulator = request.headers.get("X-Simulator") == "true"
    reply = None
    
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
       
        session_data = get_whatsapp_session(sender)
       
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
            gps_village = detect_village_from_coords(lat, lng) or name or ""
            detected_village = "Unknown"
            if gps_village:
                fuzzy = detect_village_from_text(gps_village)
                detected_village = fuzzy or gps_village.title()
            print(f"📍 Location from {sender}: {detected_village}")
            session_data["location_lat"] = lat
            session_data["location_lng"] = lng
            session_data["location_address"] = address or name
            session_data["maps_link"] = maps_link
            session_data["village"] = detected_village
            if session_data.get("state") == "waiting_for_location":
                session_data["state"] = "c_pri"
                reply = (
                    f"📍 *Location Received [లొకేషన్ అందుకుంది]*!\n"
                    f"Village [గ్రామం]: *{detected_village}*\n\n"
                    f"⚡ *How urgent? [ఎంత అత్యవసరం?]*\n"
                    f"1. Low [తక్కువ]\n"
                    f"2. Medium [మధ్యస్థం]\n"
                    f"3. High [ఎక్కువ]\n\n"
                    f"Please select 1, 2, or 3 [దయచేసి 1, 2, లేదా 3 టైప్ చేయండి]:"
                )
                send_whatsapp_message(sender, reply)
            else:
                reply = (
                    f"📍 *Location Received [లొకేషన్ అందుకుంది]*!\n"
                    f"Village [గ్రామం]: *{detected_village}*\n\n"
                    f"Please continue with your request [దయచేసి మీ అభ్యర్థనను కొనసాగించండి]."
                )
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
                lang = session_data.get("lang", "en")
                if lang == "te":
                    reply = "దయచేసి టెక్స్ట్, లొకేషన్ లేదా వాయిస్ మెసేజ్ పంపండి."
                else:
                    reply = "Please send text, location, or voice message."
                send_whatsapp_message(sender, reply)
       
        else:
            lang = session_data.get("lang", "en")
            if lang == "te":
                reply = "దయచేసి టెక్స్ట్, లొకేషన్ లేదా వాయిస్ మెసేజ్ పంపండి."
            else:
                reply = "Please send text, location, or voice message."
            send_whatsapp_message(sender, reply)
       
        save_whatsapp_session(sender, session_data)
       
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        if is_simulator:
            return {"status": "error", "message": str(e)}, 500
   
    if is_simulator:
        return {"status": "success", "reply": reply}, 200
    return "OK", 200

# ── ROUTES ────────────────────────────────────────────────────
@app.route("/chat")
def chat_simulator():
    return render_template("chat.html", village=VILLAGE_NAME, sarpanch=SARPANCH_NAME)

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
                else:
                    session['sarpanch_username'] = user[1]
                    session['sarpanch_village'] = user[3]
                return redirect(url_for('dashboard'))
            else:
                error = "Invalid username or password"
        except Exception as e:
            print(f"Login error: {e}")
            error = f"Login error: {str(e)}"
   
    return render_template('login.html', error=error)

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
            if file and file.filename != '':
                import base64
                file_bytes = file.read()
                if file_bytes:
                    base64_data = base64.b64encode(file_bytes).decode('utf-8')
                    mime_type = file.mimetype or "image/jpeg"
                    data_uri = f"data:{mime_type};base64,{base64_data}"
                    update_sarpanch_photo(username, data_uri)
       
        phone = request.form.get("phone", "")
        email = request.form.get("email", "")
       
        conn, db_type = get_db()
        cur = conn.cursor()
        p = get_placeholder(db_type)
        cur.execute(f"UPDATE sarpanch_users SET phone = {p}, email = {p} WHERE username = {p}", (phone, email, username))
        conn.commit()
        conn.close()
       
        return redirect(url_for('profile'))
   
    return render_template('profile.html', user=user)

@app.route("/dashboard")
def dashboard():
    if 'sarpanch_username' not in session:
        return redirect(url_for('login'))
   
    village = session.get('sarpanch_village', 'Kolukonda')
    username = session.get('sarpanch_username', 'Sarpanch')
    user_record = get_sarpanch_by_username(username)
    photo = user_record.get('photo', '') if user_record else ''
    
    # Get sort parameters
    sort_by = request.args.get('sort_by', 'filed_at')
    sort_order = request.args.get('sort_order', 'desc')
    
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
           
            # Multitenancy filtering: only show complaints belonging to this Sarpanch's village!
            comp_village = village_name if village_name else location_text
            if comp_village.strip().lower() != village.strip().lower():
                continue

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
        
        # Apply sorting
        reverse_sort = (sort_order == 'desc')
        if sort_by == 'priority':
            priority_order = {'high': 3, 'medium': 2, 'low': 1}
            filtered_complaints.sort(key=lambda x: priority_order.get(x.get('priority', 'medium'), 2), reverse=reverse_sort)
        elif sort_by == 'status':
            status_order = {'pending': 1, 'in_review': 2, 'in_progress': 3, 'resolved': 4, 'rejected': 5}
            filtered_complaints.sort(key=lambda x: status_order.get(x.get('status', 'pending'), 1), reverse=reverse_sort)
        elif sort_by == 'filed_at':
            filtered_complaints.sort(key=lambda x: x.get('filed_at', ''), reverse=reverse_sort)
        else:
            filtered_complaints.sort(key=lambda x: x.get('filed_at', ''), reverse=True)
       
        pending_certs = []
        processing_certs = []
       
        for x in ce:
            if isinstance(x, dict):
                status = x.get('status', 'pending')
                cert_village = x.get('village', '')
                cert = {
                    'id': x.get('id', ''), 'type': x.get('type', ''), 'name': x.get('name', ''),
                    'phone': x.get('phone', ''), 'purpose': x.get('purpose', ''),
                    'status': status, 'filed_at': x.get('filed_at', '')
                }
            else:
                status = x[6] if len(x) > 6 else 'pending'
                cert_village = x[10] if len(x) > 10 else ''
                cert = {
                    'id': x[0], 'type': x[1], 'name': x[2],
                    'phone': x[4] if len(x) > 4 else '', 'purpose': x[5] if len(x) > 5 else '',
                    'status': status, 'filed_at': x[7] if len(x) > 7 else ''
                }
            
            # Multitenancy filtering: only show certificates belonging to this village!
            if cert_village.strip().lower() != village.strip().lower():
                continue
           
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
       
        return render_template('dashboard.html',
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
            filter_priority=filter_priority,
            sort_by=sort_by,
            sort_order=sort_order)
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
            
        # Multitenancy security verification:
        sarpanch_village = session.get('sarpanch_village', 'Kolukonda')
        comp_village = ""
        if isinstance(row, dict):
            comp_village = row.get('village') or row.get('location') or ""
        else:
            comp_village = row[17] if len(row) > 17 else (row[5] or "")
            
        if comp_village.strip().lower() != sarpanch_village.strip().lower():
            return "Unauthorized to view this complaint", 403
       
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
       
        return render_template('complaint_detail.html', complaint=complaint_dict)
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
        
        # ── Send automatic WhatsApp resolution alert if resolved/rejected ──
        if new_status in ("resolved", "rejected"):
            try:
                cur.execute(f"SELECT name, phone, village FROM complaints WHERE id = {p}", (ticket_id,))
                citizen = cur.fetchone()
                if citizen:
                    c_name = citizen['name'] if isinstance(citizen, dict) else citizen[0]
                    c_phone = citizen['phone'] if isinstance(citizen, dict) else citizen[1]
                    c_village = citizen['village'] if isinstance(citizen, dict) else citizen[2]
                    
                    status_str = "RESOLVED" if new_status == "resolved" else "REJECTED"
                    status_te = "పరిష్కరించబడింది" if new_status == "resolved" else "తిరస్కరించబడింది"
                    
                    notes_section = f"\n📝 Note from Sarpanch: {notes}" if notes else ""
                    notes_section_te = f"\n📝 సర్పంచ్ గారి సందేశం: {notes}" if notes else ""
                    
                    alert_message = (
                        f"📢 *Dear {c_name}, your complaint (ID: {ticket_id}) has been marked as {status_str}!* ✅\n"
                        f"{notes_section}\n\n"
                        f"Thank you for helping keep {c_village} clean and safe! 🙏\n\n"
                        f"──────────────────\n\n"
                        f"📢 *ప్రియమైన {c_name} గారు, మీ ఫిర్యాదు (ID: {ticket_id}) {status_te}!* ✅\n"
                        f"{notes_section_te}\n\n"
                        f"మన {c_village} గ్రామాన్ని పరిశుభ్రంగా మరియు సురక్షితంగా ఉంచడంలో సహాయపడినందుకు ధన్యవాదాలు! 🙏"
                    )
                    
                    print(f"📨 Triggering automatic resolution alert to {c_phone} for {ticket_id}")
                    send_whatsapp_message(c_phone, alert_message)
            except Exception as e_notify:
                print(f"⚠️ Error triggering resolution WhatsApp alert: {e_notify}")
                
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
    return render_template('sarpanch_list.html', sarpanchs=sarpanchs)

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
   
    return render_template('add_sarpanch.html', error=error)


# ── VOICE STREAM PROXY (Mobile-friendly inline playback) ─────
@app.route("/voice-stream")
def voice_stream():
    """Serve local OGG voice files with correct Content-Type so mobile plays inline."""
    from flask import Response
    voice_url = request.args.get("url", "")
    if not voice_url or not voice_url.startswith("/static/voices/"):
        return "Not found", 404
    filepath = voice_url.lstrip("/")
    if not os.path.exists(filepath):
        return "Voice file not found", 404
    try:
        with open(filepath, "rb") as f:
            data = f.read()
        resp = Response(data, status=200, mimetype="audio/ogg")
        resp.headers["Content-Disposition"] = "inline"
        resp.headers["Accept-Ranges"] = "bytes"
        resp.headers["Cache-Control"] = "public, max-age=86400"
        return resp
    except Exception as e:
        return f"Error: {e}", 500




# ── VOICE FROM DATABASE (Permanent stream route) ─────────────
@app.route("/voice/<cid>")
def serve_voice_from_db(cid):
    """Serve voice note from database — permanent, plays on web & mobile (iPhone included)."""
    from flask import Response
    if 'sarpanch_username' not in session:
        return "Unauthorized", 401
    try:
        conn, db_type = get_db()
        cur = conn.cursor()
        p = get_placeholder(db_type)
        cur.execute(f"SELECT voice_data FROM complaints WHERE id = {p}", (cid,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return "Complaint not found", 404
        voice_b64 = row["voice_data"] if isinstance(row, dict) else row[0]
        if not voice_b64:
            return "No voice data stored", 404

        # Parse format prefix: "mp3:BASE64" or "ogg:BASE64"
        if voice_b64.startswith("mp3:"):
            mime_type  = "audio/mpeg"
            audio_bytes = base64.b64decode(voice_b64[4:])
        elif voice_b64.startswith("ogg:"):
            mime_type  = "audio/ogg"
            audio_bytes = base64.b64decode(voice_b64[4:])
        else:
            # Legacy: no prefix, assume ogg
            mime_type  = "audio/ogg"
            audio_bytes = base64.b64decode(voice_b64)

        resp = Response(audio_bytes, status=200, mimetype=mime_type)
        resp.headers["Content-Disposition"] = "inline"
        resp.headers["Content-Length"]      = str(len(audio_bytes))
        resp.headers["Accept-Ranges"]       = "bytes"
        resp.headers["Cache-Control"]       = "private, max-age=86400"
        return resp
    except Exception as e:
        print(f"❌ Voice serve error: {e}")
        return f"Error: {e}", 500

# ── RUN ──────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5006))
    print(f"🚀 Starting on port {port}")
    print(f"📞 WhatsApp Business Number: +91 80080 42801")
    app.run(host="0.0.0.0", port=port, debug=not DATABASE_URL)