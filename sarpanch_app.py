import os, uuid, sqlite3, requests, re
from datetime import datetime
from flask import Flask, request, render_template_string, redirect, session

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

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "sarpanch_secret_2024")
whatsapp_sessions = {}

# ── FORCE DATABASE FIX ON STARTUP ─────────────────────────────
def force_fix_database():
    """Add missing columns to complaints table - runs on every startup"""
    print("🔧 Checking database columns...")
    try:
        if DATABASE_URL:
            # PostgreSQL
            import psycopg2, psycopg2.extras
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()
            columns = [
                ('location_lat', 'DOUBLE PRECISION'),
                ('location_lng', 'DOUBLE PRECISION'),
                ('location_address', 'TEXT'),
                ('maps_link', 'TEXT'),
                ('media_type', 'TEXT'),
                ('media_url', 'TEXT')
            ]
            for col, dtype in columns:
                try:
                    cur.execute(f"ALTER TABLE complaints ADD COLUMN IF NOT EXISTS {col} {dtype}")
                    print(f"✅ Added column: {col}")
                except Exception as e:
                    print(f"⚠️ Column {col} may already exist: {e}")
            conn.commit()
            conn.close()
        else:
            # SQLite
            conn = sqlite3.connect("sarpanch.db")
            cur = conn.cursor()
            columns = ['location_lat', 'location_lng', 'location_address', 'maps_link', 'media_type', 'media_url']
            for col in columns:
                try:
                    cur.execute(f"ALTER TABLE complaints ADD COLUMN {col} TEXT")
                    print(f"✅ Added column: {col}")
                except Exception as e:
                    print(f"⚠️ Column {col} already exists: {e}")
            conn.commit()
            conn.close()
        print("✅ Database columns verified!")
    except Exception as e:
        print(f"❌ Database fix error: {e}")

# Run database fix immediately
force_fix_database()

# ── Database ─────────────────────────────────────────────────
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
    u = "updated" if db_type == "pg" else "updated_at"
    ai = "SERIAL" if db_type == "pg" else "INTEGER"
    autoincrement = "" if db_type == "pg" else "AUTOINCREMENT"
    
    cur.execute(f"CREATE TABLE IF NOT EXISTS complaints (id TEXT PRIMARY KEY, name TEXT, phone TEXT, category TEXT, description TEXT, location TEXT, priority TEXT DEFAULT 'medium', status TEXT DEFAULT 'pending', filed_at TEXT, {u} TEXT, notes TEXT DEFAULT '')")
    cur.execute(f"CREATE TABLE IF NOT EXISTS certificates (id TEXT PRIMARY KEY, type TEXT, name TEXT, father TEXT, phone TEXT, purpose TEXT, status TEXT DEFAULT 'pending', filed_at TEXT, {u} TEXT, notes TEXT DEFAULT '')")
    cur.execute(f"CREATE TABLE IF NOT EXISTS works (id TEXT PRIMARY KEY, title TEXT, status TEXT DEFAULT 'pending', {u} TEXT)")
    cur.execute(f"CREATE TABLE IF NOT EXISTS announcements (id {ai} PRIMARY KEY {autoincrement}, title TEXT, body TEXT, date TEXT)")
    conn.commit()
    conn.close()
    print(f" Database ready ({db_type})")

def now_str(): return datetime.now().strftime("%d-%b-%Y %H:%M")
def fmt_time(): return datetime.now().strftime("%H:%M")
def new_id(prefix=""): return f"{prefix}{str(uuid.uuid4())[:6].upper()}"

def insert_complaint(c):
    conn, db_type = get_db(); cur = conn.cursor()
    p = "%s" if db_type == "pg" else "?"
    u = "updated" if db_type == "pg" else "updated_at"
    cur.execute(f"INSERT INTO complaints (id,name,phone,category,description,location,priority,status,filed_at,{u},notes,location_lat,location_lng,location_address,maps_link,media_type,media_url) VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p})",
        (c["id"],c["name"],c["phone"],c["category"],c["desc"],c.get("location",""),c["priority"],"pending",c["filed_at"],c["filed_at"],"",
         c.get("location_lat"),c.get("location_lng"),c.get("location_address",""),c.get("maps_link",""),
         c.get("media_type",""),c.get("media_url","")))
    conn.commit(); conn.close()

def insert_certificate(c):
    conn, db_type = get_db(); cur = conn.cursor()
    p = "%s" if db_type == "pg" else "?"
    u = "updated" if db_type == "pg" else "updated_at"
    cur.execute(f"INSERT INTO certificates (id,type,name,father,phone,purpose,status,filed_at,{u},notes) VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p})",
        (c["id"],c["type"],c["name"],c["father"],c["phone"],c["purpose"],"pending",c["filed_at"],c["filed_at"],""))
    conn.commit(); conn.close()

