"""Download the CABQ Family Handbook PDF to backend/data/handbook.pdf."""

import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

HANDBOOK_URL = (
    "https://www.cabq.gov/family/documents/"
    "2019-division-of-child-and-family-development-family-handbook-final.pdf"
)
DEST = Path(__file__).resolve().parent.parent / "data" / "handbook.pdf"


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    if DEST.exists():
        logger.info("Handbook already exists at %s — skipping download", DEST)
        return

    DEST.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading handbook from %s ...", HANDBOOK_URL)

    with httpx.Client(follow_redirects=True, timeout=60) as client:
        resp = client.get(HANDBOOK_URL)
        resp.raise_for_status()
        DEST.write_bytes(resp.content)

    logger.info("Saved handbook (%d bytes) to %s", len(resp.content), DEST)


if __name__ == "__main__":
    main()
