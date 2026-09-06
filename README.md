<!-- HEADER / HERO SECTION -->
<div align="center">

# Hangarin
### `Task & To-Do Manager` • Built with Django

[![Live Demo](https://img.shields.io/badge/Admin_Dashboard-%2310B981?style=for-the-badge&logo=django&logoColor=white)](#getting-started)
[![Made by](https://img.shields.io/badge/Made_by-Jhon_Grover_Longsud-%23131F33?style=for-the-badge&logo=github&logoColor=10B981)](mailto:jhongroverlonsud@gmail.com)

![Python](https://img.shields.io/badge/Python-3.11+-2D6A4F?style=flat-square&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.2-1B4332?style=flat-square&logo=django&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-DB-40916C?style=flat-square&logo=sqlite&logoColor=white)
![Faker](https://img.shields.io/badge/Faker-seed_data-74C69D?style=flat-square)

---
</div>

## 📋 About

Hangarin is a task and to-do manager built to keep daily work from slipping
through the cracks. Tasks carry a deadline, a status, a priority, and a
category, and each one can be broken down into subtasks and backed by notes —
so the big picture and the small steps live in the same place.

---

## ✨ Features

<table>
  <tr>
    <td width="50%" valign="top">
      <h3 align="center">✅ Tasks</h3>
      <p>Every task tracks a title, description, deadline, and status (Pending / In Progress / Completed), tied to a Priority and Category.</p>
    </td>
    <td width="50%" valign="top">
      <h3 align="center">🧩 Subtasks</h3>
      <p>Break a task into smaller steps, each with its own status, so nothing large feels unmanageable.</p>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3 align="center">📝 Notes</h3>
      <p>Attach context, reminders, or updates directly to the task they belong to.</p>
    </td>
    <td width="50%" valign="top">
      <h3 align="center">🏷️ Priorities &amp; Categories</h3>
      <p>Sort work by urgency (High, Medium, Low, Critical, Optional) and by area of life (Work, School, Personal, Finance, Projects).</p>
    </td>
  </tr>
</table>

The admin dashboard is themed green end to end, with filtering and search
wired up for every model — Tasks by status, priority, or category; SubTasks
by status; Notes by date; Categories and Priorities by name.

---

## 🛠️ Tech Stack

| Layer | Tool |
|---|---|
| Framework | Django 5.2 |
| Database | SQLite |
| Seed data | Faker |
| Styling | Custom CSS (green theme, landing page + admin) |
| Deployment | PythonAnywhere |

---

<a name="getting-started"></a>
## 🚀 Getting Started

### 1. Virtual environment

```bash
cd hangarin
python3 -m venv venv

# activate it
source venv/bin/activate      # macOS/Linux
venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

### 2. Database & migrations

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

### 3. Seed data

Priorities and Categories are seeded manually (five of each), and Tasks,
SubTasks, and Notes are generated with Faker — one command handles all of it:

```bash
python manage.py populate_data
```

Optional flags for more or less data:

```bash
python manage.py populate_data --tasks 30 --subtasks-per-task 4 --notes-per-task 3
```

### 4. Run it

```bash
python manage.py runserver
```

- `http://127.0.0.1:8000/` — the landing page
- `http://127.0.0.1:8000/admin/` — the dashboard, log in with the superuser you created

---

## 🌱 Version Control

```bash
git init
git add .
git commit -m "Initial commit: Hangarin task manager"
git remote add origin <your-repo-url>
git branch -M main
git push -u origin main
```

`db.sqlite3` and `venv/` are already in `.gitignore`, so your local database
and virtual environment never get committed.

---

## ☁️ Deploying to PythonAnywhere

1. Open a **Bash console** on PythonAnywhere and clone the repo:
   ```bash
   git clone <your-repo-url>
   cd hangarin
   ```
2. Create a virtualenv and install dependencies:
   ```bash
   mkvirtualenv --python=/usr/bin/python3.11 hangarin-venv
   pip install -r requirements.txt
   ```
3. Migrate and seed:
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   python manage.py populate_data
   ```
4. On the **Web** tab, add a new web app with **Manual configuration**,
   matching Python version, and set the virtualenv path, e.g.
   `/home/yourusername/.virtualenvs/hangarin-venv`.
5. Edit the **WSGI configuration file** to point at this project:
   ```python
   import os
   import sys

   path = '/home/yourusername/hangarin'
   if path not in sys.path:
       sys.path.insert(0, path)

   os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hangarin.settings')

   from django.core.wsgi import get_wsgi_application
   application = get_wsgi_application()
   ```
6. In `hangarin/settings.py`, set `ALLOWED_HOSTS = ['yourusername.pythonanywhere.com']`
   and switch `DEBUG = False` once things are confirmed working.
7. Map static URL `/static/` to `/home/yourusername/hangarin/staticfiles`,
   then run:
   ```bash
   python manage.py collectstatic
   ```
8. Hit **Reload** and open your `.pythonanywhere.com` URL.

Whenever you push new commits, `git pull` on the console, re-run
`migrate`/`collectstatic` if needed, and reload again.

---

## 📬 Contact

<div align="center">

Questions, feedback, or just want to say hi? Reach out.

📬 **Email:** [jhongroverlonsud@gmail.com](mailto:jhongroverlonsud@gmail.com)

</div>

---

<div align="center">
  <sub>&copy; 2026 Jhon Grover Longsud. All rights reserved.</sub>
</div>