def get_record(ref_id):
    conn, db_type = get_db(); cur = conn.cursor()
    p = "%s" if db_type == "pg" else "?"
    u = "updated" if db_type == "pg" else "updated_at"
    tbl = "complaints" if ref_id.startswith("CMP") else "certificates"
    cur.execute(f"SELECT *,{u} as updated FROM {tbl} WHERE id={p}", (ref_id,))
    row = cur.fetchone(); conn.close()
    return dict(row) if row else None

def update_status(table, ref_id, status):
    conn, db_type = get_db(); cur = conn.cursor()
    p = "%s" if db_type == "pg" else "?"
    u = "updated" if db_type == "pg" else "updated_at"
    cur.execute(f"UPDATE {table} SET status={p},{u}={p} WHERE id={p}", (status, now_str(), ref_id))
    conn.commit(); conn.close()

def all_complaints():
    conn, db_type = get_db(); cur = conn.cursor()
    u = "updated" if db_type == "pg" else "updated_at"
    cur.execute(f"SELECT *,{u} as updated FROM complaints ORDER BY filed_at DESC")
    rows = [dict(r) for r in cur.fetchall()]; conn.close(); return rows

def all_certs():
    conn, db_type = get_db(); cur = conn.cursor()
    u = "updated" if db_type == "pg" else "updated_at"
    cur.execute(f"SELECT *,{u} as updated FROM certificates ORDER BY filed_at DESC")
    rows = [dict(r) for r in cur.fetchall()]; conn.close(); return rows

def all_works():
    conn, db_type = get_db(); cur = conn.cursor()
    u = "updated" if db_type == "pg" else "updated_at"
    cur.execute(f"SELECT *,{u} as updated FROM works ORDER BY {u} DESC")
    rows = [dict(r) for r in cur.fetchall()]; conn.close(); return rows

def active_works():
    conn, db_type = get_db(); cur = conn.cursor()
    p = "%s" if db_type == "pg" else "?"
    u = "updated" if db_type == "pg" else "updated_at"
    cur.execute(f"SELECT *,{u} as updated FROM works WHERE status IN ({p},{p})", ("pending","in_progress"))
    rows = [dict(r) for r in cur.fetchall()]; conn.close(); return rows

def all_announcements():
    conn, _ = get_db(); cur = conn.cursor()
    cur.execute("SELECT * FROM announcements ORDER BY id DESC")
    rows = [dict(r) for r in cur.fetchall()]; conn.close(); return rows

def insert_work(title):
    conn, db_type = get_db(); cur = conn.cursor()
    p = "%s" if db_type == "pg" else "?"
    u = "updated" if db_type == "pg" else "updated_at"
    cur.execute(f"INSERT INTO works (id,title,status,{u}) VALUES ({p},{p},{p},{p})", (new_id("WORK-"), title, "pending", now_str()))
    conn.commit(); conn.close()

