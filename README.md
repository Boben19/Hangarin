# Hangarin

A task and to-do manager built with Django. Each task has a deadline, a status,
a priority and a category, and can be broken into subtasks and backed by notes.
Every person gets a progress page with streaks, levels, a weekly chart and
badges. It works as an installable app and keeps working without a connection.

Made by Jhon Grover Longsud.

## What's in it

- **Tasks** with a title, description, deadline, status (Pending, In Progress,
  Completed), priority and category.
- **Subtasks** with their own status, for the small steps inside a big job.
- **Notes** attached to a task.
- **Priorities** (High, Medium, Low, Critical, Optional) and **categories**
  (Work, School, Personal, Finance, Projects). These come as shared defaults;
  anyone can add their own.
- **Admin site** with filters and search on every model.

| Part | Tool |
|---|---|
| Framework | Django 5.2 |
| Database | SQLite |
| Sign-in | django-allauth (password, Google, Facebook, GitHub) |
| Seed data | Faker |
| Installable app | django-pwa, plus our own service worker |
| Hosting | PythonAnywhere |

## Accounts, progress and profile

Everything is behind a login. Tasks, subtasks and notes belong to the account
that made them, so people only see their own list.

The **My progress** page shows level and XP (a task is worth 10, a subtask 3, a
note 1, up to 30), the current and best streak, a 7-day chart, a 12-week
activity grid, a daily goal ring, completion by category, recent wins and
badges.

**Edit profile** changes your name, username, picture (PNG, JPG or WebP, cropped
square), bio, daily goal and theme (light, dark or follow the device). From
there you can also change your password, manage email addresses, download your
tasks as CSV, or delete the account and everything in it.

Keyboard shortcuts: `N` for a new task, `/` to search, `?` for the list.
Animations turn themselves off if the device asks for reduced motion.

## Working offline

Once you've signed in and used the app online, it keeps working when the
connection drops.

- **Reading:** every page you open is saved on the device, and the pages
  linked from it (each task, its edit form, the next page of results) are
  fetched in the background. Offline, you see those saved copies.
- **Writing:** new tasks, subtasks, notes, categories and priorities, edits,
  deletes and status clicks are all kept on the device while offline. A small
  pill at the bottom of the screen shows what is waiting. When the connection
  returns the changes are sent in the order they were made.
- **Searching:** offline, the search box filters the items already on the page.
  Sorting and filter dropdowns need a connection.
- **Drafts:** whatever you type in a form is kept until you save it, so a closed
  tab doesn't lose it.
- **What still needs a connection:** logging in, signing up, logging out,
  changing your profile or picture, and deleting your account.

If something you did offline can't be applied (say the task was deleted
elsewhere), it stays in the list marked as rejected and you can discard it.

**Shared computers.** Saved pages and drafts are removed when you log out. Each
page also carries a one-way tag of whose account it belongs to, and if a
different person signs in on the same browser the previous person's saved pages
are thrown away. Changes still waiting to sync stay on the device until that
same account logs in again.

How it's wired together:

- `static/js/serviceworker.js` saves pages and static files, answers from the
  saved copy when the network is down or slow, and keeps changes made offline.
  django-pwa serves it at `/serviceworker.js` so it controls the whole site.
- `static/js/offline-store.js` is the small IndexedDB layer both sides share.
- `static/js/offline.js` runs on each page: the sync pill, sending waiting
  changes, warming the cache, offline search.
- `static/js/pwa.js` registers the worker and runs the Install button. These are
  separate files because the site's Content-Security-Policy doesn't allow
  inline scripts. (`templates/pwa.html` replaces django-pwa's own template for
  the same reason.)
- `todo/middleware.py` adds the account tag header and the security headers.

Good to know:

- It needs `https://` or `localhost`. PythonAnywhere is https already.
- Changed a static file and still seeing the old one? Bump `VERSION` at the top
  of `serviceworker.js`.
- Icons are in `static/img/` (192, 512 and 180 px). Replace them with files of
  the same name for a different look.
- To try it: run the site, sign in, open a few pages, then stop `runserver` (or
  tick **Offline** in Chrome DevTools, Network tab) and keep using it. DevTools,
  Application tab shows the manifest, the worker and the saved caches.
- On iPhone, install with Share, then Add to Home Screen.

## Signing in with GitHub

The "Continue with GitHub" button only shows once the keys are in `.env`, so a
half-finished setup never sends anyone to a broken page.

1. On GitHub: **Settings, Developer settings, OAuth Apps, New OAuth App**.
2. Homepage URL `http://127.0.0.1:8000`, callback URL
   `http://127.0.0.1:8000/accounts/github/login/callback/`.
3. Generate a client secret and put the ID and secret in `.env` as
   `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET`.
