"""Child-specific data queries with date resolution and attribution."""

from datetime import datetime

from backend.app.db.database import Database
from backend.app.services.date_utils import (
    format_date_natural,
    format_time_natural,
    resolve_date,
    resolve_payment_due_date,
    temporal_hint,
)


async def query_child_info(
    db: Database,
    child_id: int,
    info_type: str,
    day_offset: int = 0,
) -> dict:
    """Query child-specific information. Returns structured data for the LLM.

    info_type: attendance | meals | allergies | emergency_contacts | payments | field_trips | overview
    """
    # Get child basic info
    child = await db.fetch_one("SELECT * FROM children WHERE id = ?", (child_id,))
    if not child:
        return {"error": f"Child with id {child_id} not found"}

    child_name = f"{child['first_name']} {child['last_name']}"
    current_time = datetime.now().strftime("%-I:%M %p")
    result: dict = {
        "child_name": child_name,
        "child_id": child_id,
        "info_type": info_type,
        "current_time": current_time,
    }

    if info_type == "attendance":
        result["data"] = await _query_attendance(db, child_id, day_offset)
    elif info_type == "meals":
        result["data"] = await _query_meals(db, child_id, day_offset)
    elif info_type == "allergies":
        result["data"] = await _query_allergies(db, child_id)
    elif info_type == "emergency_contacts":
        result["data"] = await _query_emergency_contacts(db, child_id, child)
    elif info_type == "payments":
        result["data"] = await _query_payments(db, child_id)
    elif info_type == "field_trips":
        result["data"] = await _query_field_trips(db, child, day_offset)
    elif info_type == "overview":
        result["data"] = await _query_overview(db, child_id, child)
    else:
        result["error"] = f"Unknown info_type: {info_type}"

    return result


async def _query_attendance(db: Database, child_id: int, day_offset: int) -> list[dict]:
    rows = await db.fetch_all(
        "SELECT * FROM attendance WHERE child_id = ? AND day_offset = ?",
        (child_id, day_offset),
    )
    return [
        {
            "date": format_date_natural(row["day_offset"]),
            "status": row["status"],
            "check_in_time": format_time_natural(row["check_in_time"])
            if row["check_in_time"]
            else None,
            "check_out_time": format_time_natural(row["check_out_time"])
            if row["check_out_time"]
            else "still here",
            "checked_in_by": row["checked_in_by"],
            "checked_out_by": row["checked_out_by"],
            "temporal_hint": temporal_hint(row["day_offset"], row["check_in_time"])
            if row["check_in_time"]
            else "past",
        }
        for row in rows
    ]


async def _query_meals(db: Database, child_id: int, day_offset: int) -> list[dict]:
    rows = await db.fetch_all(
        "SELECT * FROM meals WHERE child_id = ? AND day_offset = ? ORDER BY scheduled_time",
        (child_id, day_offset),
    )
    return [
        {
            "meal_type": row["meal_type"],
            "time": format_time_natural(row["scheduled_time"]),
            "description": row["description"],
            "recorded_by": row["recorded_by"],
            "temporal_hint": temporal_hint(row["day_offset"], row["scheduled_time"]),
        }
        for row in rows
    ]


async def _query_allergies(db: Database, child_id: int) -> list[dict]:
    rows = await db.fetch_all("SELECT * FROM allergies WHERE child_id = ?", (child_id,))
    return [
        {
            "allergy_type": row["allergy_type"],
            "description": row["description"],
            "doctor_confirmed": bool(row["doctor_confirmed"]),
            "recorded_by": row["recorded_by"],
            "recorded_date": row["recorded_date"],
        }
        for row in rows
    ]


async def _query_emergency_contacts(db: Database, child_id: int, child) -> list[dict]:
    rows = await db.fetch_all(
        "SELECT * FROM emergency_contacts WHERE child_id = ? ORDER BY is_primary DESC",
        (child_id,),
    )
    contacts = [
        {
            "contact_name": row["contact_name"],
            "relationship": row["relationship"],
            "phone": row["phone"],
            "is_primary": bool(row["is_primary"]),
        }
        for row in rows
    ]
    # Include the child's doctor info
    if child["doctor_name"]:
        contacts.append(
            {
                "contact_name": child["doctor_name"],
                "relationship": "Pediatrician",
                "phone": child["doctor_phone"] or "N/A",
                "is_primary": False,
            }
        )
    return contacts


async def _query_payments(db: Database, child_id: int) -> list[dict]:
    row = await db.fetch_one("SELECT * FROM payments WHERE child_id = ?", (child_id,))
    if not row:
        return []
    due_date = resolve_payment_due_date(row["next_payment_days_ahead"])
    last_date = (
        resolve_date(row["last_payment_date_offset"])
        if row["last_payment_date_offset"]
        else None
    )
    return [
        {
            "current_balance": f"${row['current_balance']:.2f}",
            "next_payment_due": due_date.strftime("%A, %B %d, %Y"),
            "last_payment_amount": f"${row['last_payment_amount']:.2f}"
            if row["last_payment_amount"]
            else None,
            "last_payment_date": last_date.strftime("%B %d, %Y") if last_date else None,
            "fee_type": row["fee_type"],
            "weekly_fee": f"${row['weekly_fee']:.2f}",
        }
    ]


async def _query_field_trips(db: Database, child, day_offset: int) -> list[dict]:
    classroom = child["classroom"]
    rows = await db.fetch_all(
        "SELECT * FROM field_trips WHERE classrooms LIKE ? ORDER BY day_offset ASC",
        (f"%{classroom}%",),
    )
    return [
        {
            "date": format_date_natural(row["day_offset"]),
            "description": row["description"],
            "departure_time": format_time_natural(row["departure_time"]),
            "return_time": format_time_natural(row["return_time"]),
            "classrooms": row["classrooms"],
            "recorded_by": row["recorded_by"],
            "temporal_hint": temporal_hint(row["day_offset"], row["departure_time"]),
        }
        for row in rows
    ]


async def _query_overview(db: Database, child_id: int, child) -> dict:
    """Return a high-level summary of the child."""
    # Today's attendance
    att = await db.fetch_one(
        "SELECT * FROM attendance WHERE child_id = ? AND day_offset = 0",
        (child_id,),
    )
    # Allergies count
    allergy_rows = await db.fetch_all(
        "SELECT description FROM allergies WHERE child_id = ?", (child_id,)
    )
    # Balance
    payment = await db.fetch_one(
        "SELECT current_balance FROM payments WHERE child_id = ?", (child_id,)
    )
    return {
        "child_name": f"{child['first_name']} {child['last_name']}",
        "age": child["age"],
        "classroom": child["classroom"],
        "teacher": f"{child['teacher_name']}, {child['teacher_role']}, {child['room_number']}",
        "today_status": att["status"] if att else "no record for today",
        "check_in_time": format_time_natural(att["check_in_time"])
        if att and att["check_in_time"]
        else None,
        "allergies": [r["description"] for r in allergy_rows]
        if allergy_rows
        else ["None on file"],
        "balance": f"${payment['current_balance']:.2f}" if payment else "N/A",
    }