def insert_announcement(title, body):
    conn, db_type = get_db(); cur = conn.cursor()
    p = "%s" if db_type == "pg" else "?"
    cur.execute(f"INSERT INTO announcements (title,body,date) VALUES ({p},{p},{p})", (title, body, now_str()))
    conn.commit(); conn.close()

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
            print(f" Message sent to {to_number}")
            return True
        else:
            print(f" Failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f" Error: {e}")
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

def get_menu(ctx): return MENU_TE if ctx.get("lang")=="te" else MENU_EN

# ── MAIN BOT REPLY FUNCTION ─────────────────────────────────
def bot_reply(user_msg, ctx, media_info=None):
    msg = user_msg.strip() if user_msg else ""
    ml = msg.lower()
    state = ctx.get("state", "idle")
    lang = ctx.get("lang", "en")
    
    print(f"🔍 DEBUG: state={state}, msg={msg[:30] if msg else 'empty'}")
    
    # Language switching
    if ml == "telugu":
        return MENU_TE, {"state": "idle", "lang": "te"}
    if ml == "english":
        return MENU_EN, {"state": "idle", "lang": "en"}
    
    # Menu navigation
    if ml in ("menu", "home", "back", "hi", "hello", "start", "help"):
        return get_menu({"lang": lang}), {"state": "idle", "lang": lang}
    
    # Voice message handler
    if media_info and media_info.get("type") == "voice":
        ctx["media_type"] = "voice"
        ctx["media_url"] = media_info.get("url", "")
        ctx["state"] = "waiting_for_location"
        return "🎤 Voice received! Please share your location (📎 → Location):", ctx
    
    # IDLE STATE - Main Menu
    if state == "idle":
        if ml == "1":
            return "📝 Enter your full name:", {"state": "c_name", "lang": lang}
        elif ml == "2":
            cats = "\n".join(f"{k}. {v}" for k, v in CERT_TYPES.items())
            return f"📋 Certificate Type:\n{cats}", {"state": "cert_type", "lang": lang}
        elif ml == "3":
            return "🔍 Enter your Reference ID:", {"state": "track_id", "lang": lang}
        elif ml == "4":
            return "📋 Government Schemes\n\n" + "\n".join([f"{n}: {d}" for n, d in SCHEMES]) + "\n\nType menu", {"state": "idle", "lang": lang}
        elif ml == "5":
            rows = active_works()
            if not rows:
                return "🛠️ No active works.\n\nType menu", {"state": "idle", "lang": lang}
            return "🛠️ Works:\n" + "\n".join([f"• {w['title']}" for w in rows[:5]]), {"state": "idle", "lang": lang}
        elif ml == "6":
            rows = all_announcements()[:3]
            if not rows:
                return "📢 No announcements.\n\nType menu", {"state": "idle", "lang": lang}
            return "📢 Announcements:\n" + "\n".join([f"• {a['title']}: {a['body']}" for a in rows]), {"state": "idle", "lang": lang}
        elif ml == "7":
            return f"🏛️ {VILLAGE_NAME} Panchayat\nSarpanch: {SARPANCH_NAME}\nMandal: {MANDAL}\nTimings: Mon-Sat 10AM-5PM", {"state": "idle", "lang": lang}
        else:
            return get_menu({"lang": lang}), {"state": "idle", "lang": lang}
    
    # COMPLAINT FLOW - Name
    if state == "c_name":
        if len(msg) < 2:
            return "Please enter valid name (min 2 chars):", ctx
        ctx["c_name"] = msg.title()
        return "📱 Mobile number (10 digits):", {"state": "c_phone", "c_name": ctx["c_name"], "lang": lang}
    
    # COMPLAINT FLOW - Phone
    if state == "c_phone":
        if not (msg.isdigit() and len(msg) >= 10):
            return "Please enter 10-digit number:", ctx
        ctx["c_phone"] = msg
        cats = "\n".join(f"{k}. {v}" for k, v in COMPLAINT_CATS.items())
        return f"📂 Category:\n{cats}", {"state": "c_cat", "c_name": ctx["c_name"], "c_phone": ctx["c_phone"], "lang": lang}
    
    # COMPLAINT FLOW - Category
    if state == "c_cat":
        if msg not in COMPLAINT_CATS:
            return "Choose 1-7:", ctx
        ctx["c_cat"] = COMPLAINT_CATS[msg]
        return "📝 Describe the problem:", {"state": "c_desc", "c_name": ctx["c_name"], "c_phone": ctx["c_phone"], "c_cat": ctx["c_cat"], "lang": lang}
    
    # COMPLAINT FLOW - Description
    if state == "c_desc":
        if len(msg) < 5:
            return "More details please (min 5 chars):", ctx
        ctx["c_desc"] = msg
        ctx["state"] = "waiting_for_location"
        return "📍 Share your location (📎 → Location) or type village name:", ctx
    
    # WAITING FOR LOCATION
    if state == "waiting_for_location":
        detected_village = detect_village_from_text(msg)
        if detected_village:
            ctx["village"] = detected_village
        elif not ctx.get("location_lat"):
            ctx["location_text"] = msg
        ctx["state"] = "c_pri"
        return "⚡ How urgent?\n1️⃣ Low\n2️⃣ Medium\n3️⃣ High", ctx
    
    # FIXED c_pri STATE - Saves complaint after urgency
    if state == "c_pri":
        print(f"🔍 c_pri received: msg={msg}")
        
        pmap = {"1": "low", "2": "medium", "3": "high"}
        
        if msg not in pmap:
            return "⚡ Please reply with:\n1️⃣ Low\n2️⃣ Medium\n3️⃣ High", ctx
        
        ref = new_id("CMP-")
        maps_link = ctx.get("maps_link", "")
        village = ctx.get("village", ctx.get("location_text", "Not provided"))
        lat = ctx.get("location_lat")
        lng = ctx.get("location_lng")
        
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
            "media_type": ctx.get("media_type", ""),
            "media_url": ctx.get("media_url", "")
        }
        
        print(f"🔍 Saving complaint: {rec}")
        insert_complaint(rec)
        
        reply = f"✅ *Complaint Registered!*\n\n📋 ID: {ref}\n👤 Name: {rec['name']}\n📂 Category: {rec['category']}\n📍 Location: {rec['location']}\n⚡ Priority: {PRI_MAP[rec['priority']]}\n📅 Date: {rec['filed_at']}"
        
        if maps_link:
            reply += f"\n🗺️ Map: {maps_link}"
        
        reply += "\n\nType *menu* for main menu"
        
        return reply, {"state": "idle", "lang": ctx.get("lang", "en")}
    
    # CERTIFICATE FLOW
    if state == "cert_type":
        if msg not in CERT_TYPES:
            return "Choose 1-6:", ctx
        ctx["cert_type"] = CERT_TYPES[msg]
        return "📄 Applicant full name:", {"state": "cert_name", "cert_type": ctx["cert_type"], "lang": lang}
    
    if state == "cert_name":
        if len(msg) < 2:
            return "Please enter valid name:", ctx
        ctx["cert_name"] = msg.title()
        return "👨 Father's/Husband's name:", {"state": "cert_father", "cert_type": ctx["cert_type"], "cert_name": ctx["cert_name"], "lang": lang}
    
    if state == "cert_father":
        if len(msg) < 2:
            return "Please enter valid name:", ctx
        ctx["cert_father"] = msg.title()
        return "📱 Mobile number:", {"state": "cert_phone", "cert_type": ctx["cert_type"], "cert_name": ctx["cert_name"], "cert_father": ctx["cert_father"], "lang": lang}
    
    if state == "cert_phone":
        if not (msg.isdigit() and len(msg) >= 10):
            return "Enter 10-digit number:", ctx
        ctx["cert_phone"] = msg
        return "📝 Purpose (e.g., Bank loan):", {"state": "cert_purpose", "cert_type": ctx["cert_type"], "cert_name": ctx["cert_name"], "cert_father": ctx["cert_father"], "cert_phone": ctx["cert_phone"], "lang": lang}
    
    if state == "cert_purpose":
        if len(msg) < 3:
            return "Please provide purpose:", ctx
        ref = new_id("CERT-")
        rec = {
            "id": ref, "type": ctx["cert_type"], "name": ctx["cert_name"],
            "father": ctx["cert_father"], "phone": ctx["cert_phone"],
            "purpose": msg, "filed_at": now_str()
        }
        insert_certificate(rec)
        return f"✅ Certificate Request Submitted!\n📋 ID: {ref}\nName: {rec['name']}\nType: {rec['type']}\n\nType menu", {"state": "idle", "lang": lang}
    
    # TRACK STATUS
    if state == "track_id":
        if len(msg) < 5:
            return "Please enter valid Reference ID (e.g., CMP-XXXXX):", ctx
        ref = msg.upper().strip()
        rec = get_record(ref)
        if not rec:
            return f"❌ ID {ref} not found.\n\nType menu", {"state": "idle", "lang": lang}
        st = STATUS_MAP.get(rec.get("status", ""), rec.get("status", ""))
        if ref.startswith("CMP"):
            return f"🔍 Complaint Status\n\n📋 ID: {ref}\n👤 Name: {rec.get('name', '')}\n📂 Category: {rec.get('category', '')}\n📍 Location: {rec.get('location', '')}\n📌 Status: {st}\n📅 Filed: {rec.get('filed_at', '')}\n\nType menu", {"state": "idle", "lang": lang}
        return f"🔍 Certificate Status\n\n📋 ID: {ref}\n👤 Name: {rec.get('name', '')}\n📄 Type: {rec.get('type', '')}\n📌 Status: {st}\n📅 Filed: {rec.get('filed_at', '')}\n\nType menu", {"state": "idle", "lang": lang}
    
    # Fallback - show menu
    return get_menu({"lang": lang}), {"state": "idle", "lang": lang}

