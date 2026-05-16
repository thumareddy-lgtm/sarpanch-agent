import os
# ============================================================
#  Village Sarpanch WhatsApp Agent — Production-Grade Demo
#  Run:  pip install flask twilio
#        python sarpanch_app.py
#  Open: http://127.0.0.1:5006          (Villager web chat)
#        http://127.0.0.1:5006/sarpanch (Sarpanch dashboard)
#  WhatsApp webhook: POST /whatsapp
# ============================================================

from flask import Flask, request, render_template_string, redirect, session
from datetime import datetime
from twilio.twiml.messaging_response import MessagingResponse
import uuid


import sqlite3
try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    psycopg2 = None

def get_db():
    if DATABASE_URL:
        try:
            conn = psycopg2.connect(DATABASE_URL)
            conn.cursor_factory = psycopg2.extras.RealDictCursor
            return conn, "pg"
        except Exception as e:
            print(f"PG failed: {e}")
    conn = sqlite3.connect("sarpanch.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn, "sqlite"

def init_db():
    conn, db_type = get_db()
    cur = conn.cursor()
    u = "updated" if db_type == "pg" else "updated_at"
    cur.execute(f"""CREATE TABLE IF NOT EXISTS complaints (
        id TEXT PRIMARY KEY, name TEXT, phone TEXT, category TEXT,
        description TEXT, location TEXT, priority TEXT DEFAULT 'medium',
        status TEXT DEFAULT 'pending', filed_at TEXT, {u} TEXT, notes TEXT DEFAULT '')""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS certificates (
        id TEXT PRIMARY KEY, type TEXT, name TEXT, father TEXT, phone TEXT,
        purpose TEXT, status TEXT DEFAULT 'pending', filed_at TEXT, {u} TEXT, notes TEXT DEFAULT '')""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS works (
        id TEXT PRIMARY KEY, title TEXT, status TEXT DEFAULT 'pending', {u} TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS announcements (
        id """ + ("SERIAL" if db_type=="pg" else "INTEGER") + """ PRIMARY KEY """ + ("" if db_type=="pg" else "AUTOINCREMENT") + """, title TEXT, body TEXT, date TEXT)""")
    conn.commit(); conn.close()
    print(f"Database ready ({db_type})")

init_db()

app = Flask(__name__)
DATABASE_URL  = os.environ.get("DATABASE_URL",  "")

app.secret_key = "sarpanch_secret_2024_vG7#nQ"

# ── Twilio config ─────────────────────────────────────────────
TWILIO_ACCOUNT_SID = "ACd7034ab5ba6937b1351944abfa59e171"
TWILIO_SANDBOX_NUM = "whatsapp:+14155238886"
# Villagers join by sending: join news-badly  to +1 415 523 8886

# ── In-memory store ───────────────────────────────────────────
complaints:   dict[str, dict] = {}
certificates: dict[str, dict] = {}
works:        dict[str, dict] = {}
announcements: list[dict]     = []
whatsapp_sessions: dict[str, dict] = {}
_counter = 1000

# ── Village config ────────────────────────────────────────────
VILLAGE_NAME   = "Ramapuram Village"
SARPANCH_NAME  = "Sri Ravi Kumar"
MANDAL         = "Nalgonda Mandal"
DISTRICT       = "Nalgonda District, Telangana"

# ─────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────

def new_id(prefix=""):
    global _counter
    _counter += 1
    short = str(uuid.uuid4())[:6].upper()
    return f"{prefix}{short}"

def fmt_time():
    return datetime.now().strftime("%H:%M")

def fmt_dt():
    return datetime.now().strftime("%d-%b-%Y %H:%M")

# ─────────────────────────────────────────────────────────────
#  Bot brain — bilingual (Telugu + English)
# ─────────────────────────────────────────────────────────────

MENU_EN = (
    "Namaskaram! 🙏 Welcome to *{village}* Gram Panchayat\n"
    "Sarpanch: {sarpanch}\n\n"
    "What do you need help with?\n\n"
    "1️⃣  Register a Complaint\n"
    "2️⃣  Request a Certificate\n"
    "3️⃣  Track my Complaint / Request\n"
    "4️⃣  Check Government Schemes\n"
    "5️⃣  Development Work Status\n"
    "6️⃣  View Announcements\n"
    "7️⃣  Panchayat Office Info\n\n"
    "Reply with number or type your request.\n"
    "తెలుగులో కావాలంటే *telugu* అని పంపండి."
).format(village=VILLAGE_NAME, sarpanch=SARPANCH_NAME)

MENU_TE = (
    "నమస్కారం! 🙏 *{village}* గ్రామ పంచాయతీకి స్వాగతం\n"
    "సర్పంచ్: {sarpanch}\n\n"
    "మీకు ఏమి కావాలి?\n\n"
    "1️⃣  ఫిర్యాదు నమోదు చేయండి\n"
    "2️⃣  సర్టిఫికెట్ అభ్యర్థన\n"
    "3️⃣  ఫిర్యాదు / అభ్యర్థన స్థితి తనిఖీ\n"
    "4️⃣  ప్రభుత్వ పథకాలు తనిఖీ చేయండి\n"
    "5️⃣  అభివృద్ధి పనుల స్థితి\n"
    "6️⃣  ప్రకటనలు చూడండి\n"
    "7️⃣  పంచాయతీ కార్యాలయ సమాచారం\n\n"
    "For English type *english*"
).format(village=VILLAGE_NAME, sarpanch=SARPANCH_NAME)

COMPLAINT_CATEGORIES = {
    "1": "Road / Pothole",
    "2": "Water Supply",
    "3": "Electricity / Street Light",
    "4": "Drainage / Sanitation",
    "5": "Ration Shop Issue",
    "6": "Land / Property Dispute",
    "7": "Other",
}

CERTIFICATE_TYPES = {
    "1": "Income Certificate",
    "2": "Caste Certificate",
    "3": "Residence / Domicile Certificate",
    "4": "Birth Certificate",
    "5": "Death Certificate",
    "6": "Agriculture Land Certificate",
}

SCHEMES = [
    ("Rythu Bandhu", "Financial support ₹5,000/acre/season for farmers. Eligibility: Land-owning farmers in Telangana."),
    ("PM Awas Yojana", "Free house for BPL families. Eligibility: No pucca house, annual income < ₹3 lakh."),
    ("Aarogyasri", "Free medical treatment up to ₹5 lakh/year. Eligibility: White/Pink ration card holders."),
    ("Kalyana Lakshmi", "₹1,00,116 assistance for marriage of girl from SC/ST/BC/Minority families."),
    ("PM Kisan", "₹6,000/year to small farmers in 3 instalments. Eligibility: Farmers with < 2 hectares."),
    ("NREGA", "100 days guaranteed employment at ₹250+/day. Eligibility: Any rural household adult."),
    ("Bhadratha", "Free LPG connection + subsidy for BPL families. Eligibility: BPL ration card holders."),
]

STATUS_EMOJI = {
    "pending":     "⏳ Pending",
    "in_review":   "🔵 In Review",
    "in_progress": "🔨 In Progress",
    "resolved":    "✅ Resolved",
    "rejected":    "❌ Rejected",
    "ready":       "📄 Ready for Collection",
    "processing":  "🔄 Processing",
}

PRIORITY_EMOJI = {
    "low":    "🟢 Low",
    "medium": "🟡 Medium",
    "high":   "🔴 High",
}


def get_menu(ctx):
    return MENU_TE if ctx.get("lang") == "te" else MENU_EN


def bot_reply(user_msg: str, ctx: dict) -> tuple[str, dict]:
    msg     = user_msg.strip()
    msg_low = msg.lower()
    state   = ctx.get("state", "idle")
    lang    = ctx.get("lang", "en")

    # ── Language switch ──────────────────────────────────────
    if msg_low == "telugu":
        ctx["lang"] = "te"
        ctx["state"] = "idle"
        return MENU_TE, ctx
    if msg_low == "english":
        ctx["lang"] = "en"
        ctx["state"] = "idle"
        return MENU_EN, ctx

    # ── Global resets ────────────────────────────────────────
    if msg_low in ("menu", "home", "back", "hi", "hello", "hey", "start", "help",
                   "నమస్కారం", "హలో", "మెనూ"):
        ctx = {"state": "idle", "lang": lang}
        return get_menu(ctx), ctx

    # ═══════════════════════════════════════════════════════
    #  IDLE — Intent detection
    # ═══════════════════════════════════════════════════════
    if state == "idle":

        # ── COMPLAINT ───────────────────────────────────────
        if msg_low in ("1", "complaint", "register complaint", "ఫిర్యాదు"):
            ctx["state"] = "complaint_name"
            return (
                "📋 *Register a Complaint*\n\n"
                "Please enter your *full name*:\n"
                "(మీ పూర్తి పేరు టైప్ చేయండి)"
            ), ctx

        # ── CERTIFICATE ─────────────────────────────────────
        if msg_low in ("2", "certificate", "cert", "సర్టిఫికెట్"):
            cats = "\n".join(f"  {k}. {v}" for k, v in CERTIFICATE_TYPES.items())
            ctx["state"] = "cert_type"
            return (
                "📄 *Certificate Request*\n\n"
                "Select certificate type:\n\n"
                f"{cats}"
            ), ctx

        # ── TRACK STATUS ─────────────────────────────────────
        if msg_low in ("3", "track", "status", "check", "స్థితి"):
            ctx["state"] = "track_id"
            return (
                "🔍 *Track your Complaint / Request*\n\n"
                "Enter your *Reference ID*:\n"
                "(e.g. CMP-A3F9B2 or CERT-X7K2P1)"
            ), ctx

        # ── SCHEMES ──────────────────────────────────────────
        if msg_low in ("4", "schemes", "scheme", "పథకాలు", "yojana"):
            lines = []
            for i, (name, desc) in enumerate(SCHEMES, 1):
                lines.append(f"*{i}. {name}*\n   {desc}\n")
            ctx["state"] = "idle"
            return (
                "🏛️ *Government Schemes — Quick Guide*\n\n" +
                "\n".join(lines) +
                "\nType *menu* for more options."
            ), ctx

        # ── WORKS STATUS ─────────────────────────────────────
        if msg_low in ("5", "works", "work", "road", "water", "electricity", "పనులు"):
            if not works:
                ctx["state"] = "idle"
                return (
                    "🚧 *Development Works*\n\n"
                    "No active works found in the system.\n"
                    "Contact Panchayat office for details.\n\n"
                    "Type *menu* to go back."
                ), ctx
            lines = []
            for w in list(works.values())[-5:]:
                st = STATUS_EMOJI.get(w["status"], w["status"])
                lines.append(f"🔹 *{w['title']}*\n   Status: {st}\n   Updated: {w['updated']}")
            ctx["state"] = "idle"
            return "🚧 *Active Development Works:*\n\n" + "\n\n".join(lines) + "\n\nType *menu* for more.", ctx

        # ── ANNOUNCEMENTS ────────────────────────────────────
        if msg_low in ("6", "announcements", "news", "ప్రకటనలు"):
            ctx["state"] = "idle"
            if not announcements:
                return "📢 No announcements at this time.\n\nType *menu* for more.", ctx
            lines = []
            for a in announcements[-3:]:
                lines.append(f"📢 *{a['title']}*\n{a['body']}\n_{a['date']}_")
            return "📢 *Latest Announcements:*\n\n" + "\n\n".join(lines) + "\n\nType *menu* for more.", ctx

        # ── OFFICE INFO ──────────────────────────────────────
        if msg_low in ("7", "info", "office", "contact", "కార్యాలయం"):
            ctx["state"] = "idle"
            return (
                f"🏛️ *{VILLAGE_NAME} Gram Panchayat*\n\n"
                f"👤 Sarpanch: {SARPANCH_NAME}\n"
                f"📍 {MANDAL}, {DISTRICT}\n"
                f"🕐 Office Hours: Mon–Sat, 10 AM – 5 PM\n"
                f"📞 Helpline: 1800-425-0066 (Toll Free)\n"
                f"📞 CM Helpline: 1100\n"
                f"🚨 Emergency: 112\n\n"
                "Type *menu* for more options."
            ), ctx

        return "🤖 Please choose from the menu:\n\n" + get_menu(ctx), ctx

    # ═══════════════════════════════════════════════════════
    #  COMPLAINT FLOW
    # ═══════════════════════════════════════════════════════
    if state == "complaint_name":
        if len(msg.strip()) < 2:
            return "⚠️ Please enter a valid name.", ctx
        ctx["c_name"]  = msg.title()
        ctx["state"]   = "complaint_phone"
        return f"Hello *{ctx['c_name']}*! 😊\n\nEnter your *mobile number*:", ctx

    if state == "complaint_phone":
        if not (msg.isdigit() and len(msg) >= 10):
            return "⚠️ Enter a valid 10-digit mobile number.", ctx
        ctx["c_phone"] = msg
        ctx["state"]   = "complaint_cat"
        cats = "\n".join(f"  {k}. {v}" for k, v in COMPLAINT_CATEGORIES.items())
        return (
            "📋 *Select complaint category:*\n\n"
            f"{cats}"
        ), ctx

    if state == "complaint_cat":
        if msg not in COMPLAINT_CATEGORIES:
            return "⚠️ Please choose 1–7.", ctx
        ctx["c_cat"]  = COMPLAINT_CATEGORIES[msg]
        ctx["state"]  = "complaint_desc"
        return (
            f"Category: *{ctx['c_cat']}*\n\n"
            "Now describe your complaint in detail:\n"
            "(సమస్యను వివరంగా రాయండి)"
        ), ctx

    if state == "complaint_desc":
        if len(msg) < 5:
            return "⚠️ Please describe the issue in at least a few words.", ctx
        ctx["c_desc"]   = msg
        ctx["state"]    = "complaint_location"
        return "📍 Enter your *exact location / street name* in the village:", ctx

    if state == "complaint_location":
        ctx["c_loc"] = msg
        ctx["state"] = "complaint_priority"
        return (
            "⚡ How urgent is this issue?\n\n"
            "  1. 🟢 Low — Can wait a few days\n"
            "  2. 🟡 Medium — Need attention soon\n"
            "  3. 🔴 High — Immediate action needed"
        ), ctx

    if state == "complaint_priority":
        pmap = {"1": "low", "2": "medium", "3": "high"}
        if msg not in pmap:
            return "⚠️ Please reply 1, 2, or 3.", ctx
        priority = pmap[msg]
        ref_id   = new_id("CMP-")
        complaint = {
            "id":       ref_id,
            "name":     ctx["c_name"],
            "phone":    ctx["c_phone"],
            "category": ctx["c_cat"],
            "desc":     ctx["c_desc"],
            "location": ctx["c_loc"],
            "priority": priority,
            "status":   "pending",
            "filed_at": fmt_dt(),
            "updated":  fmt_dt(),
            "notes":    "",
        }
        complaints[ref_id] = complaint
        ctx = {"state": "idle", "lang": lang}
        return (
            "✅ *Complaint Registered Successfully!*\n\n"
            f"👤 Name      : {complaint['name']}\n"
            f"📋 Category  : {complaint['category']}\n"
            f"📍 Location  : {complaint['location']}\n"
            f"⚡ Priority  : {PRIORITY_EMOJI[priority]}\n"
            f"🆔 *Reference ID: {ref_id}*\n\n"
            "⚠️ _Please save your Reference ID to track status._\n"
            "Expected resolution: 3–7 working days.\n\n"
            "Type *menu* for more options."
        ), ctx

    # ═══════════════════════════════════════════════════════
    #  CERTIFICATE FLOW
    # ═══════════════════════════════════════════════════════
    if state == "cert_type":
        if msg not in CERTIFICATE_TYPES:
            return "⚠️ Please choose 1–6.", ctx
        ctx["cert_type"] = CERTIFICATE_TYPES[msg]
        ctx["state"]     = "cert_name"
        return (
            f"Certificate: *{ctx['cert_type']}*\n\n"
            "Enter applicant's *full name*:"
        ), ctx

    if state == "cert_name":
        ctx["cert_name"] = msg.title()
        ctx["state"]     = "cert_father"
        return "Enter *father's / husband's name*:", ctx

    if state == "cert_father":
        ctx["cert_father"] = msg.title()
        ctx["state"]       = "cert_phone"
        return "Enter your *mobile number*:", ctx

    if state == "cert_phone":
        if not (msg.isdigit() and len(msg) >= 10):
            return "⚠️ Enter a valid 10-digit mobile number.", ctx
        ctx["cert_phone"] = msg
        ctx["state"]      = "cert_purpose"
        return "What is the *purpose* of this certificate?\n(e.g. Bank loan, School admission, Job application):", ctx

    if state == "cert_purpose":
        ref_id = new_id("CERT-")
        cert = {
            "id":       ref_id,
            "type":     ctx["cert_type"],
            "name":     ctx["cert_name"],
            "father":   ctx["cert_father"],
            "phone":    ctx["cert_phone"],
            "purpose":  msg,
            "status":   "pending",
            "filed_at": fmt_dt(),
            "updated":  fmt_dt(),
            "notes":    "",
        }
        certificates[ref_id] = cert
        ctx = {"state": "idle", "lang": lang}
        return (
            "✅ *Certificate Request Submitted!*\n\n"
            f"👤 Name       : {cert['name']}\n"
            f"📄 Type       : {cert['type']}\n"
            f"🎯 Purpose    : {cert['purpose']}\n"
            f"🆔 *Reference ID: {ref_id}*\n\n"
            "⚠️ _Save your Reference ID._\n"
            "Processing time: 5–7 working days.\n"
            "Collect from Panchayat office with Aadhaar card.\n\n"
            "Type *menu* for more options."
        ), ctx

    # ═══════════════════════════════════════════════════════
    #  TRACK STATUS FLOW
    # ═══════════════════════════════════════════════════════
    if state == "track_id":
        ref_id = msg.upper().strip()
        ctx["state"] = "idle"

        record = complaints.get(ref_id) or certificates.get(ref_id)
        if not record:
            return (
                f"❌ Reference ID *{ref_id}* not found.\n\n"
                "Please check the ID and try again.\n"
                "Type *menu* for more options."
            ), ctx

        st = STATUS_EMOJI.get(record["status"], record["status"])

        if ref_id.startswith("CMP"):
            pr = PRIORITY_EMOJI.get(record.get("priority","low"), "")
            return (
                f"📋 *Complaint Status*\n\n"
                f"👤 Name      : {record['name']}\n"
                f"📋 Category  : {record['category']}\n"
                f"📍 Location  : {record['location']}\n"
                f"⚡ Priority  : {pr}\n"
                f"📅 Filed On  : {record['filed_at']}\n"
                f"🔄 Updated   : {record['updated']}\n"
                f"Status      : {st}\n"
                + (f"📝 Notes     : {record['notes']}\n" if record['notes'] else "") +
                "\nType *menu* for more options."
            ), ctx

        if ref_id.startswith("CERT"):
            return (
                f"📄 *Certificate Request Status*\n\n"
                f"👤 Name      : {record['name']}\n"
                f"📄 Type      : {record['type']}\n"
                f"🎯 Purpose   : {record['purpose']}\n"
                f"📅 Filed On  : {record['filed_at']}\n"
                f"🔄 Updated   : {record['updated']}\n"
                f"Status      : {st}\n"
                + (f"📝 Notes     : {record['notes']}\n" if record['notes'] else "") +
                "\nType *menu* for more options."
            ), ctx

    # Catch-all
    ctx["state"] = "idle"
    return "🤖 Sorry, I didn't understand. Let's start over.\n\n" + get_menu(ctx), ctx


# ─────────────────────────────────────────────────────────────
#  HTML Templates
# ─────────────────────────────────────────────────────────────

CHAT_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ village }} — Gram Panchayat</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Inter', sans-serif; background: #d9dbdd; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
  .phone { width: 390px; height: 760px; background: #fff; border-radius: 24px; box-shadow: 0 24px 64px rgba(0,0,0,.25); display: flex; flex-direction: column; overflow: hidden; }
  .header { background: #4a7c59; padding: 14px 16px 12px; display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
  .avatar { width: 40px; height: 40px; background: #6aab7a; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0; }
  .header-text h2 { color: #fff; font-size: 14px; font-weight: 600; }
  .header-text p  { color: #c5dfc9; font-size: 11px; margin-top: 2px; }
  .chat { flex: 1; overflow-y: auto; padding: 12px 10px; background: #efeae2; display: flex; flex-direction: column; gap: 6px; }
  .bubble-wrap { display: flex; flex-direction: column; }
  .bubble-wrap.user { align-items: flex-end; }
  .bubble-wrap.bot  { align-items: flex-start; }
  .bubble { max-width: 78%; padding: 8px 12px; border-radius: 12px; font-size: 13px; line-height: 1.55; white-space: pre-wrap; word-break: break-word; }
  .bubble.user { background: #dcf8c6; border-bottom-right-radius: 2px; }
  .bubble.bot  { background: #fff; border-bottom-left-radius: 2px; box-shadow: 0 1px 2px rgba(0,0,0,.1); }
  .time-label  { font-size: 10px; color: #999; margin-top: 2px; padding: 0 4px; }
  .date-divider { text-align: center; margin: 8px 0; }
  .date-divider span { background: #d4e8d7; color: #555; font-size: 11px; padding: 3px 10px; border-radius: 8px; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; padding: 6px 10px 0; background: #f8f9fa; }
  .chip { background: #eaf3ec; border: 1px solid #4a7c59; color: #2d5a3d; font-size: 12px; padding: 4px 10px; border-radius: 14px; cursor: pointer; font-family: inherit; }
  .chip:hover { background: #c5dfc9; }
  .input-row { display: flex; align-items: center; gap: 8px; padding: 10px; background: #f0f0f0; border-top: 1px solid #ddd; flex-shrink: 0; }
  .input-row input { flex: 1; border: none; background: #fff; border-radius: 22px; padding: 10px 16px; font-size: 14px; font-family: inherit; outline: none; box-shadow: 0 1px 3px rgba(0,0,0,.1); }
  .send-btn { width: 44px; height: 44px; background: #4a7c59; border: none; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 18px; }
  .send-btn:hover { background: #3a6348; }
  .fab-link { position: fixed; bottom: 24px; right: 24px; background: #4a7c59; color: #fff; text-decoration: none; padding: 10px 16px; border-radius: 24px; font-size: 13px; font-weight: 600; box-shadow: 0 4px 14px rgba(0,0,0,.25); }
</style>
</head>
<body>
<div class="phone">
  <div class="header">
    <div class="avatar">🏛️</div>
    <div class="header-text">
      <h2>{{ village }} Gram Panchayat</h2>
      <p>Sarpanch: {{ sarpanch }} · Online</p>
    </div>
  </div>
  <div class="chat" id="chatBox">
    <div class="date-divider"><span>Today</span></div>
    {% for role, text, ts in chat %}
    <div class="bubble-wrap {{ role }}">
      <div class="bubble {{ role }}">{{ text | safe }}</div>
      <div class="time-label">{{ ts }}</div>
    </div>
    {% endfor %}
  </div>
  {% if chips %}
  <form method="post" class="chips">
    {% for chip in chips %}
    <button class="chip" type="submit" name="message" value="{{ chip }}">{{ chip }}</button>
    {% endfor %}
  </form>
  {% endif %}
  <form method="post" class="input-row">
    <input type="text" name="message" placeholder="Type your message…" autocomplete="off" autofocus>
    <button type="submit" class="send-btn">➤</button>
  </form>
</div>
<a href="/sarpanch" class="fab-link">🏛️ Sarpanch View</a>
<script>
  document.getElementById('chatBox').scrollTop = 99999;
  document.querySelectorAll('.bubble.bot').forEach(el => {
    el.innerHTML = el.innerHTML.replace(/\*(.+?)\*/g, '<strong>$1</strong>').replace(/_(.+?)_/g, '<em>$1</em>');
  });
</script>
</body>
</html>
"""

SARPANCH_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="20">
<title>{{ village }} — Sarpanch Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root { --green: #4a7c59; --red: #c0392b; --blue: #0070f3; --amber: #e07b00; --grey: #f4f5f7; --border: #dfe1e6; --text: #172b4d; --sub: #6b778c; }
  body { font-family: 'DM Sans', sans-serif; background: #f0f2f5; color: var(--text); }
  .topbar { background: var(--green); color: #fff; padding: 0 28px; height: 58px; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 2px 8px rgba(0,0,0,.12); }
  .topbar h1 { font-size: 16px; font-weight: 700; }
  .topbar-sub { font-size: 12px; opacity: .8; }
  .stats { display: flex; gap: 12px; padding: 18px 28px 0; flex-wrap: wrap; }
  .stat-card { background: #fff; border-radius: 10px; padding: 14px 20px; flex: 1; min-width: 120px; box-shadow: 0 1px 4px rgba(0,0,0,.06); }
  .stat-card .val { font-size: 26px; font-weight: 700; }
  .stat-card .lbl { font-size: 11px; color: var(--sub); margin-top: 2px; }
  .stat-card.c1 .val { color: var(--amber); }
  .stat-card.c2 .val { color: var(--blue); }
  .stat-card.c3 .val { color: var(--green); }
  .stat-card.c4 .val { color: #7b2d8b; }
  .stat-card.c5 .val { color: var(--red); }
  .section { margin: 18px 28px; background: #fff; border-radius: 12px; box-shadow: 0 1px 4px rgba(0,0,0,.06); overflow: hidden; }
  .section-head { padding: 12px 18px; border-bottom: 1px solid var(--border); font-weight: 600; font-size: 14px; display: flex; justify-content: space-between; align-items: center; background: var(--grey); }
  .section-head span { font-weight: 400; color: var(--sub); font-size: 12px; }
  table { width: 100%; border-collapse: collapse; }
  th { padding: 9px 14px; font-size: 11px; color: var(--sub); text-align: left; background: var(--grey); border-bottom: 1px solid var(--border); font-weight: 600; }
  td { padding: 11px 14px; font-size: 13px; border-bottom: 1px solid var(--border); vertical-align: middle; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: #fafafa; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 20px; font-size: 11px; font-weight: 600; }
  .badge.pending    { background: #fff4e0; color: var(--amber); }
  .badge.in_review  { background: #dbeafe; color: var(--blue); }
  .badge.in_progress { background: #e0e7ff; color: #4338ca; }
  .badge.resolved   { background: #dcfce7; color: var(--green); }
  .badge.rejected   { background: #fee2e2; color: var(--red); }
  .badge.ready      { background: #dcfce7; color: var(--green); }
  .badge.processing { background: #dbeafe; color: var(--blue); }
  .pri-high   { color: var(--red); font-weight: 700; }
  .pri-medium { color: var(--amber); font-weight: 600; }
  .pri-low    { color: var(--green); }
  .actions { display: flex; gap: 5px; flex-wrap: wrap; }
  .btn { padding: 4px 10px; border-radius: 5px; font-size: 11px; font-weight: 600; text-decoration: none; cursor: pointer; border: none; font-family: inherit; display: inline-block; }
  .btn-blue   { background: var(--blue); color: #fff; }
  .btn-green  { background: var(--green); color: #fff; }
  .btn-red    { background: var(--red); color: #fff; }
  .btn-amber  { background: var(--amber); color: #fff; }
  .btn-grey   { background: #dfe1e6; color: var(--text); }
  .empty { text-align: center; padding: 28px; color: var(--sub); font-size: 13px; }
  .announce-form { padding: 16px 18px; border-top: 1px solid var(--border); display: flex; gap: 8px; }
  .announce-form input { flex: 1; border: 1px solid var(--border); border-radius: 6px; padding: 8px 12px; font-family: inherit; font-size: 13px; }
  .announce-form button { background: var(--green); color: #fff; border: none; border-radius: 6px; padding: 8px 16px; cursor: pointer; font-weight: 600; font-size: 13px; }
  .work-form { padding: 16px 18px; border-top: 1px solid var(--border); display: flex; gap: 8px; flex-wrap: wrap; }
  .work-form input, .work-form select { border: 1px solid var(--border); border-radius: 6px; padding: 8px 12px; font-family: inherit; font-size: 13px; }
  .work-form input { flex: 2; min-width: 160px; }
  .work-form select { flex: 1; min-width: 120px; }
  .work-form button { background: var(--green); color: #fff; border: none; border-radius: 6px; padding: 8px 16px; cursor: pointer; font-weight: 600; }
  @media (max-width: 700px) { .stats { gap: 8px; padding: 12px 12px 0; } .section { margin: 12px; } td, th { padding: 8px; } table { display: block; overflow-x: auto; } }
</style>
</head>
<body>

<div class="topbar">
  <h1>🏛️ {{ village }} — Sarpanch Dashboard &nbsp;|&nbsp; {{ sarpanch }}</h1>
  <div class="topbar-sub">{{ mandal }} · Auto-refreshes every 20s · {{ now }}</div>
</div>

<!-- Stats -->
<div class="stats">
  <div class="stat-card c1"><div class="val">{{ counts.pending_complaints }}</div><div class="lbl">Pending Complaints</div></div>
  <div class="stat-card c2"><div class="val">{{ counts.pending_certs }}</div><div class="lbl">Cert. Requests</div></div>
  <div class="stat-card c3"><div class="val">{{ counts.resolved }}</div><div class="lbl">Resolved Today</div></div>
  <div class="stat-card c4"><div class="val">{{ counts.works }}</div><div class="lbl">Active Works</div></div>
  <div class="stat-card c5"><div class="val">{{ counts.high_priority }}</div><div class="lbl">High Priority</div></div>
</div>

<!-- Complaints -->
<div class="section">
  <div class="section-head">📋 Complaints Queue <span>Pending + In Review + In Progress</span></div>
  {% set active_complaints = complaints | selectattr("status", "in", ["pending","in_review","in_progress"]) | sort(attribute="filed_at") | list %}
  {% if active_complaints %}
  <table>
    <thead><tr><th>#</th><th>ID</th><th>Name</th><th>Category</th><th>Location</th><th>Priority</th><th>Filed</th><th>Status</th><th>Actions</th></tr></thead>
    <tbody>
    {% for c in active_complaints %}
    <tr>
      <td>{{ loop.index }}</td>
      <td><strong>{{ c.id }}</strong></td>
      <td>{{ c.name }}<br><small style="color:#888">{{ c.phone }}</small></td>
      <td>{{ c.category }}</td>
      <td>{{ c.location }}</td>
      <td class="pri-{{ c.priority }}">{{ c.priority | upper }}</td>
      <td style="font-size:11px;color:#888">{{ c.filed_at }}</td>
      <td><span class="badge {{ c.status }}">{{ c.status.replace('_',' ').title() }}</span></td>
      <td>
        <div class="actions">
          {% if c.status == 'pending' %}<a href="/caction/{{ c.id }}/review" class="btn btn-blue">🔍 Review</a>{% endif %}
          {% if c.status == 'in_review' %}<a href="/caction/{{ c.id }}/progress" class="btn btn-amber">🔨 Start</a>{% endif %}
          {% if c.status == 'in_progress' %}<a href="/caction/{{ c.id }}/resolved" class="btn btn-green">✓ Resolve</a>{% endif %}
          <a href="/caction/{{ c.id }}/rejected" class="btn btn-red">✕ Reject</a>
        </div>
      </td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
  {% else %}<div class="empty">🎉 No active complaints!</div>{% endif %}
</div>

<!-- Certificates -->
<div class="section">
  <div class="section-head">📄 Certificate Requests <span>Pending + Processing</span></div>
  {% set active_certs = certs | selectattr("status", "in", ["pending","processing"]) | sort(attribute="filed_at") | list %}
  {% if active_certs %}
  <table>
    <thead><tr><th>#</th><th>ID</th><th>Name</th><th>Father's Name</th><th>Type</th><th>Purpose</th><th>Filed</th><th>Status</th><th>Actions</th></tr></thead>
    <tbody>
    {% for c in active_certs %}
    <tr>
      <td>{{ loop.index }}</td>
      <td><strong>{{ c.id }}</strong></td>
      <td>{{ c.name }}<br><small style="color:#888">{{ c.phone }}</small></td>
      <td>{{ c.father }}</td>
      <td>{{ c.type }}</td>
      <td>{{ c.purpose }}</td>
      <td style="font-size:11px;color:#888">{{ c.filed_at }}</td>
      <td><span class="badge {{ c.status }}">{{ c.status.title() }}</span></td>
      <td>
        <div class="actions">
          {% if c.status == 'pending' %}<a href="/certaction/{{ c.id }}/processing" class="btn btn-blue">🔄 Process</a>{% endif %}
          {% if c.status == 'processing' %}<a href="/certaction/{{ c.id }}/ready" class="btn btn-green">✓ Ready</a>{% endif %}
          <a href="/certaction/{{ c.id }}/rejected" class="btn btn-red">✕ Reject</a>
        </div>
      </td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
  {% else %}<div class="empty">No pending certificate requests.</div>{% endif %}
</div>

<!-- Development Works -->
<div class="section">
  <div class="section-head">🚧 Development Works <span>Track village infrastructure projects</span></div>
  {% if works %}
  <table>
    <thead><tr><th>ID</th><th>Work Title</th><th>Status</th><th>Last Updated</th><th>Actions</th></tr></thead>
    <tbody>
    {% for w in works %}
    <tr>
      <td><strong>{{ w.id }}</strong></td>
      <td>{{ w.title }}</td>
      <td><span class="badge {{ w.status }}">{{ w.status.replace('_',' ').title() }}</span></td>
      <td style="font-size:11px;color:#888">{{ w.updated }}</td>
      <td>
        <div class="actions">
          {% if w.status == 'pending' %}<a href="/waction/{{ w.id }}/in_progress" class="btn btn-blue">▶ Start</a>{% endif %}
          {% if w.status == 'in_progress' %}<a href="/waction/{{ w.id }}/resolved" class="btn btn-green">✓ Done</a>{% endif %}
          <a href="/waction/{{ w.id }}/rejected" class="btn btn-red">✕ Cancel</a>
        </div>
      </td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
  {% else %}<div class="empty">No development works added yet.</div>{% endif %}
  <!-- Add new work -->
  <form method="post" action="/addwork" class="work-form">
    <input type="text" name="title" placeholder="Work title (e.g. Repair Main Road near Temple)" required>
    <button type="submit">+ Add Work</button>
  </form>
</div>

<!-- Announcements -->
<div class="section">
  <div class="section-head">📢 Announcements <span>Broadcast to villagers</span></div>
  {% if announcements %}
  <table>
    <thead><tr><th>Title</th><th>Message</th><th>Date</th></tr></thead>
    <tbody>
    {% for a in announcements | reverse %}
    <tr>
      <td><strong>{{ a.title }}</strong></td>
      <td>{{ a.body }}</td>
      <td style="font-size:11px;color:#888">{{ a.date }}</td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
  {% else %}<div class="empty">No announcements yet.</div>{% endif %}
  <form method="post" action="/announce" class="announce-form">
    <input type="text" name="title" placeholder="Title (e.g. Village Meeting)" required>
    <input type="text" name="body" placeholder="Announcement message…" required>
    <button type="submit">📢 Post</button>
  </form>
</div>

<!-- History -->
<div class="section">
  <div class="section-head">✅ Resolved / Closed <span>Complaints + Certificates</span></div>
  {% set done_complaints = complaints | selectattr("status", "in", ["resolved","rejected"]) | list %}
  {% set done_certs = certs | selectattr("status", "in", ["ready","rejected"]) | list %}
  {% if done_complaints or done_certs %}
  <table>
    <thead><tr><th>ID</th><th>Type</th><th>Name</th><th>Details</th><th>Status</th></tr></thead>
    <tbody>
    {% for c in done_complaints %}
    <tr>
      <td>{{ c.id }}</td><td>Complaint</td><td>{{ c.name }}</td>
      <td>{{ c.category }} — {{ c.location }}</td>
      <td><span class="badge {{ c.status }}">{{ c.status.title() }}</span></td>
    </tr>
    {% endfor %}
    {% for c in done_certs %}
    <tr>
      <td>{{ c.id }}</td><td>Certificate</td><td>{{ c.name }}</td>
      <td>{{ c.type }}</td>
      <td><span class="badge {{ c.status }}">{{ c.status.title() }}</span></td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
  {% else %}<div class="empty">No resolved items yet.</div>{% endif %}
</div>

</body>
</html>
"""

# ─────────────────────────────────────────────────────────────
#  Routes — Villager Chat
# ─────────────────────────────────────────────────────────────

QUICK_CHIPS = ["1 Complaint", "2 Certificate", "3 Track Status", "4 Schemes", "5 Works", "6 Announcements"]

@app.route("/", methods=["GET", "POST"])
def chat_view():
    if "chat" not in session:
        session["chat"] = []
        session["ctx"]  = {"state": "idle", "lang": "en"}
        session["chat"].append(("bot", MENU_EN, fmt_time()))
        session.modified = True

    chips = QUICK_CHIPS if session["ctx"].get("state") == "idle" else []

    if request.method == "POST":
        user_msg = request.form.get("message", "").strip()
        if not user_msg:
            return redirect("/")
        session["chat"].append(("user", user_msg, fmt_time()))
        reply, new_ctx = bot_reply(user_msg, dict(session["ctx"]))
        session["ctx"]  = new_ctx
        session["chat"].append(("bot", reply, fmt_time()))
        session.modified = True
        chips = QUICK_CHIPS if session["ctx"].get("state") == "idle" else []

    session["chat"] = session["chat"][-80:]
    return render_template_string(
        CHAT_HTML,
        chat=session["chat"],
        chips=chips,
        village=VILLAGE_NAME,
        sarpanch=SARPANCH_NAME,
    )


# ─────────────────────────────────────────────────────────────
#  Routes — Sarpanch Dashboard
# ─────────────────────────────────────────────────────────────

@app.route("/sarpanch")
def sarpanch_view():
    counts = {
        "pending_complaints": sum(1 for c in complaints.values() if c["status"] in ("pending","in_review","in_progress")),
        "pending_certs":      sum(1 for c in certificates.values() if c["status"] in ("pending","processing")),
        "resolved":           sum(1 for c in list(complaints.values()) + list(certificates.values()) if c["status"] in ("resolved","ready")),
        "works":              sum(1 for w in works.values() if w["status"] in ("pending","in_progress")),
        "high_priority":      sum(1 for c in complaints.values() if c.get("priority") == "high" and c["status"] not in ("resolved","rejected")),
    }
    return render_template_string(
        SARPANCH_HTML,
        complaints=list(complaints.values()),
        certs=list(certificates.values()),
        works=list(works.values()),
        announcements=announcements,
        village=VILLAGE_NAME,
        sarpanch=SARPANCH_NAME,
        mandal=MANDAL,
        now=datetime.now().strftime("%d %b %Y, %H:%M"),
        counts=counts,
    )


@app.route("/caction/<ref_id>/<action>")
def complaint_action(ref_id, action):
    c = complaints.get(ref_id.upper())
    if c:
        status_map = {"review": "in_review", "progress": "in_progress", "resolved": "resolved", "rejected": "rejected"}
        c["status"]  = status_map.get(action, action)
        c["updated"] = fmt_dt()
    return redirect("/sarpanch")


@app.route("/certaction/<ref_id>/<action>")
def cert_action(ref_id, action):
    c = certificates.get(ref_id.upper())
    if c:
        c["status"]  = action
        c["updated"] = fmt_dt()
    return redirect("/sarpanch")


@app.route("/waction/<ref_id>/<action>")
def work_action(ref_id, action):
    w = works.get(ref_id.upper())
    if w:
        w["status"]  = action
        w["updated"] = fmt_dt()
    return redirect("/sarpanch")


@app.route("/addwork", methods=["POST"])
def add_work():
    title = request.form.get("title", "").strip()
    if title:
        ref_id = new_id("WORK-")
        works[ref_id] = {
            "id":      ref_id,
            "title":   title,
            "status":  "pending",
            "updated": fmt_dt(),
        }
    return redirect("/sarpanch")


@app.route("/announce", methods=["POST"])
def post_announcement():
    title = request.form.get("title", "").strip()
    body  = request.form.get("body", "").strip()
    if title and body:
        announcements.append({
            "title": title,
            "body":  body,
            "date":  fmt_dt(),
        })
    return redirect("/sarpanch")


# ─────────────────────────────────────────────────────────────
#  WhatsApp Webhook
# ─────────────────────────────────────────────────────────────

@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    user_msg = request.form.get("Body", "").strip()
    sender   = request.form.get("From", "")
    if not user_msg:
        return "", 204
    if sender not in whatsapp_sessions:
        whatsapp_sessions[sender] = {"state": "idle", "lang": "en"}
    reply, whatsapp_sessions[sender] = bot_reply(user_msg, whatsapp_sessions[sender])
    resp = MessagingResponse()
    resp.message(reply)
    return str(resp), 200, {"Content-Type": "text/xml"}


@app.route("/sessions")
def sessions_view():
    rows = "".join(
        f"<tr><td>{p}</td><td>{c.get('state','?')}</td><td>{c.get('lang','en')}</td></tr>"
        for p, c in whatsapp_sessions.items()
    )
    return f"""<html><body style='font-family:monospace;padding:20px'>
    <h3>Active WhatsApp Sessions ({len(whatsapp_sessions)})</h3>
    <table border=1 cellpadding=8>
    <tr><th>Phone</th><th>State</th><th>Language</th></tr>
    {rows or '<tr><td colspan=3>No sessions yet</td></tr>'}
    </table><br><a href='/sarpanch'>← Sarpanch Dashboard</a>
    </body></html>"""


# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n  {'='*54}")
    print(f"   {VILLAGE_NAME} — Sarpanch WhatsApp Agent")
    print(f"  {'='*54}")
    print(f"  Villager web chat  :  http://127.0.0.1:5006")
    print(f"  Sarpanch dashboard :  http://127.0.0.1:5006/sarpanch")
    print(f"  Sessions debug     :  http://127.0.0.1:5006/sessions")
    print(f"  WhatsApp webhook   :  POST /whatsapp  (via ngrok)")
    print(f"  {'='*54}")
    print(f"\n  Villagers join sandbox — send on WhatsApp:")
    print(f"  'join news-badly'  →  +1 415 523 8886\n")
    app.run(host="0.0.0.0", port=5006, debug=True)
# updated
