"""Seed data generator for Sunshine Learning Center.

Creates realistic demo data: 8 children across 3 classrooms with attendance,
meals, allergies, emergency contacts, payments, field trips, and sample sessions.

Idempotent: running again resets the database to a known state.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta

from backend.app.config import Settings
from backend.app.db.database import Database
from backend.app.services.date_utils import is_weekday, resolve_date

logger = logging.getLogger(__name__)

# ── Children ────────────────────────────────────────────────────────────────

CHILDREN = [
    # Caterpillar Room (ages 0-2)
    {
        "first_name": "Liam", "last_name": "Chen", "age": 1,
        "classroom": "Caterpillar Room", "teacher_name": "Mrs. Rosa Vasquez",
        "teacher_role": "Lead Infant Teacher", "room_number": "Rm 101",
        "security_code": "3847", "enrolled_date": "2025-08-15",
        "doctor_name": "Dr. Sarah Chen", "doctor_phone": "(505) 555-0201",
    },
    {
        "first_name": "Ava", "last_name": "Patel", "age": 2,
        "classroom": "Caterpillar Room", "teacher_name": "Mrs. Rosa Vasquez",
        "teacher_role": "Lead Infant Teacher", "room_number": "Rm 101",
        "security_code": "6152", "enrolled_date": "2025-07-10",
        "doctor_name": "Dr. James Whitfield", "doctor_phone": "(505) 555-0202",
    },
    # Ladybug Room (ages 2-3)
    {
        "first_name": "Noah", "last_name": "Williams", "age": 3,
        "classroom": "Ladybug Room", "teacher_name": "Mr. David Okonkwo",
        "teacher_role": "Lead Toddler Teacher", "room_number": "Rm 102",
        "security_code": "9283", "enrolled_date": "2025-09-01",
        "doctor_name": "Dr. Maria Lopez", "doctor_phone": "(505) 555-0203",
    },
    {
        "first_name": "Emma", "last_name": "Jackson", "age": 2,
        "classroom": "Ladybug Room", "teacher_name": "Mr. David Okonkwo",
        "teacher_role": "Lead Toddler Teacher", "room_number": "Rm 102",
        "security_code": "4716", "enrolled_date": "2025-10-15",
        "doctor_name": "Dr. Sarah Chen", "doctor_phone": "(505) 555-0201",
    },
    {
        "first_name": "Oliver", "last_name": "Kim", "age": 3,
        "classroom": "Ladybug Room", "teacher_name": "Mr. David Okonkwo",
        "teacher_role": "Lead Toddler Teacher", "room_number": "Rm 102",
        "security_code": "5039", "enrolled_date": "2025-08-20",
        "doctor_name": "Dr. Priya Sharma", "doctor_phone": "(505) 555-0204",
    },
    # Butterfly Room (ages 3-5)
    {
        "first_name": "Sofia", "last_name": "Martinez", "age": 4,
        "classroom": "Butterfly Room", "teacher_name": "Mrs. Elena Rodriguez",
        "teacher_role": "Lead Pre-K Teacher", "room_number": "Rm 103",
        "security_code": "7291", "enrolled_date": "2025-09-02",
        "doctor_name": "Dr. Sarah Chen", "doctor_phone": "(505) 555-0201",
    },
    {
        "first_name": "Ethan", "last_name": "Brooks", "age": 5,
        "classroom": "Butterfly Room", "teacher_name": "Mrs. Elena Rodriguez",
        "teacher_role": "Lead Pre-K Teacher", "room_number": "Rm 103",
        "security_code": "8624", "enrolled_date": "2025-08-25",
        "doctor_name": "Dr. James Whitfield", "doctor_phone": "(505) 555-0202",
    },
    {
        "first_name": "Mia", "last_name": "Thompson", "age": 4,
        "classroom": "Butterfly Room", "teacher_name": "Mrs. Elena Rodriguez",
        "teacher_role": "Lead Pre-K Teacher", "room_number": "Rm 103",
        "security_code": "1357", "enrolled_date": "2025-09-10",
        "doctor_name": "Dr. Maria Lopez", "doctor_phone": "(505) 555-0203",
    },
]

# ── Meal schedules ──────────────────────────────────────────────────────────

MEALS_SCHEDULE = [
    ("breakfast", "08:15", [
        "Oatmeal with fruit, milk",
        "Scrambled eggs, toast, orange juice",
        "Whole grain cereal, banana, milk",
        "Yogurt parfait with granola, apple juice",
        "Pancakes with blueberries, milk",
    ]),
    ("snack_am", "10:00", [
        "Apple slices with cheese",
        "Goldfish crackers, water",
        "Carrot sticks with hummus",
        "Graham crackers, milk",
        "String cheese, grapes",
    ]),
    ("lunch", "12:00", [
        "Chicken nuggets, green beans, rice, milk",
        "Mac and cheese, steamed broccoli, applesauce",
        "Turkey sandwich, mixed veggies, water",
        "Spaghetti with meat sauce, garlic bread, milk",
        "Grilled cheese, tomato soup, fruit cup",
    ]),
    ("snack_pm", "15:00", [
        "Apple slices, cheese crackers",
        "Celery with peanut butter (allergy-safe: sunbutter)",
        "Pretzels, juice box",
        "Trail mix, water",
        "Banana, vanilla wafers",
    ]),
]

# ── Allergies ───────────────────────────────────────────────────────────────

# child index → list of allergies
ALLERGIES = {
    0: [  # Liam
        ("food", "Dairy - moderate (lactose intolerant)", 1),
    ],
    2: [  # Noah
        ("food", "Peanuts - severe (EpiPen required)", 1),
        ("environmental", "Dust mites - mild", 1),
    ],
    5: [  # Sofia
        ("food", "Tree nuts - moderate (avoid all tree nuts)", 1),
    ],
    7: [  # Mia
        ("medication", "Amoxicillin - hives", 1),
        ("food", "Shellfish - moderate", 0),
    ],
}

# ── Emergency contacts ──────────────────────────────────────────────────────

EMERGENCY_CONTACTS = {
    0: [  # Liam
        ("Wei Chen", "Father", "(505) 555-0110", 1),
        ("Linda Chen", "Mother", "(505) 555-0111", 0),
        ("Mary Chen", "Grandmother", "(505) 555-0112", 0),
    ],
    1: [  # Ava
        ("Raj Patel", "Father", "(505) 555-0120", 1),
        ("Anita Patel", "Mother", "(505) 555-0121", 0),
    ],
    2: [  # Noah
        ("Marcus Williams", "Father", "(505) 555-0130", 1),
        ("Keisha Williams", "Mother", "(505) 555-0131", 0),
        ("Gloria Williams", "Grandmother", "(505) 555-0132", 0),
    ],
    3: [  # Emma
        ("Robert Jackson", "Father", "(505) 555-0140", 1),
        ("Lisa Jackson", "Mother", "(505) 555-0141", 0),
    ],
    4: [  # Oliver
        ("Joon Kim", "Father", "(505) 555-0150", 1),
        ("Soo-yeon Kim", "Mother", "(505) 555-0151", 0),
    ],
    5: [  # Sofia
        ("Carlos Martinez", "Father", "(505) 555-0160", 1),
        ("Maria Martinez", "Mother", "(505) 555-0161", 0),
        ("Elena Reyes", "Aunt", "(505) 555-0162", 0),
    ],
    6: [  # Ethan
        ("James Brooks", "Father", "(505) 555-0170", 1),
        ("Sarah Brooks", "Mother", "(505) 555-0171", 0),
    ],
    7: [  # Mia
        ("Kevin Thompson", "Father", "(505) 555-0180", 1),
        ("Jessica Thompson", "Mother", "(505) 555-0181", 0),
    ],
}

# ── Payments ────────────────────────────────────────────────────────────────

PAYMENT_DATA = [
    # (balance, days_ahead, last_amount, last_offset, fee_type, weekly)
    (0.00, 4, 250.00, 7, "Infant Full-Time", 85.00),
    (125.00, 4, 250.00, 14, "Infant Full-Time", 85.00),
    (0.00, 4, 200.00, 7, "Toddler Full-Time", 75.00),
    (50.00, 4, 200.00, 10, "Toddler Full-Time", 75.00),
    (0.00, 4, 200.00, 7, "Toddler Full-Time", 75.00),
    (0.00, 4, 175.00, 7, "Preschool Extended Care", 65.00),
    (175.00, 4, 175.00, 21, "Preschool Extended Care", 65.00),
    (0.00, 4, 175.00, 7, "Preschool Extended Care", 65.00),
]

# ── Field trips ─────────────────────────────────────────────────────────────

FIELD_TRIPS = [
    (2, "Walking trip to Tiguex Park", "10:00", "11:30",
     "Butterfly Room, Ladybug Room",
     "Mrs. Elena Rodriguez, Lead Pre-K Teacher, Rm 103"),
    (5, "Fire station visit", "09:30", "11:00",
     "Butterfly Room",
     "Mrs. Elena Rodriguez, Lead Pre-K Teacher, Rm 103"),
]


async def seed_database(db: Database) -> None:
    """Populate the database with demo data. Idempotent (drops and recreates)."""
    # Clear existing data (reverse FK order)
    for table in [
        "messages", "sessions", "operator_faq_overrides", "tour_requests",
        "field_trips", "payments", "emergency_contacts", "allergies",
        "meals", "attendance", "children",
    ]:
        await db.execute(f"DELETE FROM {table}")  # noqa: S608

    # ── Children ────────────────────────────────────────────────────────
    child_ids: list[int] = []
    for child in CHILDREN:
        row_id = await db.insert(
            """INSERT INTO children
               (first_name, last_name, age, classroom, teacher_name,
                teacher_role, room_number, security_code, enrolled_date,
                doctor_name, doctor_phone)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                child["first_name"], child["last_name"], child["age"],
                child["classroom"], child["teacher_name"], child["teacher_role"],
                child["room_number"], child["security_code"], child["enrolled_date"],
                child["doctor_name"], child["doctor_phone"],
            ),
        )
        child_ids.append(row_id)

    # ── Attendance (weekdays only, day_offsets 0-6) ─────────────────────
    check_in_times = ["07:30", "07:45", "08:00", "08:15", "08:30"]
    check_out_times = ["16:30", "16:45", "17:00", "17:15", "17:30"]

    for idx, child_id in enumerate(child_ids):
        child = CHILDREN[idx]
        teacher_attr = f"{child['teacher_name']}, {child['teacher_role']}, {child['room_number']}"

        for day_offset in range(7):
            if not is_weekday(day_offset):
                continue

            cin = check_in_times[idx % len(check_in_times)]
            cout = check_out_times[idx % len(check_out_times)]
            # Today: leave check_out null (still here) for some children
            if day_offset == 0 and idx % 2 == 0:
                cout_val = None
                cout_by = None
            else:
                cout_val = cout
                cout_by = f"Mr. James Park, Afternoon Aide, {child['room_number']}"

            await db.insert(
                """INSERT INTO attendance
                   (child_id, day_offset, check_in_time, check_out_time,
                    checked_in_by, checked_out_by, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (child_id, day_offset, cin, cout_val, teacher_attr, cout_by, "present"),
            )

    # ── Meals (weekdays only, day_offsets 0-4) ──────────────────────────
    cafeteria_staff = "Mrs. Jean Walsh, Cafeteria Mgr"

    for idx, child_id in enumerate(child_ids):
        for day_offset in range(5):
            if not is_weekday(day_offset):
                continue
            for meal_type, sched_time, descriptions in MEALS_SCHEDULE:
                desc = descriptions[(day_offset + idx) % len(descriptions)]
                await db.insert(
                    """INSERT INTO meals
                       (child_id, day_offset, meal_type, scheduled_time,
                        description, recorded_by)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (child_id, day_offset, meal_type, sched_time, desc, cafeteria_staff),
                )

    # ── Allergies ───────────────────────────────────────────────────────
    for child_idx, allergy_list in ALLERGIES.items():
        child = CHILDREN[child_idx]
        teacher_attr = f"{child['teacher_name']}, {child['teacher_role']}, {child['room_number']}"
        for allergy_type, description, doctor_confirmed in allergy_list:
            await db.insert(
                """INSERT INTO allergies
                   (child_id, allergy_type, description, doctor_confirmed,
                    recorded_by, recorded_date)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    child_ids[child_idx], allergy_type, description,
                    doctor_confirmed, teacher_attr, child["enrolled_date"],
                ),
            )

    # ── Emergency contacts ──────────────────────────────────────────────
    for child_idx, contacts in EMERGENCY_CONTACTS.items():
        for name, relationship, phone, is_primary in contacts:
            await db.insert(
                """INSERT INTO emergency_contacts
                   (child_id, contact_name, relationship, phone, is_primary,
                    recorded_by, recorded_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    child_ids[child_idx], name, relationship, phone, is_primary,
                    "Admin Office", CHILDREN[child_idx]["enrolled_date"],
                ),
            )

    # ── Payments ────────────────────────────────────────────────────────
    for idx, child_id in enumerate(child_ids):
        bal, days_ahead, last_amt, last_off, fee, weekly = PAYMENT_DATA[idx]
        await db.insert(
            """INSERT INTO payments
               (child_id, current_balance, next_payment_days_ahead,
                last_payment_amount, last_payment_date_offset, fee_type, weekly_fee)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (child_id, bal, days_ahead, last_amt, last_off, fee, weekly),
        )

    # ── Field trips (only insert if day_offset lands on a weekday) ──────
    for day_offset, desc, dep, ret, classrooms, rec_by in FIELD_TRIPS:
        if is_weekday(day_offset):
            await db.insert(
                """INSERT INTO field_trips
                   (day_offset, description, departure_time, return_time,
                    classrooms, recorded_by)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (day_offset, desc, dep, ret, classrooms, rec_by),
            )

    # ── Sample FAQ overrides ────────────────────────────────────────────
    now_iso = datetime.now().isoformat()
    faq_overrides = [
        ("What are your hours?",
         "Sunshine Learning Center is open Monday through Friday, 7:00 AM to 5:30 PM. We are closed on weekends and major holidays.",
         "Admin"),
        ("Do you provide lunch?",
         "Yes! We provide breakfast, morning snack, lunch, and afternoon snack daily. All meals meet USDA nutrition guidelines. Please let us know about any food allergies.",
         "Admin"),
    ]
    for question, answer, created_by in faq_overrides:
        await db.insert(
            """INSERT INTO operator_faq_overrides
               (question_pattern, answer, created_by, created_at, active)
               VALUES (?, ?, ?, ?, 1)""",
            (question, answer, created_by, now_iso),
        )

    # ── Sample session + messages (so operator dashboard has data) ───────
    session_id = str(uuid.uuid4())
    session_start = (datetime.now() - timedelta(hours=2)).isoformat()
    session_end = (datetime.now() - timedelta(hours=1, minutes=45)).isoformat()

    await db.insert(
        """INSERT INTO sessions
           (id, started_at, ended_at, security_code_used, child_id,
            transferred_to_human, input_mode)
           VALUES (?, ?, ?, ?, ?, 0, 'text')""",
        (session_id, session_start, session_end, "7291", child_ids[5]),
    )

    sample_messages = [
        ("user", "What time does the center open?", None, None),
        ("assistant",
         "Sunshine Learning Center opens at 7:00 AM Monday through Friday. We close at 5:30 PM. "
         "Is there anything else I can help you with?",
         json.dumps([{"page": 31, "section": "Hours of Operation",
                       "text": "The center operates Monday-Friday, 7:00 AM to 5:30 PM."}]),
         "search_handbook"),
        ("user", "I want to check on my daughter Sofia", None, None),
        ("assistant",
         "Of course! To access Sofia's information, I'll need your 4-digit security code. "
         "Could you please enter it?",
         None, None),
    ]
    for role, content, citations, tool_used in sample_messages:
        ts = (datetime.now() - timedelta(hours=1, minutes=50)).isoformat()
        await db.insert(
            """INSERT INTO messages
               (session_id, role, content, citations, tool_used, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, role, content, citations, tool_used, ts),
        )

    logger.info(
        "Seed data created: %d children, meals, attendance, allergies, contacts, payments",
        len(child_ids),
    )


async def main() -> None:
    """Run the seed script standalone."""
    logging.basicConfig(level=logging.INFO)
    settings = Settings()
    db = Database(settings.database_path)
    await db.connect()
    try:
        await seed_database(db)
        print("Database seeded successfully.")  # noqa: T201
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
