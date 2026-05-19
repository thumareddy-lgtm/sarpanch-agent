import os, uuid, sqlite3
from datetime import datetime
from flask import Flask, request, render_template_string, redirect, session

# ── Config ───────────────────────────────────────────────────
VILLAGE_NAME  = os.environ.get("VILLAGE_NAME",  "Kolukonda Village")
SARPANCH_NAME = os.environ.get("SARPANCH_NAME", "Kothi Sravanthi Praveen")
MANDAL        = os.environ.get("MANDAL",        "Jangaon Mandal")
DISTRICT      = os.environ.get("DISTRICT",      "Nalgonda District, Telangana")
DATABASE_URL  = os.environ.get("DATABASE_URL",  "")
PHOTO_B64     = "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"

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
    print(f"✅ Database ready ({db_type})")

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
    cur.execute(f"INSERT INTO works (id,title,status,{u}) VALUES ({p},{p},{p},{p})", (new_id("WORK-"),title,"pending",now_str()))
    conn.commit(); conn.close()

def insert_announcement(title, body):
    conn, db_type = get_db(); cur = conn.cursor()
    p = "%s" if db_type == "pg" else "?"
    cur.execute(f"INSERT INTO announcements (title,body,date) VALUES ({p},{p},{p})", (title,body,now_str()))
    conn.commit(); conn.close()

# ── Bot ───────────────────────────────────────────────────────
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
    if ml in ("menu","home","back","hi","hello","start","help"): ctx={"state":"idle","lang":lang}; return get_menu(ctx),ctx

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

# ── HTML ──────────────────────────────────────────────────────
CHAT_HTML = r"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ village }}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',sans-serif;background:#d9dbdd;min-height:100vh;display:flex;align-items:center;justify-content:center}
.phone{width:390px;height:760px;background:#fff;border-radius:24px;box-shadow:0 24px 64px rgba(0,0,0,.25);display:flex;flex-direction:column;overflow:hidden}
.header{background:#4a7c59;padding:12px 16px;display:flex;align-items:center;gap:10px;flex-shrink:0}
.avatar{width:44px;height:44px;border-radius:50%;object-fit:cover;border:2px solid rgba(255,255,255,.5)}
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
    <img class="avatar" src="data:image/jpeg;base64,{{ photo }}" alt="">
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
.ta{width:42px;height:42px;border-radius:50%;object-fit:cover;border:2px solid rgba(255,255,255,.4)}
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
    <img class="ta" src="data:image/jpeg;base64,{{ photo }}" alt="">
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
  {% if ac %}<table><thead><tr><th>#</th><th>ID</th><th>Name</th><th>Type</th><th>Purpose</th><th>Filed</th><th>Status</th><th>Actions</th></tr></thead><tbody>
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
        village=VILLAGE_NAME,sarpanch=SARPANCH_NAME,photo=PHOTO_B64)

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
        c=counts,photo=PHOTO_B64)

@app.route("/debug")
def debug():
    try:
        conn,db_type=get_db(); cur=conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM complaints")
        row=cur.fetchone(); conn.close()
        cnt=row["cnt"] if isinstance(row,dict) else row[0]
        return f"DB: {db_type} | DATABASE_URL set: {bool(DATABASE_URL)} | Complaints: {cnt}"
    except Exception as e:
        return f"Error: {e} | DATABASE_URL set: {bool(DATABASE_URL)}"

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

VERIFY_TOKEN   = os.environ.get("VERIFY_TOKEN", "kolukonda2024")
META_TOKEN     = os.environ.get("META_TOKEN", "")
PHONE_NUM_ID   = os.environ.get("PHONE_NUMBER_ID", "1173815852473279")

def send_meta_whatsapp(to, text):
    import requests
    if not META_TOKEN:
        print("META_TOKEN not set")
        return
    requests.post(
        f"https://graph.facebook.com/v19.0/{PHONE_NUM_ID}/messages",
        headers={"Authorization": f"Bearer {META_TOKEN}", "Content-Type": "application/json"},
        json={"messaging_product":"whatsapp","to":to,"type":"text","text":{"body":text}}
    )

@app.route("/whatsapp", methods=["GET","POST"])
def whatsapp():
    # Meta webhook verification
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge","")
        return "Invalid token", 403

    # Incoming message from Meta
    try:
        data = request.json
        entry = data.get("entry",[{}])[0]
        changes = entry.get("changes",[{}])[0]
        value = changes.get("value",{})
        messages = value.get("messages",[])
        if not messages:
            return "OK", 200
        msg = messages[0]
        sender = msg.get("from","")
        if msg.get("type") != "text":
            return "OK", 200
        user_msg = msg["text"]["body"].strip()
        if not user_msg:
            return "OK", 200
        if sender not in whatsapp_sessions:
            whatsapp_sessions[sender] = {"state":"idle","lang":"en"}
        reply, whatsapp_sessions[sender] = bot_reply(user_msg, whatsapp_sessions[sender])
        send_meta_whatsapp(sender, reply)
    except Exception as e:
        print(f"Webhook error: {e}")
    return "OK", 200

@app.route("/sessions")
def sessions():
    rows="".join(f"<tr><td>{p}</td><td>{c.get('state','?')}</td><td>{c.get('lang','en')}</td></tr>" for p,c in whatsapp_sessions.items())
    return f"<html><body style='font-family:monospace;padding:20px'><h3>Sessions ({len(whatsapp_sessions)})</h3><table border=1 cellpadding=8><tr><th>Phone</th><th>State</th><th>Lang</th></tr>{rows or '<tr><td colspan=3>None</td></tr>'}</table><br><a href='/sarpanch'>Dashboard</a></body></html>"

if __name__=="__main__":
    init_db()
    port=int(os.environ.get("PORT",5006))
    print(f"Starting on port {port}")
    app.run(host="0.0.0.0",port=port,debug=not DATABASE_URL)
