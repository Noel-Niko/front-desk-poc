"""Build the FAISS + BM25 index from the handbook PDF."""

import logging

from backend.app.config import Settings
from backend.app.services.handbook import build_index


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = Settings()
    index = build_index(settings.handbook_pdf_path, settings.handbook_index_path)
    print(f"Index built: {len(index.chunks)} chunks")  # noqa: T201


if __name__ == "__main__":
    main()