4. Restart `runserver`. The button now appears on the login and sign-up pages.

One OAuth app can have several redirect URLs, so add the live site's
(`https://boben19.pythonanywhere.com/accounts/github/login/callback/`) to the
same app and use the same keys in the server's `.env`.

A new GitHub user gets an account named after their GitHub username (with a
number added if it's taken). If their email already belongs to an existing
Hangarin account, GitHub (or Google) logs them straight into that account
instead of sending them to sign up, as long as the provider says the email is
confirmed. If the provider doesn't confirm it (Facebook sometimes doesn't), they
are asked to log in with their password instead.

Google and Facebook work the same way with their own keys. `.env.example` lists
the callback URLs.

## Getting started

1. **Virtual environment**

   ```bash
   cd Hangarin
   python3 -m venv .venv
   source .venv/bin/activate      # macOS/Linux
   .venv\Scripts\activate         # Windows
   pip install -r requirements.txt
   ```

2. **Settings file.** Copy `.env.example` to `.env` and add a secret key:

   ```bash
   python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
   ```

   Paste only that output after `DJANGO_SECRET_KEY=`. For local work also add
   `DJANGO_DEBUG=True`. On purpose, the live site won't start with a missing,
   short or placeholder key.

3. **Database**

   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

4. **Seed data (optional).** Priorities and categories are added as shared
   defaults; tasks, subtasks and notes are generated with Faker for one account:

   ```bash
   python manage.py populate_data --username yourname
   python manage.py populate_data --username yourname --tasks 30 --subtasks-per-task 4 --notes-per-task 3
   ```

5. **Run it**

   ```bash
   python manage.py runserver
   ```

   The app is at `http://127.0.0.1:8000/` and the admin at `/admin/`.

6. **Run the tests**

   ```bash
   python manage.py test
   ```

## Version control

```bash
git add .
git commit -m "Describe what you changed"
git push
```

`.env`, `db.sqlite3`, `media/` and any `.venv*` folder are in `.gitignore`, so
secrets, local data and uploaded pictures never get committed.

## Deploying to PythonAnywhere

1. In a **Bash console**, get the code and make a virtualenv:

   ```bash
   git clone <your-repo-url> Hangarin
   cd Hangarin
   mkvirtualenv --python=/usr/bin/python3.11 hangarin-venv
   pip install -r requirements.txt
   ```

2. Create `.env` on the server (`cp .env.example .env`, then edit). Use a **new**
   `DJANGO_SECRET_KEY`, different from your laptop's. Leave `DJANGO_DEBUG` out.
   With your own domain, set `DJANGO_ALLOWED_HOSTS` and
   `DJANGO_CSRF_TRUSTED_ORIGINS` as well.
3. Set up the database and static files:

   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   python manage.py collectstatic
   ```

   `migrate` also changes the Site record from the placeholder `example.com` to
   your host name (set `DJANGO_SITE_DOMAIN` to choose one). django-allauth uses
   it for the links in emails.
4. On the **Web** tab add a web app with **Manual configuration**, set the
   virtualenv path (`/home/yourusername/.virtualenvs/hangarin-venv`) and the
   source and working directory (`/home/yourusername/Hangarin`).
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

6. Under **Static files** add:
   - `/static/` to `/home/yourusername/Hangarin/staticfiles`
   - `/media/` to `/home/yourusername/Hangarin/media` (profile pictures)
7. For social login, register the callback URLs listed in `.env.example` with
   each provider.
8. Press **Reload**.

When you push new code: `git pull`, then `pip install -r requirements.txt`,
`migrate` and `collectstatic` if something changed, then reload.

## Security notes

- Secrets live in `.env` only. Never zip or commit that file. If a key or OAuth
  secret has ever been shared, replace it.
- Every list, detail, edit, delete and status change is filtered by owner on the
  server, so guessing another person's URL gives a 404.
- Logging out and social login are POST only. Session and CSRF cookies are
  HttpOnly, and secure once `DJANGO_DEBUG` is off.
- A Content-Security-Policy lets pages run only this site's own scripts. Nothing
  is loaded from other sites: the fonts are the system ones.
- Uploaded pictures are checked, re-encoded as WebP with metadata stripped and
  stored under a random name.
- CSV export defuses spreadsheet formulas.
- Signed-in pages are sent as `private, no-cache`, so the browser's Back button
  after logging out on a shared computer doesn't show them. The offline copies
  are cleared at logout (see Working offline).
- Password reset and email confirmation only work once the `EMAIL_*` values in
  `.env` point at a real mail server. Until then, emails are printed to the
  server log instead of being sent.

## Contact

Jhon Grover Longsud, jhongroverlonsud@gmail.com

&copy; 2026 Jhon Grover Longsud. All rights reserved.
