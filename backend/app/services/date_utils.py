"""Date offset system for evergreen demo data.

All event dates use day_offset (0=today, 1=yesterday, etc.) so demo data
stays fresh regardless of when the app is run.
"""

from datetime import date, datetime, timedelta


def resolve_date(day_offset: int) -> date:
    """Convert day_offset to a real date. 0=today, 1=yesterday."""
    return date.today() - timedelta(days=day_offset)


def resolve_datetime(day_offset: int, time_str: str) -> datetime:
    """Convert day_offset + HH:MM time to a real datetime."""
    d = resolve_date(day_offset)
    t = datetime.strptime(time_str, "%H:%M").time()
    return datetime.combine(d, t)


def is_future(day_offset: int, time_str: str) -> bool:
    """Check if the resolved datetime is in the future."""
    return resolve_datetime(day_offset, time_str) > datetime.now()


def resolve_payment_due_date(days_ahead: int) -> date:
    """Convert days_ahead to a future date. 4 means 4 days from today."""
    return date.today() + timedelta(days=days_ahead)


def is_weekday(day_offset: int) -> bool:
    """Check if the resolved date is a weekday (Mon-Fri)."""
    return resolve_date(day_offset).weekday() < 5


def format_date_natural(day_offset: int) -> str:
    """Format a day_offset as a natural language date string."""
    d = resolve_date(day_offset)
    if day_offset == 0:
        return f"today ({d.strftime('%A, %B %d')})"
    if day_offset == 1:
        return f"yesterday ({d.strftime('%A, %B %d')})"
    return d.strftime("%A, %B %d, %Y")


def format_time_natural(time_str: str) -> str:
    """Convert HH:MM to natural time like '7:45 AM'."""
    t = datetime.strptime(time_str, "%H:%M")
    return t.strftime("%-I:%M %p")


def temporal_hint(day_offset: int, time_str: str) -> str:
    """Return 'past' or 'future' based on whether the event has happened."""
    if day_offset > 0:
        return "past"
    if day_offset == 0:
        return "future" if is_future(day_offset, time_str) else "past"
    return "future"
