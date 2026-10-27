"""Run the review set using a configured live language model."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from tam_agent.agent import triage
from tam_agent.llm import JSONModel, ModelError
from tam_agent.tools import build_context
from scripts.check_outputs import load_review_set

ROOT = Path(__file__).resolve().parent


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--set', choices=['review'], default='review')
    parser.add_argument('--ticket', help='Run just this ticket for an initial smoke check')
    parser.add_argument('--outputs-dir', type=Path, default=ROOT / 'outputs')
    args = parser.parse_args(argv)
    ids = [args.ticket] if args.ticket else load_review_set(ROOT / 'data/review_set.txt')
    try:
        model = JSONModel()
    except ModelError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    ctx = build_context(llm=model)
    ctx['on_action'] = lambda action: print(f'  action: {action}', flush=True)
    ctx['on_observation'] = lambda action, result: print('  tool error: '+str(result['error']), flush=True) if isinstance(result, dict) and 'error' in result else None
    lookup = {t['ticket_id']:t for t in ctx['tickets']}
    if any(ticket_id not in lookup for ticket_id in ids):
        parser.error('Unknown ticket ID')
    args.outputs_dir.mkdir(parents=True, exist_ok=True)
    failures = 0
    for ticket_id in ids:
        started = time.monotonic()
        record = dict(ticket_id=ticket_id, timestamp=datetime.now(timezone.utc).isoformat(),
                      provider=model.provider, model=model.model)
        try:
            # Historical review: account snapshots are supplied, but renewal is
            # assessed at ticket creation rather than the machine's current date.
            ctx['as_of'] = datetime.fromisoformat(lookup[ticket_id]['created_at'].replace('Z','+00:00')).date()
            output = triage(lookup[ticket_id], ctx)
            target = args.outputs_dir / f'{ticket_id}.json'
            temporary = target.with_suffix('.json.tmp')
            temporary.write_text(json.dumps(output, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
            temporary.replace(target)
            record.update(status='success', steps=len(output['reasoning_trace']), as_of=str(ctx['as_of']))
            print(f'PASS {ticket_id}: {len(output["reasoning_trace"])} steps')
        except Exception as exc:
            failures += 1
            # Do not log raw provider responses, credentials, or prompt content.
            record.update(status='failed', error_type=type(exc).__name__)
            detail = str(exc) if isinstance(exc, ModelError) else type(exc).__name__
            print(f'FAIL {ticket_id}: {detail}', file=sys.stderr)
        record['elapsed_seconds'] = round(time.monotonic()-started, 3)
        with (args.outputs_dir / 'run_log.jsonl').open('a', encoding='utf-8') as log:
            log.write(json.dumps(record)+'\n')
    return 1 if failures else 0


if __name__=='__main__':
    raise SystemExit(main())