# ── WhatsApp Webhook ────────────────────────────────────────
@app.route("/whatsapp", methods=["GET", "POST"])
def whatsapp_webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge", "")
        return "Invalid token", 403
    
    try:
        data = request.json
        print(f" Webhook received")
        
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
            print(f" Text from {sender}: {user_msg}")
            reply, session_data = bot_reply(user_msg, session_data)
            send_whatsapp_message(sender, reply)
        
        elif msg_type == "location":
            lat = msg["location"]["latitude"]
            lng = msg["location"]["longitude"]
            name = msg["location"].get("name", "")
            address = msg["location"].get("address", "")
            maps_link = f"https://maps.google.com/?q={lat},{lng}"
            detected_village = detect_village_from_coords(lat, lng) or name or "Unknown"
            
            print(f" Location from {sender}: {detected_village}")
            
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
        
        elif msg_type == "voice":
            voice_id = msg["voice"]["id"]
            voice_url = f"https://graph.facebook.com/v19.0/{voice_id}"
            print(f" Voice from {sender}")
            media_info = {"type": "voice", "url": voice_url}
            reply, session_data = bot_reply("", session_data, media_info)
            send_whatsapp_message(sender, reply)
        
        else:
            send_whatsapp_message(sender, "Please send text, location, or voice message.")
        
        whatsapp_sessions[sender] = session_data
        
    except Exception as e:
        print(f" Webhook error: {e}")
    
    return "OK", 200

