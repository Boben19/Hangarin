"""
Everything the profile page and the home dashboard show about someone's
progress. All of it is worked out from the tasks, subtasks and notes they
already have, nothing extra is stored.
"""

from collections import Counter
from datetime import timedelta
from itertools import chain
from math import isqrt

from django.db.models import Count, Q
from django.utils import timezone

from .models import Category, Note, Profile, SubTask, Task

XP_PER_TASK = 10
XP_PER_SUBTASK = 3
XP_PER_NOTE = 1
NOTE_XP_CAP = 30

LEVEL_TITLES = [
    "Seed", "Sprout", "Seedling", "Sapling", "Young tree",
    "Tall tree", "Grove keeper", "Forest guardian", "Ancient oak",
]


def ensure_profile(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def _completion_counter(user):
    """How many things were finished on each local calendar day."""
    stamps = chain(
        Task.objects.filter(owner=user, completed_at__isnull=False)
        .values_list("completed_at", flat=True),
        SubTask.objects.filter(parent_task__owner=user, completed_at__isnull=False)
        .values_list("completed_at", flat=True),
    )
    return Counter(timezone.localtime(stamp).date() for stamp in stamps)


def _streaks(days, today):
    """(current, best) run of consecutive days with something finished."""
    if not days:
        return 0, 0

    ordered = sorted(days)
    best = run = 1
    for earlier, later in zip(ordered, ordered[1:]):
        run = run + 1 if (later - earlier).days == 1 else 1
        best = max(best, run)

    # a streak is still alive if you finished something today or yesterday
    cursor = today if today in days else today - timedelta(days=1)
    current = 0
    while cursor in days:
        current += 1
        cursor -= timedelta(days=1)
    return current, best


def level_for(xp):
    level = isqrt(xp // 40) + 1
    floor = 40 * (level - 1) ** 2
    ceiling = 40 * level ** 2
    return {
        "level": level,
        "title": LEVEL_TITLES[min(level - 1, len(LEVEL_TITLES) - 1)],
        "xp": xp,
        "floor": floor,
        "ceiling": ceiling,
        "into": xp - floor,
        "span": ceiling - floor,
        "pct": round((xp - floor) * 100 / (ceiling - floor)),
        "to_next": ceiling - xp,
    }


def xp_for(user):
    """Just the XP total, for callers that don't need the whole summary."""
    done_tasks = Task.objects.filter(owner=user, status=Task.Status.COMPLETED).count()
    done_subs = SubTask.objects.filter(
        parent_task__owner=user, status=SubTask.Status.COMPLETED
    ).count()
    notes = Note.objects.filter(task__owner=user).count()
    return (
        done_tasks * XP_PER_TASK
        + done_subs * XP_PER_SUBTASK
        + min(notes * XP_PER_NOTE, NOTE_XP_CAP)
    )


def today_progress(user, counter=None):
    counter = counter if counter is not None else _completion_counter(user)
    profile = ensure_profile(user)
    done = counter.get(timezone.localdate(), 0)
    goal = profile.daily_goal
    return {
        "done": done,
        "goal": goal,
        "pct": min(100, round(done * 100 / goal)),
        "hit": done >= goal,
        "left": max(0, goal - done),
    }


WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _heatmap(counter, today, weeks=12):
    """Columns of seven days (Monday first), oldest week on the left. Each
    cell gets a 0-4 level so the page can shade it like a contribution grid."""
    start = today - timedelta(days=today.weekday()) - timedelta(weeks=weeks - 1)
    top = max(
        (counter.get(start + timedelta(days=i), 0) for i in range(weeks * 7)),
        default=0,
    )
    columns = []
    last_month = None
    for w in range(weeks):
        first = start + timedelta(weeks=w)
        cells = []
        for d in range(7):
            day = first + timedelta(days=d)
            count = counter.get(day, 0)
            future = day > today
            if future or not count or not top:
                level = 0
            else:
                level = min(4, -(-count * 4 // top))  # ceiling division
            cells.append({"date": day, "count": count, "level": level, "future": future})
        label = first.strftime("%b") if first.month != last_month else ""
        last_month = first.month
        columns.append({"label": label, "cells": cells})
    return columns


def _best_weekday(counter):
    """Which day of the week you finish the most on, or None with no history."""
    by_day = Counter()
    for day, n in counter.items():
        by_day[day.weekday()] += n
    if not by_day:
        return None
    index, total = max(by_day.items(), key=lambda pair: (pair[1], -pair[0]))
    return {"name": WEEKDAYS[index], "total": total}


# Each badge keeps its icon name (a symbol in templates/_icons.html) and also
# gets an emoji, which is what the profile page shows.
BADGE_EMOJI = {
    "leaf": "🌱", "check-circle": "✅", "flame": "🔥", "tree": "🌳", "steps": "🪜",
    "note": "📝", "calendar-check": "📆", "trophy": "🏆", "target": "🎯", "clock-check": "🧹",
}


def _badges(numbers):
    """(icon, name, what-it-takes, current, needed) for each badge."""
    rows = [
        ("leaf", "First seed", "Add your first task", numbers["total"], 1),
        ("check-circle", "Finisher", "Complete a task", numbers["completed"], 1),
        ("flame", "On a roll", "Complete 10 tasks", numbers["completed"], 10),
        ("tree", "Green thumb", "Complete 50 tasks", numbers["completed"], 50),
        ("steps", "Step by step", "Finish 25 subtasks", numbers["subtasks_done"], 25),
        ("note", "Note taker", "Write 10 notes", numbers["notes"], 10),
        ("calendar-check", "Three in a row", "Get a 3-day streak", numbers["best_streak"], 3),
        ("trophy", "A full week", "Get a 7-day streak", numbers["best_streak"], 7),
        ("target", "Goal getter", "Hit your daily goal once", numbers["best_day"], numbers["goal"]),
        ("clock-check", "Nothing late", "Have 5+ tasks and none overdue",
         numbers["total"] if numbers["overdue"] == 0 else 0, 5),
    ]
    return [
        {
            "icon": icon,
            "emoji": BADGE_EMOJI.get(icon, "⭐"),
            "name": name,
            "hint": hint,
            "have": min(have, need),
            "need": need,
            "earned": have >= need,
            "pct": min(100, round(have * 100 / need)) if need else 100,
        }
        for icon, name, hint, have, need in rows
    ]


def progress_summary(user):
    tasks = Task.objects.filter(owner=user)
    now = timezone.now()
    today = timezone.localdate()

    by_status = dict(tasks.values_list("status").annotate(n=Count("id")))
    total = sum(by_status.values())
    completed = by_status.get(Task.Status.COMPLETED, 0)
    in_progress = by_status.get(Task.Status.IN_PROGRESS, 0)
    pending = by_status.get(Task.Status.PENDING, 0)
    overdue = (
        tasks.exclude(status=Task.Status.COMPLETED)
        .filter(deadline__lt=now)
        .count()
    )

    subtasks = SubTask.objects.filter(parent_task__owner=user)
    subtasks_total = subtasks.count()
    subtasks_done = subtasks.filter(status=SubTask.Status.COMPLETED).count()
    notes = Note.objects.filter(task__owner=user).count()

    counter = _completion_counter(user)
    current_streak, best_streak = _streaks(set(counter), today)
    goal_today = today_progress(user, counter)

    week = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        week.append({
            "label": day.strftime("%a"),
            "date": day,
            "count": counter.get(day, 0),
            "is_today": offset == 0,
        })
    top = max((d["count"] for d in week), default=0) or 1
    for day in week:
        day["height"] = max(6, round(day["count"] * 100 / top)) if day["count"] else 6
    this_week = sum(d["count"] for d in week)
    last_week = sum(
        counter.get(today - timedelta(days=offset), 0) for offset in range(7, 14)
    )

    breakdown = list(
        tasks.values("category__name")
        .annotate(n=Count("id"), done=Count("id", filter=Q(status=Task.Status.COMPLETED)))
        .order_by("-n")[:6]
    )
    for row in breakdown:
        row["name"] = row["category__name"] or "No category"
        row["pct"] = round(row["n"] * 100 / total) if total else 0

    xp = (
        completed * XP_PER_TASK
        + subtasks_done * XP_PER_SUBTASK
        + min(notes * XP_PER_NOTE, NOTE_XP_CAP)
    )
    heatmap = _heatmap(counter, today)
    active_days = sum(1 for column in heatmap for c in column["cells"] if c["count"])

    numbers = {
        "total": total,
        "completed": completed,
        "subtasks_done": subtasks_done,
        "notes": notes,
        "best_streak": best_streak,
        "best_day": max(counter.values(), default=0),
        "goal": goal_today["goal"],
        "overdue": overdue,
    }
    badges = _badges(numbers)

    recent_tasks = [
        {"title": t.title, "when": t.completed_at, "kind": "task", "pk": t.pk}
        for t in tasks.filter(completed_at__isnull=False).order_by("-completed_at")[:6]
    ]
    recent_subs = [
        {"title": s.title, "when": s.completed_at, "kind": "subtask", "pk": s.parent_task_id}
        for s in subtasks.filter(completed_at__isnull=False).order_by("-completed_at")[:6]
    ]
    recent = sorted(chain(recent_tasks, recent_subs), key=lambda r: r["when"], reverse=True)[:8]

    return {
        "total": total,
        "completed": completed,
        "in_progress": in_progress,
        "pending": pending,
        "open": pending + in_progress,
        "overdue": overdue,
        "completion_rate": round(completed * 100 / total) if total else 0,
        "subtasks_total": subtasks_total,
        "subtasks_done": subtasks_done,
        "notes": notes,
        "streak": current_streak,
        "best_streak": best_streak,
        "today": goal_today,
        "week": week,
        "heatmap": heatmap,
        "active_days": active_days,
        "best_weekday": _best_weekday(counter),
        "total_finished": completed + subtasks_done,
        "this_week": this_week,
        "last_week": last_week,
        "week_delta": this_week - last_week,
        "breakdown": breakdown,
        "level": level_for(xp),
        "badges": badges,
        "badges_earned": sum(1 for b in badges if b["earned"]),
        "recent": recent,
        "categories": Category.objects.visible_to(user).count(),
    }
