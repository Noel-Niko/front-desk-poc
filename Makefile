.PHONY: setup backend frontend dashboard seed test dev clean

# Setup: install deps, download handbook, build index, seed database
setup:
	uv sync
	uv run python -m backend.scripts.download_handbook
	uv run python -m backend.scripts.build_index
	uv run python -m backend.app.db.seed

# Run backend API server on :8000
backend:
	uv run uvicorn backend.app.main:create_app --factory --host 0.0.0.0 --port 8000 --reload

# Run React frontend dev server on :5173
frontend:
	cd frontend && npm run dev

# Run operator dashboard on :8001
dashboard:
	uv run uvicorn backend.app.dashboard.server:create_app --factory --host 0.0.0.0 --port 8001 --reload

# Re-seed the database (destructive — resets to known state)
seed:
	uv run python -m backend.app.db.seed

# Run tests
test:
	uv run pytest backend/tests/ -v

# Run all three services (backend + frontend + dashboard)
dev:
	@echo "Starting backend on :8000, dashboard on :8001, frontend on :5173"
	@echo "Run each in a separate terminal:"
	@echo "  make backend"
	@echo "  make dashboard"
	@echo "  make frontend"

# Remove generated data (keeps handbook PDF)
clean:
	rm -rf backend/data/handbook_index/
	rm -f backend/data/frontdesk.db
