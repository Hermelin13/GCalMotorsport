"""Monthly sync: zero Discord noise if nothing changes; nonzero exit on failures."""
import logging
import os
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv
from .sources import SERIES, deduplicate, fetch_ics, load_overrides
from .google_calendar import service_from_env, synchronize
from .discord import notify

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def main() -> int:
    load_dotenv()
    dry_run = os.getenv("DRY_RUN", "true").lower() != "false"
    calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "").strip()
    webhook = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    from .auto_sources import load_all
    now_year = datetime.now(timezone.utc).year
    events, failures, pending = load_all({now_year, now_year + 1})
    changes = []
    logging.info("Unconfirmed start times (not scheduled): %s", "; ".join(pending) or "none")
    try:
        events += load_overrides(os.getenv("OVERRIDES_FILE", "config/starts.json"))
        events = deduplicate(events)
        # Ignore historical seasons; sync present and next year only.
        events = [e for e in events if e.start.year in {now_year, now_year + 1}]
        if not calendar_id:
            raise ValueError("GOOGLE_CALENDAR_ID is missing")
        if events:
            svc = service_from_env(os.environ)
            changes = synchronize(svc, calendar_id, events, dry_run,
                                  os.getenv("TIMEZONE", "Europe/Prague"))
        else:
            failures.append("Žádné platné závody k synchronizaci")
    except Exception as exc:
        failures.append(f"Calendar: {exc}")
    try:
        notify(webhook, changes, failures, dry_run)
    except Exception as exc:
        logging.error("Discord notification failed: %s", exc)
        failures.append("Discord notification failed")
    logging.info("events=%s changes=%s failures=%s dry_run=%s", len(events), len(changes), len(failures), dry_run)
    for failure in failures:
        logging.error(failure)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
