# TAM Agentic Ticket Triage

An AI-assisted support-ticket triage system built for the TAM internship assessment.

The system uses Google Gemini to select tools, gather customer and technical context, and produce a structured triage recommendation. Python executes the tools and validates the final output.

## What It Does

For each ticket, the agent:

- Resolves the customer account using available identity evidence.
- Retrieves account tier, renewal timing, usage snapshots, and escalation notes.
- Searches previous tickets for recurring issues or potential duplicates.
- Retrieves relevant knowledge-base documentation.
- Recommends category, priority, routing, escalation, and TAM notification.
- Drafts a customer reply and an internal note.
- Records tool inputs, observations, and concise decision summaries.

The model chooses the lookup order. Finish-time checks reject answers that lack required evidence or fail validation.

## Workflow

```text
Ticket
  → Gemini selects a tool
  → Python executes the tool
  → Gemini reviews the observation
  → Additional lookup or final decision
  → Evidence checks and schema validation
  → Output JSON and execution log
```

## Project Structure

```text
starter-repo/
├── data/
│   ├── tickets.json
│   ├── accounts.json
│   └── review_set.txt
├── knowledge-base/
│   ├── products/
│   ├── troubleshooting/
│   ├── billing/
│   └── onboarding/
├── tam_agent/
│   ├── agent.py          # Model-directed tool loop and finish checks
│   ├── tools.py          # Account lookup and TF-IDF retrieval
│   ├── llm.py            # Model API clients and retry handling
│   ├── schema.py         # Strict Pydantic output contract
│   ├── data.py           # JSON loaders
│   └── kb.py             # Markdown loader
├── scripts/
│   └── check_outputs.py
├── tests/
├── outputs/
├── run.py
├── requirements.txt
├── DATA_SCHEMA.md
└── SOLUTION.md
```

## Agent Tools

| Tool | Purpose |
|---|---|
| `resolve_account` | Match explicit account ID, company, contact, or available email-domain evidence |
| `get_account_context` | Retrieve account metadata, renewal timing, metrics, and escalation notes |
| `search_ticket_history` | Rank similar historical tickets using TF-IDF |
| `search_kb` | Retrieve relevant Markdown articles using TF-IDF |
| `get_kb_article` | Read a complete article or follow a reference |

History searches exclude the current ticket and future submissions. Ambiguous account matches remain explicit.

## Dataset

The supplied assets contain:

- **500** synthetic support tickets.
- **50** synthetic account summaries.
- **9** Markdown knowledge-base articles.
- A locally selected review set of **10** real ticket IDs.

Most raw ticket account IDs do not match the accounts table. Some category and urgency labels are inconsistent with the ticket descriptions.

Monthly usage metrics were not supplied. Account-level snapshots are used where available.

See [DATA_SCHEMA.md](DATA_SCHEMA.md) for field definitions.

## Setup

Python 3.12 is recommended.

### Windows PowerShell

From the repository root:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Set the provider and model:

```powershell
$env:TAM_LLM_PROVIDER = "gemini"
$env:TAM_MODEL = "gemini-3.1-flash-lite"
```

Enter the API key securely. Run this command, paste the actual key when prompted, and press Enter:

```powershell
$secureKey = Read-Host "Gemini API key" -AsSecureString
```

Then run:

```powershell
$env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new("", $secureKey).Password.Trim()
Remove-Variable secureKey
```

These variables apply to the current terminal session.

The application reads process environment variables directly; it does not automatically load `.env` files. `TAM_API_KEY` is an optional fallback, not an additional required key.

Never commit API keys or `.env` files.

## Run

### 1. Offline tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

### 2. Single-ticket smoke test

```powershell
.\.venv\Scripts\python.exe run.py --ticket TKT-10000
```

### 3. Generate the review outputs

```powershell
.\.venv\Scripts\python.exe run.py --set review
```

### 4. Validate the outputs

```powershell
.\.venv\Scripts\python.exe scripts/check_outputs.py
```

Expected result:

```text
10/10 valid
```

On macOS/Linux, create and activate a virtual environment, install the same requirements, export the environment variables, and use `python` instead of the Windows executable path.

## Outputs

Each completed ticket is saved as:

```text
outputs/<ticket_id>.json
```

The output includes category, priority, routing, escalation, TAM notification, duplicate information, clarification status, customer reply, internal note, and `reasoning_trace`.

Execution metadata appends to:

```text
outputs/run_log.jsonl
```

A printed `action: finish` is an attempted finish. The runtime may reject it and request more evidence before reporting `PASS`.

## Validation and Results

Verified results:

- **14 offline tests passed.**
- **10/10 review outputs passed schema validation.**

Checks cover strict field types, allowed values, required evidence, duplicate-field consistency, self-duplicate rejection, relevant KB citations, and mandatory critical-account escalation.

**Schema validity does not establish decision accuracy.** Human review is still needed to assess diagnosis, priority, citation support, and customer-reply quality.

## Retry Failed Tickets

The client includes bounded retries for temporary API rate limits and timeouts. Individual failures can be rerun without regenerating other tickets:

```powershell
.\.venv\Scripts\python.exe run.py --ticket TKT-10112
```

Then rerun the output checker. Failed tickets restart from the beginning; execution logs retain previous attempts.

## Limitations

- The supplied assets are smaller than the dataset described in the brief.
- The original fixed output schema and review set were unavailable; local versions were created.
- No monthly usage history or complete incident-priority policy was supplied.
- Priority interpretation and the 90-day renewal window are implementation assumptions.
- Email-domain matching requires explicit domain/email data, which is absent from the supplied accounts.
- Model instructions and structural checks cannot guarantee factual accuracy or prevent every internal-information leak.
- Live generation requires internet access, a valid API key, and available provider quota.

See [SOLUTION.md](SOLUTION.md) for the design, evaluation plan, scaling strategy, and limitations.
