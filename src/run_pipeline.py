"""Run the full pipeline: extract -> stage -> validate -> transform -> load -> marts."""
import argparse
import logging
import sys
from pathlib import Path

import extract
import load
import marts
import transform
import validate
from config import DB_PATH, LOG_DIR, OUT_DIR, SAMPLE_DIR

log = logging.getLogger("pipeline")


def run(input_dir, db_path=DB_PATH, out_dir=OUT_DIR, today=None, reset=False):
    db_path = Path(db_path)
    if reset and db_path.exists():
        db_path.unlink()
        log.info("Deleted existing warehouse %s", db_path)

    conn = load.connect(db_path)
    run_id = load.start_run(conn)
    stats = {"rows_read": 0, "rows_rejected": 0, "duplicates_dropped": 0, "rows_inserted": 0}
    try:
        raw = extract.read_sources(input_dir)
        if raw.empty:
            raise ValueError(f"No recognised source files in {input_dir}")
        stats["rows_read"] = len(raw)
        load.stage(conn, raw, run_id)

        valid, rejects = validate.validate(raw, today=today)
        stats["rows_rejected"] = len(rejects)
        load.load_rejects(conn, rejects, run_id)
        for reason, n in rejects["reason"].value_counts().items():
            log.warning("Rejected %d row(s): %s", n, reason)

        clean, dups = transform.transform(valid)
        stats["duplicates_dropped"] = dups
        stats["rows_inserted"] = load.load_warehouse(conn, clean)

        marts.build(conn)
        marts.export(conn, out_dir)
        load.finish_run(conn, run_id, "success", **stats)
        log.info("Run %d OK: read=%d rejected=%d duplicates=%d inserted=%d", run_id,
                 stats["rows_read"], stats["rows_rejected"],
                 stats["duplicates_dropped"], stats["rows_inserted"])
        return stats
    except Exception as exc:
        load.finish_run(conn, run_id, "failed", error=str(exc), **stats)
        log.exception("Run %d failed", run_id)
        raise
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", default=str(SAMPLE_DIR), help="folder with source files")
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--out", default=str(OUT_DIR), help="folder for dashboard JSON")
    ap.add_argument("--reset", action="store_true", help="delete the warehouse first")
    a = ap.parse_args()

    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(LOG_DIR / "pipeline.log")])
    try:
        run(a.input, a.db, a.out, reset=a.reset)
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
