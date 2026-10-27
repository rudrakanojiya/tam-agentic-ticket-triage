"""Validate outputs/<ticket_id>.json for each ID in the review set."""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tam_agent.schema import validate_output
from pydantic import ValidationError


def load_review_set(path: Path) -> list[str]:
    ids = [line.strip() for line in path.read_text(encoding='utf-8-sig').splitlines()
           if line.strip() and not line.lstrip().startswith('#')]
    if len(ids) != 10 or len(set(ids)) != 10:
        raise ValueError('review set must contain exactly 10 unique ticket IDs')
    if any(not re.fullmatch(r'TKT-\d+', ticket_id) for ticket_id in ids):
        raise ValueError('invalid ticket ID in review set')
    return ids


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review-set', type=Path, default=ROOT / 'data/review_set.txt')
    parser.add_argument('--outputs-dir', type=Path, default=ROOT / 'outputs')
    args = parser.parse_args(argv)
    try:
        ids = load_review_set(args.review_set)
    except (OSError, ValueError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        return 1
    passed = 0
    for ticket_id in ids:
        try:
            data = json.loads((args.outputs_dir / f'{ticket_id}.json').read_text(encoding='utf-8-sig'))
            output = validate_output(data)
            if output.duplicate_of_ticket_id == ticket_id:
                raise ValueError('a ticket cannot duplicate itself')
        except (OSError, ValueError, ValidationError) as exc:
            print(f'FAIL {ticket_id}: {exc}')
        else:
            passed += 1
            print(f'PASS {ticket_id}')
    print(f'{passed}/{len(ids)} valid')
    return 0 if passed == len(ids) else 1


if __name__ == '__main__':
    raise SystemExit(main())
