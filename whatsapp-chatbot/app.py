from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
import requests
import sqlite3
import json
import re
from datetime import datetime
import uuid
import hashlib

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'

# ============================================
# CONFIGURATION
# ============================================

ACCESS_TOKEN = "EAAdlVJxjkxEBRaYycHCyhQRKej18Gxx59ZBQHb0D4wvf8ZAYfDBtpZAQh2LQ3yVeDS5ynXOe9fcldW3RMCuoo2IMpY5cmWkhPHSZAZB1dHmWHBhlZCZCeL4JWeQjCua3H5MGRVVQJIXYQjsqFyFCZAMa1bHDZCbZB3uilL2nKXZAf9bwOonB9e5TWIYdoSYXG7nngH2bL9vvKNeLoodqjmNt5Cnp6WiLVT5QEkUZAzN7QFZBtsj73vMl6sq83CNXeCQLJ57UaXXZBZC5QB6fF0EioZAkYBZBIOQZDZD"
PHONE_NUMBER_ID = "1169761576210394"
VERIFY_TOKEN = "SarpanchBot2025"

user_sessions = {}
VILLAGES = ['Kolukonda', 'Keesara', 'Ghatkesar', 'Pocharam', 'Jangaon', 'Hyderabad']

# ============================================
# DATABASE
# ============================================

