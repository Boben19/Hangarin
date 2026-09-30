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
so the big picture and the small steps live in the same place. Each person
also gets a progress page with streaks, levels, a weekly chart and badges.

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
| Installable app | django-pwa (manifest and service worker) |
| Deployment | PythonAnywhere |

---

## Accounts, progress and profile

Everything sits behind a login. You can sign up with a username and
password, or with Google, Facebook or GitHub. Tasks (and their subtasks and
notes) belong to the account that made them, so people only ever see their
own list. Categories and priorities come as shared defaults, and anyone can
add their own on top.

**My progress** (the profile page) shows:

- level and XP (tasks are worth 10, subtasks 3, notes 1 up to 30)
- current and best streak, and how this week compares to last week
- a 7 day bar chart and a 12 week activity grid, plus the weekday you finish the most on
- a daily goal ring (you set the number in **Edit profile**)
- completion by category, your recent wins, and badges to unlock

**Edit profile** lets you change your name, username, picture (PNG, JPG or
WebP, cropped square), a short bio, your daily goal and light/dark/device
theme. From there you can also change your password, manage email addresses,
download all your tasks as a CSV, or delete your account and everything in it.

Small touches: confetti when you finish something (bigger for a level up or
hitting your daily goal), a light/dark switch that follows you between
devices, and keyboard shortcuts (`N` new task, `/` search, `?` for the list).
Animations switch themselves off if your device asks for reduced motion.

---

## 🔑 Signing in with GitHub

The "Continue with GitHub" button only shows up once the GitHub keys are in
`.env`, so a half-finished setup never sends anyone to a broken page.

1. On GitHub go to **Settings → Developer settings → OAuth Apps → New OAuth App**.
2. Homepage URL: `http://127.0.0.1:8000`
   Authorization callback URL: `http://127.0.0.1:8000/accounts/github/login/callback/`
3. Click **Generate a new client secret**, then copy the Client ID and the
   secret into `.env` as `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET`.
4. Restart `runserver`. The button now appears on the login and signup pages.

GitHub lets one OAuth app have several redirect URIs, so add the live site's
(`https://boben19.pythonanywhere.com/accounts/github/login/callback/`) to the
same app and use the same keys in the `.env` on the server.

