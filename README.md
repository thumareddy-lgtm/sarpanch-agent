# 🏛️ Village Gram Panchayat — WhatsApp Agent

A WhatsApp-based village governance system for Gram Panchayats.
Built with Python, Flask, Twilio, and PostgreSQL.

## Features
- 🗣️ Bilingual — Telugu + English
- 📋 Complaint registration with priority levels
- 📄 Certificate requests (income, caste, residence, birth, death)
- 🔍 Real-time status tracking by Reference ID
- 🏛️ Government schemes information (Rythu Bandhu, Aarogyasri, etc.)
- 🚧 Development works tracker
- 📢 Announcements broadcast
- 👨‍💼 Sarpanch dashboard with photo
- 💾 PostgreSQL (production) / SQLite (local) database

## Quick Start

```bash
pip install -r requirements.txt
python sarpanch_app.py
```

Open: http://127.0.0.1:5006

## Environment Variables

Copy `.env.example` to `.env` and fill in your values.

| Variable | Description |
|---|---|
| VILLAGE_NAME | Your village name |
| SARPANCH_NAME | Sarpanch's name |
| MANDAL | Mandal name |
| DATABASE_URL | PostgreSQL URL (leave blank for SQLite) |
| SECRET_KEY | Flask session secret |
| SARPANCH_PASS | Dashboard password |

## WhatsApp Setup (Twilio)

1. Create account at twilio.com
2. Go to Messaging → Try it out → Send a WhatsApp message
3. Set webhook URL: `https://your-domain.com/whatsapp`
4. Villagers join by sending `join <sandbox-code>` to +1 415 523 8886

## Deploy to Render.com

1. Push this code to GitHub
2. Create new Web Service on render.com
3. Connect your GitHub repo
4. Add environment variables
5. Add PostgreSQL database
6. Deploy!

## Customise Per Village

Change these 3 lines in `sarpanch_app.py` or set environment variables:

```python
VILLAGE_NAME  = "Your Village Name"
SARPANCH_NAME = "Sarpanch Name"
MANDAL        = "Your Mandal"
```

## License
MIT