def init_db():
    conn = sqlite3.connect('complaints.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS complaints (
        ticket_id TEXT PRIMARY KEY,
        citizen_number TEXT,
        citizen_name TEXT,
        village TEXT,
        complaint_text TEXT,
        category TEXT,
        location_lat REAL,
        location_lng REAL,
        maps_link TEXT,
        status TEXT,
        created_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS sarpanchs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        village_name TEXT
    )''')
    
    # Insert test sarpanch if not exists
    c.execute("SELECT * FROM sarpanchs WHERE username = 'kolukonda_sarpanch'")
    if not c.fetchone():
        c.execute("INSERT INTO sarpanchs (username, password, village_name) VALUES (?, ?, ?)",
                  ('kolukonda_sarpanch', hashlib.sha256('sarpanch123'.encode()).hexdigest(), 'Kolukonda'))
    
    conn.commit()
    conn.close()
    print(" Database initialized")

# ============================================
# MENUS
# ============================================

def get_main_menu():
    return """🏘️ *Namaskaram! Welcome to Gram Panchayat*

1️⃣ *Register a Complaint*
2️⃣ *Track Complaint Status*
3️⃣ *Government Schemes*
4️⃣ *Office Contact*

Reply with 1, 2, 3, or 4"""

def get_complaint_menu():
    return """📋 *Complaint Categories:*

1️⃣ *Street Light* 💡
2️⃣ *Water Problem* 💧
3️⃣ *Road Problem* 🛣️
4️⃣ *Garbage* 🗑️
5️⃣ *Other* 📝

Reply with 1, 2, 3, 4, or 5"""

# ============================================
# WEBHOOK
# ============================================

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode and token:
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            return challenge, 200
    return 'Verification failed', 403

@app.route('/webhook', methods=['POST'])
def handle_incoming():
    data = request.get_json()
    print("📨 Received webhook")
    
    try:
        entry = data.get('entry', [{}])[0]
        changes = entry.get('changes', [{}])[0]
        value = changes.get('value', {})
        messages = value.get('messages', [])
        
        for msg in messages:
            sender = msg.get('from')
            msg_type = msg.get('type')
            
            if sender not in user_sessions:
                user_sessions[sender] = {'step': 'menu'}
            
            if msg_type == 'text':
                text = msg.get('text', {}).get('body', '').strip()
                print(f" Text from {sender}: '{text}'")
                handle_text_message(sender, text)
            
            elif msg_type == 'location':
                lat = msg.get('location', {}).get('latitude')
                lng = msg.get('location', {}).get('longitude')
                print(f" Location from {sender}")
                handle_location_message(sender, lat, lng)
            
            else:
                send_whatsapp_message(sender, "Please send text or share your location.")
    
    except Exception as e:
        print(f" Error: {e}")
    
    return 'OK', 200

def handle_text_message(sender, text):
    session_data = user_sessions.get(sender, {'step': 'menu'})
    current_step = session_data.get('step', 'menu')
    
    if current_step == 'menu':
        if text.lower() in ['hi', 'hello', 'hey', 'start', 'menu']:
            send_whatsapp_message(sender, get_main_menu())
        elif text == '1':
            user_sessions[sender]['step'] = 'complaint_category'
            send_whatsapp_message(sender, get_complaint_menu())
        elif text == '2':
            user_sessions[sender]['step'] = 'track_ticket'
            send_whatsapp_message(sender, "🔍 *Track Complaint*\n\nSend your Ticket ID:")
        elif text == '3':
            send_whatsapp_message(sender, "📋 *Government Schemes*\n\n• PM Awas Yojana\n• MNREGA\n• PM Kisan\n• Ayushman Bharat")
        elif text == '4':
            send_whatsapp_message(sender, "🏛️ *Panchayat Office*\n📍 Main Road\n⏰ 10 AM - 5 PM")
        else:
            send_whatsapp_message(sender, get_main_menu())
    
    elif current_step == 'complaint_category':
        cats = {'1': 'Street Light', '2': 'Water Problem', '3': 'Road Problem', '4': 'Garbage', '5': 'Other'}
        if text in cats:
            user_sessions[sender]['category'] = cats[text]
            user_sessions[sender]['step'] = 'waiting_for_location'
            send_whatsapp_message(sender, f"✅ Category: {cats[text]}\n\n📍 Share your location (📎 → Location)")
        else:
            send_whatsapp_message(sender, get_complaint_menu())
    
    elif current_step == 'waiting_for_location':
        village = detect_village(text)
        if village != "Unknown":
            user_sessions[sender]['village'] = village
            user_sessions[sender]['step'] = 'waiting_for_name'
            send_whatsapp_message(sender, f"✅ Village: {village}\n\n📝 Send your name:")
        else:
            user_sessions[sender]['location_text'] = text
            user_sessions[sender]['step'] = 'waiting_for_name'
            send_whatsapp_message(sender, f"✅ Location: {text}\n\n📝 Send your name:")
    
    elif current_step == 'waiting_for_name':
        if len(text) >= 2:
            user_sessions[sender]['citizen_name'] = text
            save_complaint(sender, user_sessions[sender])
            user_sessions[sender] = {'step': 'menu'}
        else:
            send_whatsapp_message(sender, "📝 Please send your full name:")
    
    elif current_step == 'track_ticket':
        track_complaint(sender, text)
        user_sessions[sender] = {'step': 'menu'}

def handle_location_message(sender, lat, lng):
    session_data = user_sessions.get(sender, {'step': 'menu'})
    maps_link = f"https://maps.google.com/?q={lat},{lng}"
    session_data['location_lat'] = lat
    session_data['location_lng'] = lng
    session_data['maps_link'] = maps_link
    session_data['step'] = 'waiting_for_name'
    user_sessions[sender] = session_data
    send_whatsapp_message(sender, f"📍 Location received!\n\n📝 Send your name:")

def detect_village(text):
    for village in VILLAGES:
        if village.lower() in text.lower():
            return village
    return "Unknown"

def save_complaint(sender, data):
    ticket_id = f"TKT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4]}"
    
    conn = sqlite3.connect('complaints.db')
    c = conn.cursor()
    c.execute('''INSERT INTO complaints 
                 (ticket_id, citizen_number, citizen_name, village, complaint_text, category,
                  location_lat, location_lng, maps_link, status, created_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (ticket_id, sender, data.get('citizen_name', 'Unknown'),
               data.get('village', 'Unknown'), data.get('complaint_text', ''),
               data.get('category', 'General'),
               data.get('location_lat'), data.get('location_lng'),
               data.get('maps_link', ''), 'OPEN', datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    reply = f"""✅ *Complaint Registered!*

📋 *Ticket ID:* {ticket_id}
📍 *Village:* {data.get('village', 'Unknown')}
📂 *Category:* {data.get('category', 'General')}

Thank you!"""
    
    send_whatsapp_message(sender, reply)

def track_complaint(sender, ticket_id):
    conn = sqlite3.connect('complaints.db')
    c = conn.cursor()
    c.execute("SELECT status, created_at FROM complaints WHERE ticket_id = ? AND citizen_number = ?", 
              (ticket_id, sender))
    result = c.fetchone()
    conn.close()
    
    if result:
        status, created = result
        reply = f"🔍 *Status*\n📋 {ticket_id}\n📌 {status}\n📅 {created[:16]}"
    else:
        reply = f"❌ Ticket {ticket_id} not found"
    
    send_whatsapp_message(sender, reply)

def send_whatsapp_message(to_number, message):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to_number, "type": "text", "text": {"body": message}}
    try:
        r = requests.post(url, headers=headers, json=payload)
        print(f" Message sent to {to_number}")
        return r.json()
    except Exception as e:
        print(f" Error: {e}")
        return None

# ============================================
# DASHBOARD - FIXED VERSION
# ============================================

def login_required(f):
    def decorated(*args, **kwargs):
        if 'sarpanch_username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated.__name__ = f.__name__
    return decorated

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        hashed = hashlib.sha256(password.encode()).hexdigest()
        conn = sqlite3.connect('complaints.db')
        c = conn.cursor()
        c.execute("SELECT * FROM sarpanchs WHERE username = ? AND password = ?", (username, hashed))
        sarpanch = c.fetchone()
        conn.close()
        if sarpanch:
            session['sarpanch_username'] = sarpanch[1]
            session['sarpanch_village'] = sarpanch[3]
            return redirect(url_for('dashboard'))
        return render_template_string(LOGIN_TEMPLATE, error="Invalid credentials")
    return render_template_string(LOGIN_TEMPLATE, error=None)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def home():
    if 'sarpanch_username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    village = session.get('sarpanch_village', 'Unknown')
    conn = sqlite3.connect('complaints.db')
    c = conn.cursor()
    c.execute("SELECT * FROM complaints WHERE village = ? ORDER BY created_at DESC", (village,))
    rows = c.fetchall()
    complaints = rows if rows else []
    c.execute("SELECT COUNT(*) FROM complaints WHERE village = ?", (village,))
    total_row = c.fetchone()
    total = total_row[0] if total_row else 0
    c.execute("SELECT COUNT(*) FROM complaints WHERE village = ? AND status = 'OPEN'", (village,))
    open_row = c.fetchone()
    open_count = open_row[0] if open_row else 0
    conn.close()
    return render_template_string(DASHBOARD_TEMPLATE, 
                                   complaints=complaints, 
                                   village=village, 
                                   total=total, 
                                   open_count=open_count)

@app.route('/complaint/<ticket_id>')
@login_required
def view_complaint(ticket_id):
    village = session.get('sarpanch_village', 'Unknown')
    conn = sqlite3.connect('complaints.db')
    c = conn.cursor()
    c.execute("SELECT * FROM complaints WHERE ticket_id = ? AND village = ?", (ticket_id, village))
    row = c.fetchone()
    conn.close()
    if not row:
        return "Complaint not found", 404
    return render_template_string(COMPLAINT_TEMPLATE, complaint=row)

@app.route('/update_status', methods=['POST'])
@login_required
def update_status():
    ticket_id = request.form.get('ticket_id')
    new_status = request.form.get('status')
    conn = sqlite3.connect('complaints.db')
    c = conn.cursor()
    c.execute("UPDATE complaints SET status = ? WHERE ticket_id = ?", (new_status, ticket_id))
    conn.commit()
    conn.close()
    return redirect(url_for('view_complaint', ticket_id=ticket_id))

@app.route('/send_reply', methods=['POST'])
@login_required
def send_reply():
    ticket_id = request.form.get('ticket_id')
    reply_msg = request.form.get('reply_message')
    conn = sqlite3.connect('complaints.db')
    c = conn.cursor()
    c.execute("SELECT citizen_number FROM complaints WHERE ticket_id = ?", (ticket_id,))
    result = c.fetchone()
    conn.close()
    if result:
        send_whatsapp_message(result[0], f"📢 Update on {ticket_id}\n\n{reply_msg}")
    return redirect(url_for('view_complaint', ticket_id=ticket_id))

# ============================================
# TEMPLATES
# ============================================

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>Sarpanch Login</title>
<style>
body{font-family:Arial;display:flex;justify-content:center;align-items:center;height:100vh;background:#f0f2f5;margin:0}
.login-container{background:white;padding:30px;border-radius:10px;width:300px}
h2{color:#1a73e8;text-align:center}
input{width:100%;padding:10px;margin:10px 0;border:1px solid #ddd;border-radius:5px}
button{width:100%;padding:10px;background:#1a73e8;color:white;border:none;border-radius:5px;cursor:pointer}
</style>
</head>
<body>
<div class="login-container">
<h2>Sarpanch Login</h2>
<form method="POST">
<input type="text" name="username" placeholder="Username" required>
<input type="password" name="password" placeholder="Password" required>
<button type="submit">Login</button>
</form>
<p style="text-align:center">Test: kolukonda_sarpanch / sarpanch123</p>
</div>
</body>
</html>
"""

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>{{ village }} Dashboard</title>
<style>
body{font-family:Arial;margin:0;background:#f5f5f5}
.header{background:#1a73e8;color:white;padding:15px 20px;display:flex;justify-content:space-between}
.stats{display:flex;gap:15px;padding:20px}
.stat-card{background:white;padding:15px;border-radius:8px;flex:1;text-align:center}
.stat-number{font-size:28px;font-weight:bold;color:#1a73e8}
table{width:100%;border-collapse:collapse;background:white}
th,td{padding:12px;text-align:left;border-bottom:1px solid #ddd}
.container{padding:20px}
.logout{color:white;text-decoration:none;background:rgba(255,255,255,0.2);padding:8px 15px;border-radius:5px}
</style>
</head>
<body>
<div class="header">
<h2>{{ village }} Gram Panchayat</h2>
<a href="/logout" class="logout">Logout</a>
</div>
<div class="stats">
<div class="stat-card"><div class="stat-number">{{ total }}</div>Total</div>
<div class="stat-card"><div class="stat-number">{{ open_count }}</div>Open</div>
</div>
<div class="container">
<h3>Complaints</h3>
<table>
<tr><th>Ticket</th><th>Citizen</th><th>Category</th><th>Complaint</th><th>Status</th><th>Date</th><th>Action</th></tr>
{% for c in complaints %}
<tr>
<td>{{ c[0] }}</td>
<td>{{ c[2] }}</td>
<td>{{ c[5] }}</td>
<td>{{ c[4][:40] if c[4] else '' }}...</td>
<td>{{ c[9] }}</td>
<td>{{ c[10][:16] if c[10] else '' }}</td>
<td><a href="/complaint/{{ c[0] }}">View</a></td>
</tr>
{% endfor %}
</table>
{% if complaints|length == 0 %}
<p style="text-align:center;color:gray">No complaints yet</p>
{% endif %}
</div>
</body>
</html>
"""

COMPLAINT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>Complaint Details</title>
<style>
body{font-family:Arial;margin:0;background:#f5f5f5}
.header{background:#1a73e8;color:white;padding:15px}
.container{max-width:800px;margin:30px auto;background:white;padding:25px;border-radius:10px}
.field{margin-bottom:15px}
.label{font-weight:bold;width:150px;display:inline-block}
button{background:#1a73e8;color:white;border:none;padding:10px 20px;border-radius:5px;cursor:pointer}
.reply-box{width:100%;padding:10px;margin:10px 0;border:1px solid #ddd;border-radius:5px}
.back-btn{background:#666;color:white;padding:8px 15px;text-decoration:none;display:inline-block;margin-bottom:20px;border-radius:5px}
hr{margin:20px 0}
</style>
</head>
<body>
<div class="header"><h2>Complaint Details</h2></div>
<div class="container">
<a href="/dashboard" class="back-btn">← Back</a>
<div class="field"><span class="label">Ticket:</span> {{ complaint[0] }}</div>
<div class="field"><span class="label">Citizen:</span> {{ complaint[2] }}</div>
<div class="field"><span class="label">Phone:</span> {{ complaint[1] }}</div>
<div class="field"><span class="label">Village:</span> {{ complaint[3] }}</div>
<div class="field"><span class="label">Category:</span> {{ complaint[5] }}</div>
<div class="field"><span class="label">Status:</span> {{ complaint[9] }}</div>
<div class="field"><span class="label">Complaint:</span><br><div style="background:#f8f9fa;padding:15px;border-radius:5px">{{ complaint[4] }}</div></div>
<hr>
<h3>Update Status</h3>
<form method="POST" action="/update_status">
<input type="hidden" name="ticket_id" value="{{ complaint[0] }}">
<select name="status">
<option value="OPEN">Open</option>
<option value="IN_PROGRESS">In Progress</option>
<option value="RESOLVED">Resolved</option>
</select>
<textarea name="notes" placeholder="Notes..." rows="2" style="width:100%;margin:10px 0"></textarea>
<button type="submit">Update</button>
</form>
<hr>
<h3>Send Reply</h3>
<form method="POST" action="/send_reply">
<input type="hidden" name="ticket_id" value="{{ complaint[0] }}">
<textarea name="reply_message" class="reply-box" rows="4" placeholder="Type your reply..."></textarea>
<button type="submit">Send Reply</button>
</form>
</div>
</body>
</html>
"""

# ============================================
# RUN
# ============================================

if __name__ == '__main__':
    init_db()
    print("=" * 50)
    print(" WhatsApp Chatbot Running")
    print("=" * 50)
    print(" URL: http://localhost:5001")
    print(" Dashboard: http://localhost:5001/login")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5001, debug=True)