# ── Routes ────────────────────────────────────────────────────
@app.route("/")
def home():
    return redirect("/sarpanch")

@app.route("/sarpanch")
def dashboard():
    ac = all_complaints()
    ce = all_certs()
    wo = all_works()
    an = all_announcements()
    
    active_complaints = [x for x in ac if x["status"] in ("pending", "in_review", "in_progress")]
    resolved_complaints = [x for x in ac if x["status"] in ("resolved", "rejected")]
    active_certs = [x for x in ce if x["status"] in ("pending", "processing")]
    resolved_certs = [x for x in ce if x["status"] in ("ready", "rejected")]
    
    counts = dict(
        pc=len(active_complaints),
        cert=len(active_certs),
        res=len(resolved_complaints) + len(resolved_certs),
        works=sum(1 for x in wo if x["status"] in ("pending", "in_progress")),
        hi=sum(1 for x in ac if x.get("priority") == "high" and x["status"] not in ("resolved", "rejected")),
    )
    
    return render_template_string(DASH_HTML, 
        active_complaints=active_complaints,
        resolved_complaints=resolved_complaints,
        active_certs=active_certs,
        resolved_certs=resolved_certs,
        works=wo,
        announcements=an,
        village=VILLAGE_NAME,
        sarpanch=SARPANCH_NAME,
        mandal=MANDAL,
        now=datetime.now().strftime("%d %b %Y, %H:%M"),
        c=counts)

@app.route("/complaint/<cid>")
def view_complaint(cid):
    conn, db_type = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM complaints WHERE id = ?", (cid,))
    complaint = cur.fetchone()
    conn.close()
    if not complaint:
        return "Complaint not found", 404
    return render_template_string(COMPLAINT_DETAIL_HTML, complaint=complaint)

@app.route("/update_status", methods=["POST"])
def update_status_route():
    ticket_id = request.form.get("ticket_id")
    new_status = request.form.get("status")
    notes = request.form.get("notes", "")
    conn, db_type = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE complaints SET status = ?, notes = ? WHERE id = ?", (new_status, notes, ticket_id))
    conn.commit()
    conn.close()
    return redirect(f"/complaint/{ticket_id}")

@app.route("/send_reply", methods=["POST"])
def send_reply_route():
    ticket_id = request.form.get("ticket_id")
    reply_message = request.form.get("reply_message")
    conn, db_type = get_db()
    cur = conn.cursor()
    cur.execute("SELECT phone FROM complaints WHERE id = ?", (ticket_id,))
    result = cur.fetchone()
    conn.close()
    if result:
        citizen_number = result["phone"] if isinstance(result, dict) else result[0]
        send_whatsapp_message(citizen_number, f"📢 Update on Ticket {ticket_id}\n\n{reply_message}\n\n- Sarpanch, {VILLAGE_NAME}")
    return redirect(f"/complaint/{ticket_id}")

@app.route("/caction/<rid>/<action>")
def c_action(rid, action):
    update_status("complaints", rid.upper(), action)
    return redirect("/sarpanch")

@app.route("/certaction/<rid>/<action>")
def cert_action(rid, action):
    update_status("certificates", rid.upper(), action)
    return redirect("/sarpanch")

@app.route("/waction/<rid>/<action>")
def w_action(rid, action):
    update_status("works", rid.upper(), action)
    return redirect("/sarpanch")

@app.route("/addwork", methods=["POST"])
def add_work():
    t = request.form.get("title", "").strip()
    if t:
        insert_work(t)
    return redirect("/sarpanch")

@app.route("/announce", methods=["POST"])
def announce():
    t = request.form.get("title", "").strip()
    b = request.form.get("body", "").strip()
    if t and b:
        insert_announcement(t, b)
    return redirect("/sarpanch")

