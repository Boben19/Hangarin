# Hangarin — Task & To-Do Manager

Django app for organizing tasks, priorities, categories, notes, and subtasks,
based on the ERD in the spec.

## Project layout

```
hangarin/
├── hangarin/          # project settings, urls, wsgi/asgi
├── todo/              # the app itself
│   ├── models.py       # BaseModel, Priority, Category, Task, SubTask, Note
│   ├── admin.py         # admin site config
│   └── management/commands/populate_data.py   # faker seed script
├── manage.py
├── requirements.txt
└── .gitignore
```

## 1. Virtual environment

```bash
cd hangarin
python3 -m venv venv

# activate it
source venv/bin/activate      # macOS/Linux
venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

## 2. Database & migrations

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

## 3. Seed data

Priority and Category are added manually per the spec (five of each), and
Task/SubTask/Note are generated with Faker. One command does all of it:

```bash
python manage.py populate_data
```

Optional flags if you want more or less data:

```bash
python manage.py populate_data --tasks 30 --subtasks-per-task 4 --notes-per-task 3
```

## 4. Run it

```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000/admin/` and log in with the superuser you created.
You should see Tasks, SubTasks, Notes, Categories, and Priorities, with the
list columns, filters, and search boxes from the spec, and "Categories" /
"Priorities" showing up correctly pluralized.

## 5. Git

```bash
git init
git add .
git commit -m "Initial commit: Hangarin task manager"
```

Push to GitHub (or wherever) from there:

```bash
git remote add origin <your-repo-url>
git branch -M main
git push -u origin main
```

`db.sqlite3` and `venv/` are already in `.gitignore` so you're not committing
your local database or virtual environment.

## 6. Deploying to PythonAnywhere

1. Sign in to PythonAnywhere and open a **Bash console**.
2. Clone your repo:
   ```bash
   git clone <your-repo-url>
   cd hangarin
   ```
3. Create a virtualenv (PythonAnywhere's own tooling):
   ```bash
   mkvirtualenv --python=/usr/bin/python3.11 hangarin-venv
   pip install -r requirements.txt
   ```
4. Run migrations and seed data the same way as locally:
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   python manage.py populate_data
   ```
5. Go to the **Web** tab → **Add a new web app** → choose **Manual
   configuration** (not the Django wizard) → pick the same Python version.
6. Set the **virtualenv** path to the one you just created, e.g.
   `/home/yourusername/.virtualenvs/hangarin-venv`.
7. Edit the **WSGI configuration file** it links to and point it at this
   project's `hangarin/wsgi.py` — replace the boilerplate with something
   like:
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
8. In `hangarin/settings.py`, update `ALLOWED_HOSTS`:
   ```python
   ALLOWED_HOSTS = ['yourusername.pythonanywhere.com']
   ```
   and set `DEBUG = False` once you've confirmed it works.
9. Under the **Static files** section of the Web tab, map URL `/static/` to
   `/home/yourusername/hangarin/static`, then run:
   ```bash
   python manage.py collectstatic
   ```
10. Hit **Reload** on the Web tab and open your `.pythonanywhere.com` URL.
    The admin should be live at `/admin/`.

Whenever you push new commits, `git pull` inside the PythonAnywhere console,
re-run `migrate`/`collectstatic` if needed, and hit Reload again.
