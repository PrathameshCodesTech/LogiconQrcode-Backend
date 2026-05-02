# ATS Logicon — Server Knowledge Base

Complete deployment reference for `ats.vibecopilot.ai`.
Written on: 2026-05-02

---

## 1. Server Info

| Key | Value |
|-----|-------|
| IP | `139.5.188.191` |
| OS | Ubuntu 18.04.6 LTS |
| Domain | `ats.vibecopilot.ai` |
| SSH User | `root` |
| PEM File | `C:\Users\Prathmesh Marathe\Desktop\VibeCopilotPEMFiles\masheera-access` |

**SSH command:**
```bash
ssh -i "C:\Users\Prathmesh Marathe\Desktop\VibeCopilotPEMFiles\masheera-access" root@139.5.188.191
```

---

## 2. GitHub Repositories

| Repo | URL |
|------|-----|
| Backend | https://github.com/PrathameshCodesTech/LogiconQrcode-Backend |
| Frontend | https://github.com/PrathameshCodesTech/LogiconQrcode-Frontend |

---

## 3. Server Folder Structure

```
/var/www/ats-logicon/
├── backend/                  ← Django project (cloned from GitHub)
│   ├── venv/                 ← Python 3.11 virtual environment
│   ├── config/               ← Django settings, urls, wsgi
│   ├── accounts/             ← Auth app
│   ├── surveys/              ← Surveys app
│   ├── submissions/          ← Submissions app
│   ├── staticfiles/          ← Collected static files (from collectstatic)
│   ├── media/                ← Uploaded media files
│   ├── .env                  ← Production environment variables (NOT in git)
│   └── requirements.txt
└── frontend/                 ← React dist files (uploaded via scp)
    ├── index.html
    ├── assets/
    └── public files...
```

---

## 4. PostgreSQL Database

| Key | Value |
|-----|-------|
| Version | PostgreSQL 14 |
| Port | `5433` (PG10 is on 5432, PG14 on 5433) |
| Database | `ats_logicon` |
| User | `ats_logicon_user` |
| Password | `Ats@Logicon#2026!Secure` |
| Host | `localhost` |

> **Why port 5433?** This server runs two Postgres versions simultaneously. PG10 occupies the default port 5432. PG14 was installed later and assigned 5433 automatically.

**Connect to DB manually:**
```bash
sudo -u postgres psql -p 5433 -d ats_logicon
```

**Or as the app user:**
```bash
psql -h localhost -p 5433 -U ats_logicon_user -d ats_logicon
```

---

## 5. Python & Virtual Environment

| Key | Value |
|-----|-------|
| Python version | 3.11 (system-installed at `/usr/bin/python3.11`) |
| Venv location | `/var/www/ats-logicon/backend/venv/` |

> **Why Python 3.11?** Server is Ubuntu 18.04 — Python 3.12 could not be installed (deadsnakes PPA not available). Django 5.2.13 works with Python 3.11.

> **Why Django 5.2.13 and not 6.0.4?** Django 6.x requires Python >=3.12 which is not available on this server. Django 5.2.x is LTS (supported until 2028) and fully compatible with the codebase.

**Activate venv:**
```bash
cd /var/www/ats-logicon/backend
source venv/bin/activate
```

---

## 6. Production `.env` File

Location: `/var/www/ats-logicon/backend/.env`

```env
SECRET_KEY=7x#k2@9pLmQ!vRnT4wYsZ6cJdXeAuB3fGhNiOqPjKtMrWs8VyUo
DEBUG=False
FRONTEND_URL=https://ats.vibecopilot.ai
DB_NAME=ats_logicon
DB_USER=ats_logicon_user
DB_PASSWORD=Ats@Logicon#2026!Secure
DB_HOST=localhost
DB_PORT=5433
```

> This file is NOT in git. Must be created manually on any new server.

---

## 7. Gunicorn Service

| Key | Value |
|-----|-------|
| Service name | `ats-logicon` |
| Port | `127.0.0.1:8016` |
| Workers | 3 |
| Service file | `/etc/systemd/system/ats-logicon.service` |
| Access log | `/var/log/ats-logicon-access.log` |
| Error log | `/var/log/ats-logicon-error.log` |

