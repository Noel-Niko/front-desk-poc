"""Dashboard service — analytics queries against the shared SQLite database."""

import json
from datetime import datetime

from backend.app.db.database import Database


class DashboardService:
    """Queries for the operator dashboard."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def list_sessions(
        self,
        min_rating: int | None = None,
        transferred_only: bool = False,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict]:
        """List sessions with optional filters, ordered by most recent first."""
        conditions = []
        params: list = []

        if min_rating is not None:
            conditions.append("rating >= ?")
            params.append(min_rating)
        if transferred_only:
            conditions.append("transferred_to_human = 1")
        if date_from is not None:
            conditions.append("started_at >= ?")
            params.append(date_from)
        if date_to is not None:
            conditions.append("started_at <= ?")
            params.append(date_to)

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        rows = await self._db.fetch_all(
            f"""SELECT id, started_at, ended_at, input_mode,
                      transferred_to_human, transfer_reason,
                      security_code_used, child_id, rating, rating_feedback
               FROM sessions
               {where_clause}
               ORDER BY started_at DESC""",
            tuple(params),
        )
        return [dict(r) for r in rows]

    async def get_session(self, session_id: str) -> dict | None:
        """Get session detail with all messages."""
        session = await self._db.fetch_one(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        )
        if session is None:
            return None

        messages = await self._db.fetch_all(
            """SELECT id, role, content, citations, tool_used, timestamp
               FROM messages
               WHERE session_id = ?
               ORDER BY timestamp ASC""",
            (session_id,),
        )

        result = dict(session)
        result["messages"] = []
        for m in messages:
            msg = dict(m)
            if msg.get("citations"):
                msg["citations"] = json.loads(msg["citations"])
            result["messages"].append(msg)

        return result

    async def get_stats(self) -> dict:
        """Get KPI stats for the dashboard."""
        total_sessions = await self._db.fetch_one(
            "SELECT COUNT(*) as cnt FROM sessions"
        )
        total_messages = await self._db.fetch_one(
            "SELECT COUNT(*) as cnt FROM messages"
        )
        transferred = await self._db.fetch_one(
            "SELECT COUNT(*) as cnt FROM sessions WHERE transferred_to_human = 1"
        )
        tool_usage = await self._db.fetch_all(
            """SELECT tool_used, COUNT(*) as cnt
               FROM messages
               WHERE tool_used IS NOT NULL
               GROUP BY tool_used
               ORDER BY cnt DESC"""
        )

        rating_stats = await self._db.fetch_one(
            "SELECT AVG(rating) as avg_rating, COUNT(rating) as rating_count FROM sessions WHERE rating IS NOT NULL"
        )

        total = total_sessions["cnt"] if total_sessions else 0
        xfer = transferred["cnt"] if transferred else 0

        return {
            "total_sessions": total,
            "total_messages": total_messages["cnt"] if total_messages else 0,
            "transferred_count": xfer,
            "transfer_rate": round(xfer / total * 100, 1) if total > 0 else 0,
            "tool_usage": [dict(r) for r in tool_usage],
            "avg_rating": round(rating_stats["avg_rating"], 1)
            if rating_stats and rating_stats["avg_rating"]
            else 0,
            "rating_count": rating_stats["rating_count"] if rating_stats else 0,
        }

    async def get_struggles(self) -> list[dict]:
        """Get sessions where the system struggled (transfers or no tool used)."""
        rows = await self._db.fetch_all(
            """SELECT s.id, s.started_at, s.transfer_reason, s.input_mode,
                      COUNT(m.id) as message_count
               FROM sessions s
               LEFT JOIN messages m ON s.id = m.session_id
               WHERE s.transferred_to_human = 1
               GROUP BY s.id
               ORDER BY s.started_at DESC"""
        )
        return [dict(r) for r in rows]

    async def get_rating_distribution(self) -> list[dict]:
        """Get count of sessions per rating value (1-5)."""
        rows = await self._db.fetch_all(
            """SELECT rating, COUNT(*) as count
               FROM sessions
               WHERE rating IS NOT NULL
               GROUP BY rating
               ORDER BY rating"""
        )
        return [dict(r) for r in rows]

    async def get_citation_frequency(self) -> list[dict]:
        """Get most frequently cited handbook pages."""
        rows = await self._db.fetch_all(
            "SELECT citations FROM messages WHERE citations IS NOT NULL"
        )
        page_counts: dict[int, int] = {}
        for row in rows:
            try:
                citations = json.loads(row["citations"])
                for c in citations:
                    page = c.get("page")
                    if page is not None:
                        page_counts[page] = page_counts.get(page, 0) + 1
            except (json.JSONDecodeError, TypeError):
                continue

        result = [
            {"page": page, "count": count}
            for page, count in sorted(page_counts.items(), key=lambda x: -x[1])
        ]
        return result

    async def get_low_rating_sessions(self) -> list[dict]:
        """Get sessions with rating <= 2 (needs attention)."""
        rows = await self._db.fetch_all(
            """SELECT id, started_at, rating, rating_feedback, transfer_reason
               FROM sessions
               WHERE rating IS NOT NULL AND rating <= 2
               ORDER BY started_at DESC"""
        )
        return [dict(r) for r in rows]

    async def list_faq_overrides(self) -> list[dict]:
        """List all active FAQ overrides."""
        rows = await self._db.fetch_all(
            """SELECT id, question_pattern, answer, created_by,
                      created_at, updated_at, active
               FROM operator_faq_overrides
               WHERE active = 1
               ORDER BY created_at DESC"""
        )
        return [dict(r) for r in rows]

    async def create_faq_override(self, question_pattern: str, answer: str) -> dict:
        """Create a new FAQ override."""
        now = datetime.now().isoformat()
        row_id = await self._db.insert(
            """INSERT INTO operator_faq_overrides
               (question_pattern, answer, created_by, created_at, active)
               VALUES (?, ?, 'Operator', ?, 1)""",
            (question_pattern, answer, now),
        )
        return {
            "id": row_id,
            "question_pattern": question_pattern,
            "answer": answer,
            "created_by": "Operator",
            "created_at": now,
            "active": 1,
        }

    async def update_faq_override(self, override_id: int, updates: dict) -> dict | None:
        """Update an existing FAQ override."""
        existing = await self._db.fetch_one(
            "SELECT * FROM operator_faq_overrides WHERE id = ?", (override_id,)
        )
        if existing is None:
            return None

        answer = updates.get("answer", existing["answer"])
        question_pattern = updates.get("question_pattern", existing["question_pattern"])
        now = datetime.now().isoformat()

        await self._db.execute(
            """UPDATE operator_faq_overrides
               SET question_pattern = ?, answer = ?, updated_at = ?
               WHERE id = ?""",
            (question_pattern, answer, now, override_id),
        )

        return {
            "id": override_id,
            "question_pattern": question_pattern,
            "answer": answer,
            "created_by": existing["created_by"],
            "created_at": existing["created_at"],
            "updated_at": now,
            "active": existing["active"],
        }

    async def delete_faq_override(self, override_id: int) -> None:
        """Soft-delete a FAQ override (set active=0)."""
        await self._db.execute(
            "UPDATE operator_faq_overrides SET active = 0 WHERE id = ?",
            (override_id,),
        )

    async def list_tour_requests(self) -> list[dict]:
        """List all tour requests ordered by most recent."""
        rows = await self._db.fetch_all(
            """SELECT id, parent_name, parent_phone, parent_email,
                      child_age, preferred_date, notes, status, created_at
               FROM tour_requests
               ORDER BY created_at DESC"""
        )
        return [dict(r) for r in rows]
