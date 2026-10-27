import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from pydantic import ValidationError
from tam_agent.data import load_tickets, load_accounts, load_usage_metrics
from tam_agent.kb import load_kb_articles
from tam_agent.schema import validate_output

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = dict(category='Bug', priority='P2', routing='Support', escalation=False,
               tam_notification=False, duplicate_status=False, duplicate_of_ticket_id=None,
               clarification_needed=True, customer_reply='Could you share the error code?',
               internal_note='Account unavailable; SLA unknown; KB lookup pending.',
               reasoning_trace=[dict(thought='More evidence needed', action='request_details',
                                     observation='No error code', outcome='Clarification needed')])


class Phase1Tests(unittest.TestCase):
    def test_real_assets(self):
        self.assertEqual(len(load_tickets()), 500)
        self.assertEqual(len(load_accounts()), 50)
        self.assertEqual(len(load_kb_articles()), 9)
        with self.assertRaises(FileNotFoundError):
            load_usage_metrics()
        ids = (ROOT / 'data/review_set.txt').read_text().splitlines()
        self.assertEqual(len(set(ids)), 10)
        self.assertTrue(set(ids) <= {t['ticket_id'] for t in load_tickets()})

    def test_strict_contract(self):
        validate_output(FIXTURE)
        for patch in [dict(escalation='false'), dict(priority='High'), dict(extra=True),
                      dict(duplicate_status=True), dict(reasoning_trace=[]),
                      dict(customer_reply='  ')]:
            with self.subTest(patch=patch), self.assertRaises(ValidationError):
                validate_output(FIXTURE | patch)
        missing = copy.deepcopy(FIXTURE)
        del missing['routing']
        with self.assertRaises(ValidationError):
            validate_output(missing)
        validate_output(FIXTURE | dict(duplicate_status=True, duplicate_of_ticket_id='TKT-10035'))

    def test_cli_success_missing_invalid_and_self_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            ids = (ROOT / 'data/review_set.txt').read_text().splitlines()
            def run():
                return subprocess.run([sys.executable, str(ROOT / 'scripts/check_outputs.py'),
                                       '--outputs-dir', directory], cwd=directory, capture_output=True, text=True)
            self.assertEqual(run().returncode, 1)
            for ticket_id in ids:
                (out / f'{ticket_id}.json').write_text(json.dumps(FIXTURE))
            result = run()
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('10/10 valid', result.stdout)
            target = out / f'{ids[0]}.json'
            target.write_text('{broken')
            self.assertEqual(run().returncode, 1)
            target.write_text(json.dumps(FIXTURE | dict(duplicate_status=True, duplicate_of_ticket_id=ids[0])))
            self.assertEqual(run().returncode, 1)


if __name__ == '__main__':
    unittest.main()
