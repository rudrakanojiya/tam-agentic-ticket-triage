from datetime import date
import json
import unittest
from tam_agent.agent import AgentError, triage
from tam_agent.tools import (Index, build_context, get_account_context, get_kb_article,
                             resolve_account, search_kb, search_ticket_history)
from test_phase1 import FIXTURE


class Phase2Tests(unittest.TestCase):
    def setUp(self):
        self.ctx = build_context(as_of=date(2026, 2, 1))

    def test_resolve_account_and_context(self):
        a = self.ctx['accounts'][0]
        result = resolve_account(a['company'], raw_account_id='unmatched', ctx=self.ctx)
        self.assertEqual(result['status'], 'matched')
        self.assertEqual(result['match']['account_id'], a['account_id'])
        self.assertEqual(resolve_account('unknown customer', ctx=self.ctx)['status'], 'unresolved')
        self.assertEqual(get_account_context(a['account_id'], ctx=self.ctx)['account'], a)
        contact_result = resolve_account(a['primary_contact']['name'], ctx=self.ctx)
        self.assertIn(a['account_id'], [c['account_id'] for c in contact_result['candidates']])
        self.assertEqual(contact_result['status'], 'ambiguous')
        a['domain'] = 'example.test'
        self.assertEqual(resolve_account('', 'person@example.test', ctx=self.ctx)['status'], 'matched')
        self.ctx['accounts'].append(dict(a, account_id='OTHER'))
        self.assertEqual(resolve_account(a['company'], ctx=self.ctx)['status'], 'ambiguous')

    def test_kb_and_cross_reference(self):
        results = search_kb('support SLA Enterprise', ctx=self.ctx)
        self.assertTrue(results)
        article = get_kb_article(results[0]['article_id'], ctx=self.ctx)
        self.assertIn('SLA', article['content'])
        onboarding = get_kb_article('onboarding/onboarding-guide', ctx=self.ctx)
        self.assertTrue(onboarding['cross_references'])
        self.assertIn('content', get_kb_article('authentication-sso', ctx=self.ctx))

    def test_history_excludes_self_future_and_wrong_customer(self):
        sample = dict(self.ctx['tickets'][0])
        sample.update(ticket_id='TKT-1', created_at='2026-02-01T00:00:00Z')
        prior = dict(sample, ticket_id='TKT-2', created_at='2026-01-01T00:00:00Z')
        future = dict(sample, ticket_id='TKT-3', created_at='2026-03-01T00:00:00Z')
        other = dict(prior, ticket_id='TKT-4', account_id='OTHER', company='OTHER')
        self.ctx.update(current_ticket=sample, tickets=[sample, prior, future, other],
                        ticket_index=Index([t['body'] for t in [sample, prior, future, other]]))
        results = search_ticket_history(sample['account_id'], sample['body'], ctx=self.ctx)
        self.assertEqual([r['ticket_id'] for r in results], ['TKT-2'])

    def test_model_directed_branch_and_validation_repair(self):
        seen = []
        def model(messages):
            seen.append(messages[-1]['content'])
            if len(seen)==1:
                return dict(summary='Need SLA evidence', action='search_kb', input=dict(query='support SLA'))
            if len(seen)==2:
                obs = json.loads(messages[-1]['content'].split(': ',1)[1])
                return dict(summary='Inspect retrieved source', action='get_kb_article',
                            input=dict(article_id_or_title=obs[0]['article_id']))
            if len(seen)==3:
                return dict(summary='Draft', action='finish', output=FIXTURE | dict(priority='invalid'))
            self.assertIn('validation failed', messages[-1]['content'])
            return dict(summary='Corrected draft', action='finish', output=FIXTURE)
        self.ctx['allow_unverified_finish'] = True
        self.ctx['llm'] = model
        output = triage(self.ctx['tickets'][0], self.ctx)
        self.assertEqual(len(output['reasoning_trace']), 4)
        self.assertEqual(json.loads(output['reasoning_trace'][1]['action'])['tool'], 'get_kb_article')
        # A second model path can finish without following the first path.
        self.ctx['llm'] = lambda messages: dict(summary='Evidence already provided', action='finish', output=FIXTURE)
        self.assertEqual(len(triage(self.ctx['tickets'][0], self.ctx)['reasoning_trace']), 1)

    def test_malformed_response_is_retried(self):
        calls = []
        def model(messages):
            calls.append(1)
            if len(calls)==1:
                raise json.JSONDecodeError('truncated', '{', 1)
            return dict(summary='Corrected response', action='finish', output=FIXTURE)
        self.ctx.update(llm=model, allow_unverified_finish=True)
        result = triage(self.ctx['tickets'][0], self.ctx)
        self.assertEqual(result['reasoning_trace'][0]['action'], 'invalid_response')
        self.assertEqual(len(calls), 2)

    def test_finish_requires_observed_evidence(self):
        self.ctx.update(max_steps=2, llm=lambda messages: dict(
            summary='Premature finish', action='finish', output=FIXTURE))
        with self.assertRaisesRegex(AgentError, 'budget'):
            triage(self.ctx['tickets'][0], self.ctx)

    def test_budget_and_missing_model(self):
        with self.assertRaises(AgentError):
            triage(self.ctx['tickets'][0], self.ctx)
        self.ctx.update(max_steps=2, llm=lambda messages: dict(summary='Try tool', action='unknown', input={}))
        with self.assertRaisesRegex(AgentError, 'budget'):
            triage(self.ctx['tickets'][0], self.ctx)


if __name__=='__main__':
    unittest.main()
