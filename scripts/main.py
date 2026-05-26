"""Orchestriert die tägliche SAP-News-Pipeline: research → render → cleanup."""
from __future__ import annotations

import logging
import sys

from cleanup import cleanup
from render import render_all
from research import run_research

logger = logging.getLogger("main")


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("=== Schritt 1: Recherche ===")
    try:
        run_research()
    except Exception as exc:
        logger.exception("Recherche fehlgeschlagen: %s", exc)
        return 1

    logger.info("=== Schritt 2: Rendering ===")
    try:
        render_all()
    except Exception as exc:
        logger.exception("Rendering fehlgeschlagen: %s", exc)
        return 1

    logger.info("=== Schritt 3: Cleanup ===")
    try:
        cleanup()
    except Exception as exc:
        logger.exception("Cleanup fehlgeschlagen: %s", exc)
        return 1

    logger.info("Pipeline erfolgreich abgeschlossen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
