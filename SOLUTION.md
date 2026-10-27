# TAM Ticket Triage — Solution

## 1. Design
The system uses Gemini (`gemini-3.1-flash-lite`) in a bounded,
model-directed tool loop. The model chooses its next lookup, reads the
result, and decides whether to gather more evidence or finish.

Five read-only tools provide account resolution, account context,
ticket-history search, KB search, and full-article retrieval.
Account resolution uses explicit ID, company-name, contact-name, and
available email-domain evidence. History and KB retrieval use TF-IDF;
history excludes the current ticket and future submissions.

Finish checks require identity, history, and KB evidence, account
context for resolved identities, and relevant KB citations. P1/P2 cases
in Business/Enterprise accounts or within 90 days of renewal require
escalation and TAM notification. Pydantic validates the final output.
Traces record concise decision summaries, actual tool inputs/results,
and rejected finish attempts. Invalid JSON and output validation failures
have bounded correction paths; API rate limits and timeouts have retries.

## 2. Evaluation
Completed checks: 14 offline tests pass; all 10 generated review outputs
pass schema validation. These results do not establish decision accuracy.

Before production, I would:
- Compare category and priority against human-reviewed labels.
- Measure account-resolution precision and ambiguity handling.
- Measure duplicate precision and recall using verified pairs.
- Audit escalation and TAM notifications against agreed policy.
- Review KB grounding, unsupported claims, and customer-reply information leaks.
- Track latency, API cost, tool failures, and completion rate.

## 3. Scale at 10x
For 30,000 tickets and 4,000 articles, persist inverted indexes and
partition history by verified account to reduce search latency. Retrieve
KB sections with heading/version metadata rather than full articles.
Cache stable content, bound context and tool budgets, and use limited
concurrency that respects API quotas to control latency and cost.
Benchmark hybrid keyword/vector retrieval and reranking against labeled
queries before adopting them; a vector database alone does not guarantee
better retrieval quality.

## 4. Limitations
The supplied assets contain 500 tickets, 50 accounts, and nine KB articles.
Most raw account IDs are unmatched; ambiguous identities remain explicit.
Email/domain fields, monthly usage history, and a complete incident-priority
policy were unavailable. Priority interpretation and the 90-day renewal
window are implementation assumptions, not supplied company policy.

The brief's original schema and review set were absent, so local versions
were created; compatibility with an unavailable official contract is
unverified. Structural validation cannot guarantee correct diagnosis,
polite replies, or absence of internal leaks. Human review remains necessary.

## 5. How to Run
Create and activate a Python virtual environment, then run:
`python -m pip install -r requirements.txt`

Set `GEMINI_API_KEY` securely in the process environment. The defaults are
`TAM_LLM_PROVIDER=gemini` and `TAM_MODEL=gemini-3.1-flash-lite`.
`TAM_API_KEY` is an optional fallback; `.env` is not loaded automatically.

Run:
- `python -m unittest discover -s tests -v`
- `python run.py --ticket TKT-10000`
- `python run.py --set review`
- `python scripts/check_outputs.py`

Results are saved in `outputs/<ticket_id>.json`; execution metadata appends
to `outputs/run_log.jsonl`. Retry individual failures with `--ticket`.