A new GitHub user gets an account named after their GitHub username (with a
number added if it's taken), and their email is read from GitHub even if it's
set to private. If that email already belongs to a password account, they
aren't logged into it automatically. They're sent to a short form instead.

---

## 📱 Installing it as an app

Hangarin is a Progressive Web App, built with `django-pwa`. Browsers can
install it like a normal app (own window, own icon, no address bar), and if
the connection drops you get a friendly offline page instead of a browser error.

How it's wired up:

- `pwa` is in `INSTALLED_APPS`, and the `PWA_APP_*` settings in `settings.py`
  describe the app (name, colours, icons)
- `path('', include('pwa.urls'))` in `hangarin/urls.py` serves `/manifest.json`
  and `/serviceworker.js`
- `{% progressive_web_app_meta %}` sits in the `<head>` of `base.html` and `base_auth.html`
- `static/js/serviceworker.js` keeps the CSS, JS and icons, and shows `/offline/`
  when a page can't be loaded
- `static/js/pwa.js` registers the service worker and runs the **Install Hangarin**
  button in the sidebar. It's a separate file because the site's
  Content-Security-Policy doesn't allow inline scripts.

Good to know:

- Pages with your tasks are **not** cached. They're private and change all
  the time, and a saved copy would still be there after logging out on a
  shared computer. Offline you see the offline page, not old data.
- It needs `https://` or `localhost`. PythonAnywhere is https already.
- Changed a CSS or JS file and the old one still shows? Bump `VERSION` at the top
  of `serviceworker.js`.
- The icons are in `static/img/` (192, 512 and 180 px). Swap in your own
  files with the same names if you want a different look.

To try it: run the site, open it in Chrome, then **DevTools → Application**.
*Manifest* shows the name and icons and *Service Workers* shows the worker as
activated. Stop `runserver` and reload to see the offline page. To install,
use the icon at the right end of the address bar or the button in the
sidebar. On iPhone: Share → Add to Home Screen.

---

<a name="getting-started"></a>
## 🚀 Getting Started

### 1. Virtual environment

```bash
cd Hangarin
python3 -m venv .venv

# activate it
source .venv/bin/activate      # macOS/Linux
.venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

### 2. Settings file

```bash
cp .env.example .env           # copy .env.example .env on Windows
```

Open `.env` and add a secret key. Generate one with:

```bash
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```

Paste only that output after `DJANGO_SECRET_KEY=`. For local work also add
`DJANGO_DEBUG=True`. The site will not start on the live server with a
missing, short or placeholder key, on purpose.

### 3. Database

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 4. Seed data (optional)

Priorities and categories are added as shared defaults, and Tasks, SubTasks
and Notes are generated with Faker for one account:

```bash
python manage.py populate_data --username yourname
python manage.py populate_data --username yourname --tasks 30 --subtasks-per-task 4 --notes-per-task 3
```

### 5. Run it

```bash
python manage.py runserver
```

- `http://127.0.0.1:8000/` is the app (sign up or log in first)
- `http://127.0.0.1:8000/admin/` is the admin, use the superuser from step 3

---

## 🌱 Version Control

```bash
git add .
git commit -m "Describe what you changed"
git push
```

`.env`, `db.sqlite3`, `media/` and any `.venv*` folder are in `.gitignore`,
so secrets, your local data and uploaded pictures never get committed.

---

## ☁️ Deploying to PythonAnywhere

1. In a **Bash console**, get the code and make a virtualenv:
   ```bash
   git clone <your-repo-url> Hangarin
   cd Hangarin
   mkvirtualenv --python=/usr/bin/python3.11 hangarin-venv
   pip install -r requirements.txt
   ```
2. Create the `.env` file on the server (`cp .env.example .env`, then edit it).
   Set a **new** `DJANGO_SECRET_KEY` there, different from your laptop's.
   Leave `DJANGO_DEBUG` out. If you use your own domain, set
   `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` too.
3. Set up the database and static files:
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   python manage.py collectstatic
   ```
4. On the **Web** tab, add a web app with **Manual configuration**, set the
   virtualenv path (`/home/yourusername/.virtualenvs/hangarin-venv`) and the
   source/working directory (`/home/yourusername/Hangarin`).
5. In the WSGI file:
   ```python
   import os
   import sys

   path = '/home/yourusername/Hangarin'
   if path not in sys.path:
       sys.path.insert(0, path)

   os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hangarin.settings')

   from django.core.wsgi import get_wsgi_application
   application = get_wsgi_application()
   ```
6. Under **Static files** add two entries:
   - `/static/` -> `/home/yourusername/Hangarin/staticfiles`
   - `/media/` -> `/home/yourusername/Hangarin/media` (profile pictures)
7. Social login only: add your domain under **Sites** in the admin, and
   register the callback URLs listed in `.env.example` with each provider
   (for GitHub, see the section above).
8. Hit **Reload**.

When you push new code: `git pull`, then `pip install -r requirements.txt`,
`migrate` and `collectstatic` if something changed, then reload.

---

## 🔒 Security notes

- Secrets live in `.env` only. Never zip or commit that file. If a key or
  OAuth secret has ever been shared, rotate it.
- Every list, detail, edit, delete and status change is filtered by owner
  on the server, so guessing another person's URL gets a 404.
- Logging out and social login are POST only. Session and CSRF cookies are
  HttpOnly, and secure once `DJANGO_DEBUG` is off.
- A Content-Security-Policy lets pages run only this site's own scripts.
- Uploaded pictures are checked, re-encoded as WebP with metadata stripped,
  and stored under a random name. Nothing the user uploads is served as-is.
- CSV export defuses spreadsheet formulas.
- Pages with personal data are sent as `private, no-cache`, so the Back
  button after logging out on a shared computer doesn't reveal them.
- Set the `EMAIL_*` values to send real mail. Once you do, new email
  addresses have to be confirmed before they can be used to log in.

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
