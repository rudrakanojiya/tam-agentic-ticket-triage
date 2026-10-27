"""Read-only agent tools. All data and cached indexes live in the supplied context."""
from collections import Counter
from datetime import date
import math
from pathlib import PurePosixPath
import re
from urllib.parse import unquote
from .data import load_accounts, load_tickets
from .kb import load_kb_articles


def tokens(text):
    return re.findall(r'[a-z0-9]+', text.lower())


class Index:
    """Sparse TF-IDF cosine index built once per corpus."""
    def __init__(self, texts):
        counts = [Counter(tokens(t)) for t in texts]
        df = Counter(word for row in counts for word in row)
        self.idf = {w: math.log((1 + len(counts)) / (1 + n)) + 1 for w, n in df.items()}
        self.rows = [self.vector(row) for row in counts]

    def vector(self, counts):
        v = {w: n * self.idf[w] for w, n in counts.items() if w in self.idf}
        norm = math.sqrt(sum(x*x for x in v.values())) or 1
        return {w: x/norm for w, x in v.items()}

    def scores(self, text):
        q = self.vector(Counter(tokens(text)))
        return [sum(v.get(w, 0)*x for w, x in q.items()) for v in self.rows]


def build_context(*, llm=None, as_of=None):
    tickets, accounts, articles = load_tickets(), load_accounts(), load_kb_articles()
    return dict(tickets=tickets, accounts=accounts, articles=articles, llm=llm,
                as_of=as_of or date.today(),
                ticket_index=Index([t['subject']+' '+t['body'] for t in tickets]),
                kb_index=Index([a.title+' '+a.content for a in articles]))


def _phrase(phrase, text):
    return bool(phrase.strip()) and (' '+ ' '.join(tokens(phrase))+' ') in (' '+' '.join(tokens(text))+' ')


def resolve_account(query_text, sender_email='', raw_account_id='', *, ctx):
    candidates = []
    domain = sender_email.rpartition('@')[2].casefold() if '@' in sender_email else ''
    for a in ctx['accounts']:
        evidence = []
        if raw_account_id and a['account_id'] == raw_account_id:
            evidence.append(('account_id', 1.0))
        if _phrase(a['company'], query_text):
            evidence.append(('company_name', .95))
        if _phrase(a.get('primary_contact', {}).get('name', ''), query_text):
            evidence.append(('contact_name', .85))
        # Use explicit email/domain fields only; never invent domains from names.
        emails = [a.get('email', ''), a.get('primary_contact', {}).get('email', '')]
        domains = [a.get('domain', '')] + [e.rpartition('@')[2] for e in emails if '@' in e]
        if domain and domain in [d.casefold() for d in domains if d]:
            evidence.append(('email_domain', .95))
        if evidence:
            candidates.append(dict(account_id=a['account_id'], name=a['company'], tier=a['plan_tier'],
                                   renewal=a['renewal_date'], confidence=max(x[1] for x in evidence),
                                   evidence=[x[0] for x in evidence]))
    candidates.sort(key=lambda a: (-a['confidence'], a['account_id']))
    ambiguous = len(candidates)>1 and candidates[0]['confidence'] == candidates[1]['confidence']
    return dict(status='ambiguous' if ambiguous else 'matched' if candidates else 'unresolved',
                match=candidates[0] if candidates and not ambiguous else None, candidates=candidates)


def get_account_context(account_id, *, ctx):
    a = next((a for a in ctx['accounts'] if a['account_id']==account_id), None)
    if a is None:
        return dict(status='unresolved', account_id=account_id)
    return dict(status='matched', account=dict(a),
                support_tier='Enterprise' if a['plan_tier']=='Enterprise' else 'Standard',
                days_until_renewal=(date.fromisoformat(a['renewal_date'])-ctx['as_of']).days,
                metrics_source='Account snapshot only; monthly usage metrics unavailable',
                escalation_notes=a.get('escalation_notes', []))


def search_ticket_history(account_id, query_text, limit=5, *, ctx):
    if not 1 <= limit <= 20:
        raise ValueError('limit must be between 1 and 20')
    a = next((a for a in ctx['accounts'] if a['account_id']==account_id), None)
    current = ctx.get('current_ticket', {})
    company = a['company'] if a else current.get('company', '')
    scores = ctx['ticket_index'].scores(query_text)
    results = []
    for t, score in zip(ctx['tickets'], scores):
        if t['ticket_id']==current.get('ticket_id'):
            continue
        # Future tickets are not history for a historical review ticket.
        if current.get('created_at') and t['created_at'] > current['created_at']:
            continue
        same_id = bool(account_id) and t.get('account_id')==account_id
        same_company = bool(company) and t.get('company', '').casefold()==company.casefold()
        if (same_id or same_company) and score > 0:
            results.append(dict(ticket_id=t['ticket_id'], subject=t['subject'], body=t['body'],
                                status=t['status'], created_at=t['created_at'], score=round(score, 4),
                                identity_basis='account_id' if same_id else 'company_name'))
    return sorted(results, key=lambda t: (-t['score'], t['ticket_id']))[:limit]


def _article(a, score=None):
    links = re.findall(r'\[[^\]]+\]\(([^)]+)\)', a.content)
    result = dict(article_id=a.article_id, title=a.title, path=a.path,
                  cross_references=links)
    if score is not None:
        result.update(score=round(score, 4), excerpt=a.content[:1200])
    else:
        result['content'] = a.content
    return result


def search_kb(query, top_k=3, *, ctx):
    if not 1 <= top_k <= 10:
        raise ValueError('top_k must be between 1 and 10')
    ranked = sorted(zip(ctx['articles'], ctx['kb_index'].scores(query)), key=lambda x: -x[1])
    return [_article(a, score) for a, score in ranked if score>0][:top_k]


def get_kb_article(article_id_or_title, *, ctx):
    key = unquote(article_id_or_title).split('#')[0].removesuffix('.md').casefold()
    if key.startswith('../') or key.startswith('./'):
        key = PurePosixPath(key).name
    matches = [a for a in ctx['articles'] if key in
               {a.article_id.casefold(), a.title.casefold(), PurePosixPath(a.article_id).name.casefold()}]
    if len(matches)!=1:
        return dict(status='not_found_or_ambiguous', query=article_id_or_title)
    return _article(matches[0])


TOOLS = {f.__name__: f for f in [resolve_account, get_account_context, search_ticket_history,
                                search_kb, get_kb_article]}
TOOL_PARAMETERS = {
    'resolve_account': ({'query_text':'string', 'sender_email':'string', 'raw_account_id':'string'}, ['query_text']),
    'get_account_context': ({'account_id':'string'}, ['account_id']),
    'search_ticket_history': ({'account_id':'string', 'query_text':'string', 'limit':'integer'}, ['account_id','query_text']),
    'search_kb': ({'query':'string', 'top_k':'integer'}, ['query']),
    'get_kb_article': ({'article_id_or_title':'string'}, ['article_id_or_title']),
}
