import os, uuid, sqlite3
from datetime import datetime
from flask import Flask, request, render_template_string, redirect, session
import requests

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
    cur.execute(f"INSERT INTO complaints (id,name,phone,category,description,location,priority,status,filed_at,{u},notes) VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p})",
        (c["id"],c["name"],c["phone"],c["category"],c["desc"],c["location"],c["priority"],"pending",c["filed_at"],c["filed_at"],""))
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

# ── WhatsApp API Function (Meta, not Twilio) ─────────────────
def send_whatsapp_message(to_number, message):
    """Send message using Meta WhatsApp Cloud API"""
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
            print(f" Failed to send: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f" Error sending message: {e}")
        return False

# ── Bot Logic ────────────────────────────────────────────────
MENU_EN = ("Namaskaram! Welcome to *{v}* Gram Panchayat\nSarpanch: *{s}*\n\n"
    "1 Register Complaint\n2 Request Certificate\n3 Track Status\n"
    "4 Government Schemes\n5 Development Works\n6 Announcements\n7 Office Info\n\n"
    "Telugu lo kavali ante *telugu* ani pampandi.").format(v=VILLAGE_NAME,s=SARPANCH_NAME)

MENU_TE = ("Namaskaram! *{v}* Grama Panchayatiki swaagatam\nSarpanch: *{s}*\n\n"
    "1 Firyaadu Namodhu\n2 Certificate Abhyartana\n3 Sthiti Tanikhee\n"
    "4 Prabhutvam Pathakaalu\n5 Abhivruddhi Panulu\n6 Prakatanalu\n7 Karyalayam\n\n"
    "For English type *english*").format(v=VILLAGE_NAME,s=SARPANCH_NAME)

COMPLAINT_CATS = {"1":"Road / Pothole","2":"Water Supply","3":"Electricity","4":"Drainage","5":"Ration Shop","6":"Land Dispute","7":"Other"}
CERT_TYPES = {"1":"Income Certificate","2":"Caste Certificate","3":"Residence Certificate","4":"Birth Certificate","5":"Death Certificate","6":"Agriculture Land Certificate"}
SCHEMES = [("Rythu Bandhu","Rs 5000/acre/season for farmers"),("PM Awas Yojana","Free house for BPL families"),
    ("Aarogyasri","Free medical up to Rs 5L/year"),("Kalyana Lakshmi","Rs 1 lakh for girl marriage"),
    ("PM Kisan","Rs 6000/year for farmers"),("NREGA","100 days employment"),("Bhadratha","Free LPG for BPL")]
STATUS_MAP = {"pending":"Pending","in_review":"In Review","in_progress":"In Progress","resolved":"Resolved","rejected":"Rejected","ready":"Ready to Collect","processing":"Processing"}
PRI_MAP = {"low":"Low","medium":"Medium","high":"High"}

def get_menu(ctx): return MENU_TE if ctx.get("lang")=="te" else MENU_EN

def bot_reply(user_msg, ctx):
    msg=user_msg.strip(); ml=msg.lower()
    state=ctx.get("state","idle"); lang=ctx.get("lang","en")
    
    if ml=="telugu": ctx.update({"lang":"te","state":"idle"}); return MENU_TE,ctx
    if ml=="english": ctx.update({"lang":"en","state":"idle"}); return MENU_EN,ctx
    if ml in ("menu","home","back","hi","hello","start","help"): 
        ctx={"state":"idle","lang":lang}; return get_menu(ctx),ctx

    if state=="idle":
        if ml in ("1","complaint"): ctx["state"]="c_name"; return "Register Complaint\n\nEnter your full name:",ctx
        if ml in ("2","certificate"):
            cats="\n".join(f"{k}. {v}" for k,v in CERT_TYPES.items()); ctx["state"]="cert_type"
            return f"Certificate Request\n\nSelect type:\n{cats}",ctx
        if ml in ("3","track","status"): ctx["state"]="track_id"; return "Enter your Reference ID:\n(e.g. CMP-A3F9B2)",ctx
        if ml in ("4","schemes"):
            lines=[f"{n}: {d}" for n,d in SCHEMES]; ctx["state"]="idle"
            return "Government Schemes\n\n"+"\n\n".join(lines)+"\n\nType menu.",ctx
        if ml in ("5","works"):
            rows=active_works(); ctx["state"]="idle"
            if not rows: return "No active works.\n\nType menu.",ctx
            lines=[f"{w['title']} - {STATUS_MAP.get(w['status'],w['status'])}" for w in rows[:5]]
            return "Development Works:\n\n"+"\n".join(lines)+"\n\nType menu.",ctx
        if ml in ("6","announcements"):
            rows=all_announcements()[:3]; ctx["state"]="idle"
            if not rows: return "No announcements.\n\nType menu.",ctx
            return "Announcements:\n\n"+"\n\n".join(f"{a['title']}: {a['body']}" for a in rows)+"\n\nType menu.",ctx
        if ml in ("7","info","office"):
            ctx["state"]="idle"
            return f"{VILLAGE_NAME} Gram Panchayat\nSarpanch: {SARPANCH_NAME}\n{MANDAL}\nOffice: Mon-Sat 10AM-5PM\nHelpline: 1800-425-0066\nCM: 1100\nEmergency: 112",ctx
        return "Please choose from menu:\n\n"+get_menu(ctx),ctx

    # COMPLAINT
    if state=="c_name":
        if len(msg)<2: return "Enter valid name.",ctx
        ctx["c_name"]=msg.title(); ctx["state"]="c_phone"; return f"Hello {ctx['c_name']}!\n\nMobile number:",ctx
    if state=="c_phone":
        if not(msg.isdigit() and len(msg)>=10): return "Enter 10-digit number.",ctx
        ctx["c_phone"]=msg; ctx["state"]="c_cat"
        return "Select category:\n\n"+"\n".join(f"{k}. {v}" for k,v in COMPLAINT_CATS.items()),ctx
    if state=="c_cat":
        if msg not in COMPLAINT_CATS: return "Choose 1-7.",ctx
        ctx["c_cat"]=COMPLAINT_CATS[msg]; ctx["state"]="c_desc"; return f"Category: {ctx['c_cat']}\n\nDescribe the problem:",ctx
    if state=="c_desc":
        if len(msg)<5: return "Describe in more words.",ctx
        ctx["c_desc"]=msg; ctx["state"]="c_loc"; return "Enter exact location / street name:",ctx
    if state=="c_loc":
        ctx["c_loc"]=msg; ctx["state"]="c_pri"; return "How urgent?\n\n1. Low\n2. Medium\n3. High",ctx
    if state=="c_pri":
        pmap={"1":"low","2":"medium","3":"high"}
        if msg not in pmap: return "Reply 1, 2, or 3.",ctx
        ref=new_id("CMP-")
        rec={"id":ref,"name":ctx["c_name"],"phone":ctx["c_phone"],"category":ctx["c_cat"],
             "desc":ctx["c_desc"],"location":ctx["c_loc"],"priority":pmap[msg],"filed_at":now_str()}
        insert_complaint(rec)
        ctx={"state":"idle","lang":lang}
        return f"Complaint Registered!\n\nName: {rec['name']}\nCategory: {rec['category']}\nLocation: {rec['location']}\nPriority: {PRI_MAP[rec['priority']]}\nReference ID: {ref}\n\nSave your ID.\nResolution: 3-7 days.\n\nType menu.",ctx

    # CERTIFICATE
    if state=="cert_type":
        if msg not in CERT_TYPES: return "Choose 1-6.",ctx
        ctx["cert_type"]=CERT_TYPES[msg]; ctx["state"]="cert_name"; return f"Certificate: {ctx['cert_type']}\n\nApplicant full name:",ctx
    if state=="cert_name":
        ctx["cert_name"]=msg.title(); ctx["state"]="cert_father"; return "Father's / husband's name:",ctx
    if state=="cert_father":
        ctx["cert_father"]=msg.title(); ctx["state"]="cert_phone"; return "Mobile number:",ctx
    if state=="cert_phone":
        if not(msg.isdigit() and len(msg)>=10): return "Enter 10-digit number.",ctx
        ctx["cert_phone"]=msg; ctx["state"]="cert_purpose"; return "Purpose?\n(e.g. Bank loan, School admission)",ctx
    if state=="cert_purpose":
        ref=new_id("CERT-")
        rec={"id":ref,"type":ctx["cert_type"],"name":ctx["cert_name"],"father":ctx["cert_father"],
             "phone":ctx["cert_phone"],"purpose":msg,"filed_at":now_str()}
        insert_certificate(rec)
        ctx={"state":"idle","lang":lang}
        return f"Certificate Request Submitted!\n\nName: {rec['name']}\nType: {rec['type']}\nReference ID: {ref}\n\nSave your ID.\nProcessing: 5-7 days.\n\nType menu.",ctx

    # TRACK
    if state=="track_id":
        ref=msg.upper().strip(); ctx["state"]="idle"
        rec=get_record(ref)
        if not rec: return f"ID {ref} not found.\n\nType menu.",ctx
        st=STATUS_MAP.get(rec.get("status",""),rec.get("status",""))
        if ref.startswith("CMP"):
            return f"Complaint Status\n\nName: {rec['name']}\nCategory: {rec.get('category','')}\nLocation: {rec.get('location','')}\nFiled: {rec.get('filed_at','')}\nStatus: {st}\n\nType menu.",ctx
        return f"Certificate Status\n\nName: {rec['name']}\nType: {rec.get('type','')}\nFiled: {rec.get('filed_at','')}\nStatus: {st}\n\nType menu.",ctx

    ctx["state"]="idle"; return "Let's start over.\n\n"+get_menu(ctx),ctx

# ── Routes ────────────────────────────────────────────────────
CHIPS = ["1 Complaint","2 Certificate","3 Track Status","4 Schemes","5 Works","6 Announcements"]

@app.route("/", methods=["GET","POST"])
def chat_view():
    if "chat" not in session:
        session["chat"]=[("bot",MENU_EN,fmt_time())]
        session["ctx"]={"state":"idle","lang":"en"}
        session.modified=True
    chips=CHIPS if session["ctx"].get("state")=="idle" else []
    if request.method=="POST":
        um=request.form.get("message","").strip()
        if not um: return redirect("/")
        session["chat"].append(("user",um,fmt_time()))
        reply,nc=bot_reply(um,dict(session["ctx"]))
        session["ctx"]=nc
        session["chat"].append(("bot",reply,fmt_time()))
        session.modified=True
        chips=CHIPS if session["ctx"].get("state")=="idle" else []
    session["chat"]=session["chat"][-80:]
    return render_template_string(CHAT_HTML,chat=session["chat"],chips=chips,
        village=VILLAGE_NAME,sarpanch=SARPANCH_NAME)

@app.route("/sarpanch")
def dashboard():
    ac=all_complaints(); ce=all_certs(); wo=all_works(); an=all_announcements()
    counts=dict(
        pc=sum(1 for x in ac if x["status"] in ("pending","in_review","in_progress")),
        cert=sum(1 for x in ce if x["status"] in ("pending","processing")),
        res=sum(1 for x in ac+ce if x["status"] in ("resolved","ready")),
        works=sum(1 for x in wo if x["status"] in ("pending","in_progress")),
        hi=sum(1 for x in ac if x.get("priority")=="high" and x["status"] not in ("resolved","rejected")),
    )
    return render_template_string(DASH_HTML,complaints=ac,certs=ce,works=wo,
        announcements=an,village=VILLAGE_NAME,sarpanch=SARPANCH_NAME,
        mandal=MANDAL,now=datetime.now().strftime("%d %b %Y, %H:%M"),
        c=counts)

@app.route("/caction/<rid>/<action>")
def c_action(rid,action): update_status("complaints",rid.upper(),action); return redirect("/sarpanch")

@app.route("/certaction/<rid>/<action>")
def cert_action(rid,action): update_status("certificates",rid.upper(),action); return redirect("/sarpanch")

@app.route("/waction/<rid>/<action>")
def w_action(rid,action): update_status("works",rid.upper(),action); return redirect("/sarpanch")

@app.route("/addwork",methods=["POST"])
def add_work():
    t=request.form.get("title","").strip()
    if t: insert_work(t)
    return redirect("/sarpanch")

@app.route("/announce",methods=["POST"])
def announce():
    t=request.form.get("title","").strip(); b=request.form.get("body","").strip()
    if t and b: insert_announcement(t,b)
    return redirect("/sarpanch")

# ── WhatsApp Webhook Endpoint (Meta API) ─────────────────────
@app.route("/whatsapp", methods=["GET", "POST"])
def whatsapp_webhook():
    # Meta webhook verification (GET request)
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge", "")
        return "Invalid token", 403

    # Incoming message from Meta (POST request)
    try:
        data = request.json
        print(f" Webhook received: {data}")
        
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        
        if not messages:
            return "OK", 200
        
        msg = messages[0]
        sender = msg.get("from", "")
        msg_type = msg.get("type", "")
        
        if msg_type != "text":
            # For non-text messages, reply accordingly
            send_whatsapp_message(sender, "Please send text messages only. For complaints, please describe your problem in text.")
            return "OK", 200
        
        user_msg = msg["text"]["body"].strip()
        print(f" Message from {sender}: {user_msg}")
        
        # Get or create session for this user
        if sender not in whatsapp_sessions:
            whatsapp_sessions[sender] = {"state": "idle", "lang": "en"}
        
        # Get bot reply
        reply, whatsapp_sessions[sender] = bot_reply(user_msg, whatsapp_sessions[sender])
        
        # Send reply via Meta API
        send_whatsapp_message(sender, reply)
        
    except Exception as e:
        print(f" Webhook error: {e}")
    
    return "OK", 200

@app.route("/sessions")
def sessions():
    rows="".join(f"<tr><td>{p}</td><td>{c.get('state','?')}</td><td>{c.get('lang','en')}</td></tr>" for p,c in whatsapp_sessions.items())
    return f"<html><body style='font-family:monospace;padding:20px'><h3>Sessions ({len(whatsapp_sessions)})</h3><table border=1 cellpadding=8><tr><th>Phone</th><th>State</th><th>Lang</th></tr>{rows or '<tr><td colspan=3>None</td></tr>'}</table><br><a href='/sarpanch'>Dashboard</a></body></html>"

# ── HTML Templates (No photo) ────────────────────────────────
CHAT_HTML = r"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ village }}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',sans-serif;background:#d9dbdd;min-height:100vh;display:flex;align-items:center;justify-content:center}
.phone{width:390px;height:760px;background:#fff;border-radius:24px;box-shadow:0 24px 64px rgba(0,0,0,.25);display:flex;flex-direction:column;overflow:hidden}
.header{background:#4a7c59;padding:12px 16px;display:flex;align-items:center;gap:10px;flex-shrink:0}
.header-text h2{color:#fff;font-size:14px;font-weight:600}
.header-text p{color:#c5dfc9;font-size:11px}
.chat{flex:1;overflow-y:auto;padding:12px 10px;background:#efeae2;display:flex;flex-direction:column;gap:6px}
.bw{display:flex;flex-direction:column}
.bw.user{align-items:flex-end}.bw.bot{align-items:flex-start}
.bubble{max-width:78%;padding:8px 12px;border-radius:12px;font-size:13px;line-height:1.55;white-space:pre-wrap;word-break:break-word}
.bubble.user{background:#dcf8c6;border-bottom-right-radius:2px}
.bubble.bot{background:#fff;border-bottom-left-radius:2px;box-shadow:0 1px 2px rgba(0,0,0,.1)}
.tl{font-size:10px;color:#999;margin-top:2px;padding:0 4px}
.dd{text-align:center;margin:8px 0}
.dd span{background:#d4e8d7;color:#555;font-size:11px;padding:3px 10px;border-radius:8px}
.chips{display:flex;flex-wrap:wrap;gap:6px;padding:6px 10px 0;background:#f8f9fa}
.chip{background:#eaf3ec;border:1px solid #4a7c59;color:#2d5a3d;font-size:12px;padding:4px 10px;border-radius:14px;cursor:pointer;font-family:inherit}
.ir{display:flex;align-items:center;gap:8px;padding:10px;background:#f0f0f0;border-top:1px solid #ddd;flex-shrink:0}
.ir input{flex:1;border:none;background:#fff;border-radius:22px;padding:10px 16px;font-size:14px;font-family:inherit;outline:none}
.sb{width:44px;height:44px;background:#4a7c59;border:none;border-radius:50%;cursor:pointer;font-size:18px;color:#fff}
.fab{position:fixed;bottom:24px;right:24px;background:#4a7c59;color:#fff;text-decoration:none;padding:10px 16px;border-radius:24px;font-size:13px;font-weight:600;box-shadow:0 4px 14px rgba(0,0,0,.25)}
</style></head><body>
<div class="phone">
  <div class="header">
    <div class="header-text"><h2>{{ sarpanch }}</h2><p>{{ village }} Gram Panchayat</p></div>
  </div>
  <div class="chat" id="cb">
    <div class="dd"><span>Today</span></div>
    {% for r,t,ts in chat %}
    <div class="bw {{ r }}"><div class="bubble {{ r }}">{{ t|safe }}</div><div class="tl">{{ ts }}</div></div>
    {% endfor %}
  </div>
  {% if chips %}<form method="post" class="chips">
    {% for c in chips %}<button class="chip" type="submit" name="message" value="{{ c }}">{{ c }}</button>{% endfor %}
  </form>{% endif %}
  <form method="post" class="ir">
    <input type="text" name="message" placeholder="Type your message..." autocomplete="off" autofocus>
    <button type="submit" class="sb">&#10148;</button>
  </form>
</div>
<a href="/sarpanch" class="fab">Dashboard</a>
<script>document.getElementById('cb').scrollTop=99999;</script>
</body></html>"""

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
</style></head><body>
<div class="tb">
  <div class="tl">
    <div><h1>{{ village }} — Sarpanch Dashboard</h1><div class="ts">{{ sarpanch }} · {{ mandal }}</div></div>
  </div>
  <div style="font-size:12px;opacity:.8">Auto-refresh 20s · {{ now }}</div>
</div>
<div class="stats">
  <div class="sc c1"><div class="val">{{ c.pc }}</div><div class="lbl">Pending Complaints</div></div>
  <div class="sc c2"><div class="val">{{ c.cert }}</div><div class="lbl">Cert Requests</div></div>
  <div class="sc c3"><div class="val">{{ c.res }}</div><div class="lbl">Resolved</div></div>
  <div class="sc c4"><div class="val">{{ c.works }}</div><div class="lbl">Active Works</div></div>
  <div class="sc c5"><div class="val">{{ c.hi }}</div><div class="lbl">High Priority</div></div>
</div>
<div class="sec">
  <div class="sh">Complaints Queue <span>Pending + In Review + In Progress</span></div>
  {% set ac=complaints|selectattr("status","in",["pending","in_review","in_progress"])|list %}
  {% if ac %}<table><thead><tr><th>#</th><th>ID</th><th>Name</th><th>Category</th><th>Location</th><th>Priority</th><th>Filed</th><th>Status</th><th>Actions</th></tr></thead><tbody>
  {% for x in ac %}<tr>
    <td>{{ loop.index }}</td><td><strong>{{ x.id }}</strong></td>
    <td>{{ x.name }}<br><small style="color:#888">{{ x.phone }}</small></td>
    <td>{{ x.category }}</td><td>{{ x.location }}</td>
    <td class="p{{ x.priority[0] }}">{{ x.priority|upper }}</td>
    <td style="font-size:11px;color:#888">{{ x.filed_at }}</td>
    <td><span class="badge {{ x.status }}">{{ x.status.replace('_',' ').title() }}</span></td>
    <td><div class="acts">
      {% if x.status=='pending' %}<a href="/caction/{{ x.id }}/in_review" class="btn bb">Review</a>{% endif %}
      {% if x.status=='in_review' %}<a href="/caction/{{ x.id }}/in_progress" class="btn ba">Start</a>{% endif %}
      {% if x.status=='in_progress' %}<a href="/caction/{{ x.id }}/resolved" class="btn bg">Done</a>{% endif %}
      <a href="/caction/{{ x.id }}/rejected" class="btn br">X</a>
    </div></td>
  </tr>{% endfor %}</tbody></table>
  {% else %}<div class="empty">No active complaints!</div>{% endif %}
</div>
<div class="sec">
  <div class="sh">Certificate Requests <span>Pending + Processing</span></div>
  {% set ac=certs|selectattr("status","in",["pending","processing"])|list %}
  {% if ac %}</td><thead><tr><th>#</th><th>ID</th><th>Name</th><th>Type</th><th>Purpose</th><th>Filed</th><th>Status</th><th>Actions</th></tr></thead><tbody>
  {% for x in ac %}<tr>
    <td>{{ loop.index }}</td><td><strong>{{ x.id }}</strong></td>
    <td>{{ x.name }}<br><small style="color:#888">{{ x.phone }}</small></td>
    <td>{{ x.type }}</td><td>{{ x.purpose }}</td>
    <td style="font-size:11px;color:#888">{{ x.filed_at }}</td>
    <td><span class="badge {{ x.status }}">{{ x.status.title() }}</span></td>
    <td><div class="acts">
      {% if x.status=='pending' %}<a href="/certaction/{{ x.id }}/processing" class="btn bb">Process</a>{% endif %}
      {% if x.status=='processing' %}<a href="/certaction/{{ x.id }}/ready" class="btn bg">Ready</a>{% endif %}
      <a href="/certaction/{{ x.id }}/rejected" class="btn br">X</a>
    </div></td>
  </tr>{% endfor %}</tbody></table>
  {% else %}<div class="empty">No pending requests.</div>{% endif %}
</div>
<div class="sec">
  <div class="sh">Development Works</div>
  {% if works %}<table><thead><tr><th>ID</th><th>Title</th><th>Status</th><th>Updated</th><th>Actions</th></tr></thead><tbody>
  {% for w in works %}<tr>
    <td><strong>{{ w.id }}</strong></td><td>{{ w.title }}</td>
    <td><span class="badge {{ w.status }}">{{ w.status.replace('_',' ').title() }}</span></td>
    <td style="font-size:11px;color:#888">{{ w.updated }}</td>
    <td><div class="acts">
      {% if w.status=='pending' %}<a href="/waction/{{ w.id }}/in_progress" class="btn bb">Start</a>{% endif %}
      {% if w.status=='in_progress' %}<a href="/waction/{{ w.id }}/resolved" class="btn bg">Done</a>{% endif %}
      <a href="/waction/{{ w.id }}/rejected" class="btn br">X</a>
    </div></td>
  </tr>{% endfor %}</tbody></table>
  {% else %}<div class="empty">No works added.</div>{% endif %}
  <form method="post" action="/addwork" class="wf">
    <input type="text" name="title" placeholder="Add new work" required>
    <button type="submit">+ Add</button>
  </form>
</div>
<div class="sec">
  <div class="sh">Announcements</div>
  {% if announcements %}<table><thead><tr><th>Title</th><th>Message</th><th>Date</th></tr></thead><tbody>
  {% for a in announcements %}<tr>
    <td><strong>{{ a.title }}</strong></td><td>{{ a.body }}</td>
    <td style="font-size:11px;color:#888">{{ a.date }}</td>
  </tr>{% endfor %}</tbody></table>
  {% else %}<div class="empty">No announcements.</div>{% endif %}
  <form method="post" action="/announce" class="af">
    <input type="text" name="title" placeholder="Title" required>
    <input type="text" name="body" placeholder="Message..." required>
    <button type="submit">Post</button>
  </form>
</div>
<div class="sec">
  <div class="sh">Resolved / Closed</div>
  {% set dc=complaints|selectattr("status","in",["resolved","rejected"])|list %}
  {% set dce=certs|selectattr("status","in",["ready","rejected"])|list %}
  {% if dc or dce %}<table><thead><tr><th>ID</th><th>Type</th><th>Name</th><th>Details</th><th>Status</th></tr></thead><tbody>
  {% for x in dc %}<tr><td>{{ x.id }}</td><td>Complaint</td><td>{{ x.name }}</td><td>{{ x.category }}</td><td><span class="badge {{ x.status }}">{{ x.status.title() }}</span></td></tr>{% endfor %}
  {% for x in dce %}<tr><td>{{ x.id }}</td><td>Certificate</td><td>{{ x.name }}</td><td>{{ x.type }}</td><td><span class="badge {{ x.status }}">{{ x.status.title() }}</span></td></tr>{% endfor %}
  </tbody></table>
  {% else %}<div class="empty">No resolved items.</div>{% endif %}
</div>
</body></html>"""

# ── Run ──────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5006))
    print(f" Starting on port {port}")
    print(f" WhatsApp Business Number: +91 {PHONE_NUMBER_ID[-10:] if len(PHONE_NUMBER_ID) > 10 else '8008042801'}")
    app.run(host="0.0.0.0", port=port, debug=not DATABASE_URL)