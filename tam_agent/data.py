"""Pure UTF-8 JSON loaders. No joins, search, inference, or mutation."""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / 'data'


def _load_records(path: str | Path) -> list[dict]:
    path = Path(path)
    rows = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError(f'{path}: expected a JSON array of objects')
    return rows


def load_tickets(path: str | Path = DATA_DIR / 'tickets.json') -> list[dict]:
    return _load_records(path)


def load_accounts(path: str | Path = DATA_DIR / 'accounts.json') -> list[dict]:
    return _load_records(path)


def load_usage_metrics(path: str | Path = DATA_DIR / 'usage_metrics.json') -> list[dict]:
    """Load supplied metrics; raises FileNotFoundError when unavailable.

    No metrics file was provided. Do not fabricate monthly history from the
    account-level usage_trend and seat-count snapshots.
    """
    return _load_records(path)