**Service file content:**
```ini
[Unit]
Description=Gunicorn daemon for ATS Logicon
After=network.target

[Service]
User=root
Group=www-data
WorkingDirectory=/var/www/ats-logicon/backend
ExecStart=/var/www/ats-logicon/backend/venv/bin/gunicorn \
    --workers 3 \
    --bind 127.0.0.1:8016 \
    --access-logfile /var/log/ats-logicon-access.log \
    --error-logfile /var/log/ats-logicon-error.log \
    config.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

**Gunicorn commands:**
```bash
systemctl status ats-logicon       # check status
systemctl restart ats-logicon      # restart
systemctl stop ats-logicon         # stop
systemctl start ats-logicon        # start
journalctl -u ats-logicon -f       # live logs
```

---

## 8. Nginx Config

| Key | Value |
|-----|-------|
| Config file | `/etc/nginx/sites-available/ats.vibecopilot.ai` |
| Symlink | `/etc/nginx/sites-enabled/ats.vibecopilot.ai` |

**Routing:**
- `/` → serves `/var/www/ats-logicon/frontend/` (React SPA)
- `/api/` → proxied to Gunicorn on `127.0.0.1:8016`
- `/admin/` → proxied to Gunicorn on `127.0.0.1:8016`
- `/static/` → served from `/var/www/ats-logicon/backend/staticfiles/`
- `/media/` → served from `/var/www/ats-logicon/backend/media/`

**Nginx commands:**
```bash
nginx -t                           # test config syntax
systemctl reload nginx             # reload without downtime
systemctl restart nginx            # full restart
```

---

## 9. SSL Certificate

| Key | Value |
|-----|-------|
| Tool | Certbot (Let's Encrypt) |
| Certificate path | `/etc/letsencrypt/live/ats.vibecopilot.ai/fullchain.pem` |
| Key path | `/etc/letsencrypt/live/ats.vibecopilot.ai/privkey.pem` |
| Expires | 2026-07-31 (auto-renews via cron) |

**Renew manually if needed:**
```bash
certbot renew
```

---

## 10. Ports Used on This Server (Full Map)

| Port | Service |
|------|---------|
| 22 | SSH |
| 80 | Nginx (HTTP) |
| 443 | Nginx (HTTPS) |
| 5432 | PostgreSQL 10 |
| 5433 | PostgreSQL 14 |
| 5434 | PostgreSQL (another instance) |
| 6379 | Redis |
| 8000 | Python (other project) |
| 8001 | Gunicorn (other project) |
| 8002 | Gunicorn (other project) |
| 8003 | Gunicorn (other project) |
| 8005 | Python (other project) |
| 8006 | Gunicorn (other project) |
| 8008 | Gunicorn (other project) |
| 8009 | Gunicorn (other project) |
| 8010 | Gunicorn (other project) |
| 8013 | Gunicorn (other project) |
| 8014 | Gunicorn (other project) |
| 8015 | Gunicorn (other project) |
| **8016** | **Gunicorn — ATS Logicon (this project)** |

> Next available ports start at 8017+

---

## 11. How to Deploy Future Backend Changes

Every time backend code changes:

**Step 1 — On local machine, commit and push:**
```bash
cd backend/
git add .
git commit -m "your message"
git push origin main
```

**Step 2 — On server, pull and restart:**
```bash
ssh -i "C:\Users\Prathmesh Marathe\Desktop\VibeCopilotPEMFiles\masheera-access" root@139.5.188.191

cd /var/www/ats-logicon/backend
git pull origin main
source venv/bin/activate
pip install -r requirements.txt          # only if requirements changed
python manage.py migrate                 # only if there are new migrations
python manage.py collectstatic --noinput # only if static files changed
systemctl restart ats-logicon
```

---

## 12. How to Deploy Future Frontend Changes

Every time frontend code changes:

**Step 1 — On local machine, build:**
```bash
cd frontend/
npm run build
```

**Step 2 — Upload dist to server:**
```bash
scp -i "C:\Users\Prathmesh Marathe\Desktop\VibeCopilotPEMFiles\masheera-access" -r frontend/dist/. root@139.5.188.191:/var/www/ats-logicon/frontend/
```

> No server restart needed — Nginx serves static files directly.

---

## 13. Django Admin

URL: `https://ats.vibecopilot.ai/admin/`

**Create superuser (first time):**
```bash
cd /var/www/ats-logicon/backend
source venv/bin/activate
python manage.py createsuperuser
```

---

## 14. Useful Logs

```bash
# Gunicorn access log
tail -f /var/log/ats-logicon-access.log

# Gunicorn error log
tail -f /var/log/ats-logicon-error.log

# Nginx error log
tail -f /var/log/nginx/error.log

# Systemd service log
journalctl -u ats-logicon -f
```

---

## 15. Quick Health Check

```bash
# Is Gunicorn running?
systemctl status ats-logicon

# Is port 8016 listening?
ss -tlnp | grep 8016

# Is the API responding?
curl -s https://ats.vibecopilot.ai/api/ | head -c 200

# Is the DB accessible?
sudo -u postgres psql -p 5433 -c "\l" | grep ats_logicon
```