# ── HTML TEMPLATES ────────────────────────────────────────────
DASH_HTML = r"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="20">
<title>{{ village }} Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--green:#4a7c59;--red:#c0392b;--blue:#0070f3;--amber:#e07b00;--border:#dfe1e6;--text:#172b4d;--sub:#6b778c}
body{font-family:'DM Sans',sans-serif;background:#f0f2f5;color:var(--text)}
.tb{background:var(--green);color:#fff;padding:0 24px;height:62px;display:flex;align-items:center;justify-content:space-between}
.tl{display:flex;align-items:center;gap:14px}
.tb h1{font-size:15px;font-weight:700}
.ts{font-size:11px;opacity:.75}
.stats{display:flex;gap:12px;padding:18px 24px 0;flex-wrap:wrap}
.sc{background:#fff;border-radius:10px;padding:14px 20px;flex:1;min-width:110px;box-shadow:0 1px 4px rgba(0,0,0,.06)}
.sc .val{font-size:26px;font-weight:700}.sc .lbl{font-size:11px;color:var(--sub);margin-top:2px}
.sc.c1 .val{color:var(--amber)}.sc.c2 .val{color:var(--blue)}.sc.c3 .val{color:var(--green)}.sc.c4 .val{color:#7b2d8b}.sc.c5 .val{color:var(--red)}
.sec{margin:18px 24px;background:#fff;border-radius:12px;box-shadow:0 1px 4px rgba(0,0,0,.06);overflow:hidden}
.sh{padding:12px 18px;border-bottom:1px solid var(--border);font-weight:600;font-size:14px;display:flex;justify-content:space-between;align-items:center;background:#f4f5f7}
.sh span{font-weight:400;color:var(--sub);font-size:12px}
table{width:100%;border-collapse:collapse}
th{padding:9px 14px;font-size:11px;color:var(--sub);text-align:left;background:#f4f5f7;border-bottom:1px solid var(--border);font-weight:600}
td{padding:10px 14px;font-size:13px;border-bottom:1px solid var(--border);vertical-align:middle}
tr:last-child td{border-bottom:none}tr:hover td{background:#fafafa}
.badge{display:inline-block;padding:2px 8px;border-radius:20px;font-size:11px;font-weight:600}
.badge.pending{background:#fff4e0;color:var(--amber)}.badge.in_review{background:#dbeafe;color:var(--blue)}
.badge.in_progress{background:#e0e7ff;color:#4338ca}.badge.resolved{background:#dcfce7;color:var(--green)}
.badge.rejected{background:#fee2e2;color:var(--red)}.badge.ready{background:#dcfce7;color:var(--green)}
.badge.processing{background:#dbeafe;color:var(--blue)}
.ph{color:var(--red);font-weight:700}.pm{color:var(--amber)}.pl{color:var(--green)}
.acts{display:flex;gap:5px;flex-wrap:wrap}
.btn{padding:4px 10px;border-radius:5px;font-size:11px;font-weight:600;text-decoration:none;border:none;font-family:inherit;display:inline-block;cursor:pointer}
.bb{background:var(--blue);color:#fff}.bg{background:var(--green);color:#fff}
.br{background:var(--red);color:#fff}.ba{background:var(--amber);color:#fff}
.empty{text-align:center;padding:28px;color:var(--sub);font-size:13px}
.af,.wf{padding:14px 18px;border-top:1px solid var(--border);display:flex;gap:8px;flex-wrap:wrap}
.af input,.wf input{flex:1;border:1px solid var(--border);border-radius:6px;padding:8px 12px;font-family:inherit;font-size:13px;min-width:140px}
.af button,.wf button{background:var(--green);color:#fff;border:none;border-radius:6px;padding:8px 16px;cursor:pointer;font-weight:600}
.map-link{color:#1a73e8;text-decoration:none;font-weight:500}
</style></head><body>
<div class="tb">
  <div class="tl"><div><h1>{{ village }} — Sarpanch Dashboard</h1><div class="ts">{{ sarpanch }} · {{ mandal }}</div></div></div>
  <div style="font-size:12px;opacity:.8">Auto-refresh 20s · {{ now }}</div>
</div>
<div class="stats">
  <div class="sc c1"><div class="val">{{ c.pc }}</div><div class="lbl">Pending Complaints</div></div>
  <div class="sc c2"><div class="val">{{ c.cert }}</div><div class="lbl">Cert Requests</div></div>
  <div class="sc c3"><div class="val">{{ c.res }}</div><div class="lbl">Resolved</div></div>
  <div class="sc c4"><div class="val">{{ c.works }}</div><div class="lbl">Active Works</div></div>
  <div class="sc c5"><div class="val">{{ c.hi }}</div><div class="lbl">High Priority</div></div>
</div>

<!-- Active Complaints Section -->
<div class="sec">
  <div class="sh">📋 Active Complaints <span>Pending + In Review + In Progress</span></div>
  {% if active_complaints %}
  <table><thead><tr><th>#</th><th>ID</th><th>Name</th><th>Category</th><th>Location</th><th>Priority</th><th>Filed</th><th>Status</th><th>Actions</th></tr></thead><tbody>
  {% for x in active_complaints %}
  <tr>
    <td>{{ loop.index }}</td>
    <td><strong>{{ x.id }}</strong></td>
    <td>{{ x.name }}<br><small style="color:#888">{{ x.phone }}</small></td>
    <td>{{ x.category }}</td>
    <td>{% if x.maps_link %}<a href="{{ x.maps_link }}" target="_blank" class="map-link">📍 Map</a>{% else %}{{ x.location }}{% endif %}</td>
    <td class="p{{ x.priority[0] }}">{{ x.priority|upper }}</td>
    <td style="font-size:11px;color:#888">{{ x.filed_at }}</td>
    <td><span class="badge {{ x.status }}">{{ x.status.replace('_',' ').title() }}</span></td>
    <td><div class="acts">
      {% if x.status=='pending' %}<a href="/caction/{{ x.id }}/in_review" class="btn bb">Review</a>{% endif %}
      {% if x.status=='in_review' %}<a href="/caction/{{ x.id }}/in_progress" class="btn ba">Start</a>{% endif %}
      {% if x.status=='in_progress' %}<a href="/caction/{{ x.id }}/resolved" class="btn bg">Done</a>{% endif %}
      <a href="/caction/{{ x.id }}/rejected" class="btn br">X</a>
      <a href="/complaint/{{ x.id }}" class="btn bb" style="background:#666">View</a>
    </div></td>
  </tr>
  {% endfor %}</tbody></table>
  {% else %}<div class="empty">No active complaints!</div>{% endif %}
</div>

<!-- Active Certificate Requests -->
<div class="sec">
  <div class="sh">📋 Active Certificate Requests <span>Pending + Processing</span></div>
  {% if active_certs %}
  <table><thead><tr><th>#</th><th>ID</th><th>Name</th><th>Type</th><th>Purpose</th><th>Filed</th><th>Status</th><th>Actions</th></tr></thead><tbody>
  {% for x in active_certs %}
  <tr>
    <td>{{ loop.index }}</td>
    <td><strong>{{ x.id }}</strong></td>
    <td>{{ x.name }}<br><small style="color:#888">{{ x.phone }}</small></td>
    <td>{{ x.type }}</td>
    <td>{{ x.purpose }}</td>
    <td style="font-size:11px;color:#888">{{ x.filed_at }}</td>
    <td><span class="badge {{ x.status }}">{{ x.status.title() }}</span></td>
    <td><div class="acts">
      {% if x.status=='pending' %}<a href="/certaction/{{ x.id }}/processing" class="btn bb">Process</a>{% endif %}
      {% if x.status=='processing' %}<a href="/certaction/{{ x.id }}/ready" class="btn bg">Ready</a>{% endif %}
      <a href="/certaction/{{ x.id }}/rejected" class="btn br">X</a>
    </div></td>
  </tr>
  {% endfor %}</tbody></table>
  {% else %}<div class="empty">No pending certificate requests!</div>{% endif %}
</div>

<!-- Development Works -->
<div class="sec">
  <div class="sh">🛠️ Development Works</div>
  {% if works %}
  <table><thead><tr><th>ID</th><th>Title</th><th>Status</th><th>Updated</th><th>Actions</th></tr></thead><tbody>
  {% for w in works %}
  <tr>
    <td><strong>{{ w.id }}</strong></td>
    <td>{{ w.title }}</td>
    <td><span class="badge {{ w.status }}">{{ w.status.replace('_',' ').title() }}</span></td>
    <td style="font-size:11px;color:#888">{{ w.updated }}</td>
    <td><div class="acts">
      {% if w.status=='pending' %}<a href="/waction/{{ w.id }}/in_progress" class="btn bb">Start</a>{% endif %}
      {% if w.status=='in_progress' %}<a href="/waction/{{ w.id }}/resolved" class="btn bg">Done</a>{% endif %}
      <a href="/waction/{{ w.id }}/rejected" class="btn br">X</a>
    </div></td>
  </tr>
  {% endfor %}</tbody></table>
  {% else %}<div class="empty">No works added.</div>{% endif %}
  <form method="post" action="/addwork" class="wf">
    <input type="text" name="title" placeholder="Add new work" required>
    <button type="submit">+ Add Work</button>
  </form>
</div>

<!-- Announcements -->
<div class="sec">
  <div class="sh">📢 Announcements</div>
  {% if announcements %}
  <table><thead><tr><th>Title</th><th>Message</th><th>Date</th></tr></thead><tbody>
  {% for a in announcements %}
  <tr>
    <td><strong>{{ a.title }}</strong></td>
    <td>{{ a.body }}</td>
    <td style="font-size:11px;color:#888">{{ a.date }}</td>
  </tr>
  {% endfor %}</tbody></table>
  {% else %}<div class="empty">No announcements.</div>{% endif %}
  <form method="post" action="/announce" class="af">
    <input type="text" name="title" placeholder="Title" required>
    <input type="text" name="body" placeholder="Message..." required>
    <button type="submit">Post Announcement</button>
  </form>
</div>

<!-- Resolved/Closed Items -->
<div class="sec">
  <div class="sh">✅ Resolved / Closed Items</div>
  {% if resolved_complaints or resolved_certs %}
  <table><thead><tr><th>ID</th><th>Type</th><th>Name</th><th>Details</th><th>Status</th><th>Action</th></tr></thead><tbody>
  {% for x in resolved_complaints %}
  <tr>
    <td>{{ x.id }}</td>
    <td>Complaint</td>
    <td>{{ x.name }}</td>
    <td>{{ x.category }}</td>
    <td><span class="badge {{ x.status }}">{{ x.status.title() }}</span></td>
    <td><a href="/complaint/{{ x.id }}" class="btn bb" style="background:#666">View</a></td>
  </tr>
  {% endfor %}
  {% for x in resolved_certs %}
  <tr>
    <td>{{ x.id }}</td>
    <td>Certificate</td>
    <td>{{ x.name }}</td>
    <td>{{ x.type }}</td>
    <td><span class="badge {{ x.status }}">{{ x.status.title() }}</span></td>
    <td>-</td>
  </tr>
  {% endfor %}
  </tbody></table>
  {% else %}<div class="empty">No resolved items.</div>{% endif %}
</div>
</body></html>
"""

COMPLAINT_DETAIL_HTML = r"""<!DOCTYPE html>
<html>
<head><title>Complaint Details</title>
<style>
body{font-family: Arial; margin:0; background:#f5f5f5}
.header{background:#4a7c59; color:white; padding:15px 20px}
.container{max-width:800px; margin:30px auto; background:white; padding:25px; border-radius:10px; box-shadow:0 2px 10px rgba(0,0,0,0.1)}
.field{margin-bottom:15px}
.label{font-weight:bold; width:150px; display:inline-block}
button{background:#1a73e8; color:white; border:none; padding:10px 20px; border-radius:5px; cursor:pointer}
.reply-box{width:100%; padding:10px; margin:10px 0; border:1px solid #ddd; border-radius:5px}
.back-btn{background:#666; color:white; padding:8px 15px; text-decoration:none; display:inline-block; margin-bottom:20px; border-radius:5px}
hr{margin:20px 0}
.map-link{color:#1a73e8; text-decoration:none; font-weight:bold}
</style>
</head>
<body>
<div class="header"><h2>Complaint Details</h2></div>
<div class="container">
<a href="/sarpanch" class="back-btn">← Back to Dashboard</a>
<div class="field"><span class="label">Ticket ID:</span> {{ complaint.id }}</div>
<div class="field"><span class="label">Citizen Name:</span> {{ complaint.name }}</div>
<div class="field"><span class="label">Phone:</span> {{ complaint.phone }}</div>
<div class="field"><span class="label">Category:</span> {{ complaint.category }}</div>
<div class="field"><span class="label">Location:</span> {{ complaint.location }}</div>
<div class="field"><span class="label">Priority:</span> {{ complaint.priority|upper }}</div>
<div class="field"><span class="label">Status:</span> {{ complaint.status.replace('_',' ').title() }}</div>
<div class="field"><span class="label">Filed:</span> {{ complaint.filed_at }}</div>
{% if complaint.maps_link %}
<div class="field">
    <span class="label">🗺️ Map Location:</span>
    <a href="{{ complaint.maps_link }}" target="_blank" class="map-link">Click to view on Google Maps</a>
    <br><small style="color:#666">Coordinates: {{ complaint.location_lat }}, {{ complaint.location_lng }}</small>
</div>
{% endif %}
<div class="field">
    <span class="label">Complaint:</span><br>
    <div style="background:#f8f9fa; padding:15px; border-radius:5px; margin-top:5px">{{ complaint.description }}</div>
</div>
<hr>
<h3>Update Status</h3>
<form method="POST" action="/update_status">
<input type="hidden" name="ticket_id" value="{{ complaint.id }}">
<select name="status">
    <option value="pending" {% if complaint.status=='pending' %}selected{% endif %}>Pending</option>
    <option value="in_review" {% if complaint.status=='in_review' %}selected{% endif %}>In Review</option>
    <option value="in_progress" {% if complaint.status=='in_progress' %}selected{% endif %}>In Progress</option>
    <option value="resolved" {% if complaint.status=='resolved' %}selected{% endif %}>Resolved</option>
    <option value="rejected" {% if complaint.status=='rejected' %}selected{% endif %}>Rejected</option>
</select>
<textarea name="notes" placeholder="Add internal notes..." rows="2" style="width:100%; margin:10px 0"></textarea>
<button type="submit">Update Status</button>
</form>
<hr>
<h3>Send Reply to Citizen</h3>
<form method="POST" action="/send_reply">
<input type="hidden" name="ticket_id" value="{{ complaint.id }}">
<textarea name="reply_message" class="reply-box" rows="4" placeholder="Type your reply... Citizen will receive this on WhatsApp"></textarea>
<button type="submit">Send Reply</button>
</form>
</div>
</body></html>
"""

# ── Run ──────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5006))
    print(f" Starting on port {port}")
    print(f" WhatsApp Business Number: +91 80080 42801")
    app.run(host="0.0.0.0", port=port, debug=not DATABASE_URL)