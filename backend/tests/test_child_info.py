"""Tests for child info queries — exercises the DB + date resolution."""


import pytest
import pytest_asyncio

from backend.app.db.database import Database
from backend.app.db.seed import seed_database
from backend.app.services.child_info import query_child_info


@pytest_asyncio.fixture
async def seeded_db(tmp_path):
    """Create a temporary seeded database for testing."""
    db_path = str(tmp_path / "test.db")
    db = Database(db_path)
    await db.connect()
    await seed_database(db)
    yield db
    await db.close()


class TestQueryChildInfo:
    @pytest.mark.asyncio
    async def test_overview_returns_child_data(self, seeded_db: Database) -> None:
        # Sofia Martinez is child_id 6 (6th inserted)
        result = await query_child_info(seeded_db, 6, "overview")
        assert "Sofia" in result["data"]["child_name"]
        assert result["data"]["classroom"] == "Butterfly Room"
        assert result["data"]["age"] == 4

    @pytest.mark.asyncio
    async def test_nonexistent_child_returns_error(self, seeded_db: Database) -> None:
        result = await query_child_info(seeded_db, 999, "overview")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_meals_returns_list(self, seeded_db: Database) -> None:
        result = await query_child_info(seeded_db, 1, "meals", day_offset=0)
        assert result["info_type"] == "meals"
        # Should have meals data (might be empty if today is weekend)
        assert isinstance(result["data"], list)

    @pytest.mark.asyncio
    async def test_meals_have_temporal_hint(self, seeded_db: Database) -> None:
        result = await query_child_info(seeded_db, 1, "meals", day_offset=0)
        if result["data"]:  # Only if today is a weekday
            for meal in result["data"]:
                assert meal["temporal_hint"] in ("past", "future")

    @pytest.mark.asyncio
    async def test_allergies_returns_data(self, seeded_db: Database) -> None:
        # Liam (child_id 1) has dairy allergy
        result = await query_child_info(seeded_db, 1, "allergies")
        assert result["info_type"] == "allergies"
        assert len(result["data"]) >= 1
        assert "Dairy" in result["data"][0]["description"]

    @pytest.mark.asyncio
    async def test_child_with_no_allergies(self, seeded_db: Database) -> None:
        # Ava (child_id 2) has no allergies
        result = await query_child_info(seeded_db, 2, "allergies")
        assert result["data"] == []

    @pytest.mark.asyncio
    async def test_emergency_contacts_includes_doctor(
        self, seeded_db: Database
    ) -> None:
        result = await query_child_info(seeded_db, 1, "emergency_contacts")
        contacts = result["data"]
        relationships = [c["relationship"] for c in contacts]
        assert "Pediatrician" in relationships

    @pytest.mark.asyncio
    async def test_payments_returns_formatted_currency(
        self, seeded_db: Database
    ) -> None:
        result = await query_child_info(seeded_db, 1, "payments")
        assert result["data"]
        payment = result["data"][0]
        assert payment["current_balance"].startswith("$")
        assert payment["weekly_fee"].startswith("$")

    @pytest.mark.asyncio
    async def test_attendance_returns_data(self, seeded_db: Database) -> None:
        result = await query_child_info(seeded_db, 1, "attendance", day_offset=0)
        assert result["info_type"] == "attendance"
        assert isinstance(result["data"], list)

    @pytest.mark.asyncio
    async def test_field_trips_for_butterfly_room(self, seeded_db: Database) -> None:
        # Sofia (child_id 6) is in Butterfly Room
        result = await query_child_info(seeded_db, 6, "field_trips")
        assert isinstance(result["data"], list)
        # Should find field trips that include Butterfly Room
