# TAM Intern Task: Agentic Ticket Triage - Solution

## 1. Architecture & Design
The system uses a dynamic ReAct (Reason + Act) loop powered by the Gemini API (`gemini-3.1-flash-lite`). Instead of a rigid pipeline, the agent independently chooses when to use four custom tools:
* `resolve_account`: Resolves missing/unmatched IDs via fuzzy domain and name matching.
* `get_account_context`: Pulls tier, renewal dates, and open escalations.
* `search_ticket_history`: Checks for duplicate submissions.
* `search_kb` / `get_kb_article`: Retrieves technical fixes.
Strict guardrails prevent the agent from finishing prematurely before completing identity, history, and KB checks.

## 2. Evaluation & Validation Results
* **Schema Compliance:** 10/10 review tickets successfully generated outputs that strictly match the Pydantic schema.
* **Test Coverage:** 14/14 offline unit tests passed, covering tool execution and fallback logic.
* **Tool Execution:** Trace logs confirm the agent successfully performs real multi-step lookups rather than hallucinating answers.
* **Resilience:** Implemented rate-limit retry handling to gracefully recover from HTTP 429 errors during batch processing.

## 3. Scaling Strategy at 10x Volume
To handle 5,000+ tickets, the current sequential processing would bottleneck. The scaling plan includes:
* **Asynchronous Execution:** Transitioning the tool calls and API requests to `asyncio` to process multiple tickets concurrently.
* **Caching Layer:** Implementing Redis for KB articles and Account Context to prevent redundant database lookups.
* **Vector Database:** Moving from basic TF-IDF to a dedicated vector store (e.g., Pinecone/Milvus) for faster, more accurate semantic searches across historical tickets.

## 4. System Limitations & Edge Cases
* **Fuzzy Matching Limits:** If a customer submits a ticket from a personal email (e.g., Gmail) and doesn't mention their company, `resolve_account` will fail to match them to an Enterprise account.
* **Rate Limiting:** Heavy ReAct traces require multiple API calls per ticket, making the system susceptible to LLM provider rate limits without strict backoff handling.

## 5. Instructions on How to Run
1. Clone the repository and install requirements: `pip install -r requirements.txt`
2. Set your environment variables:
   * `export GEMINI_API_KEY="your_api_key"`
   * `export TAM_API_KEY="your_tam_key"`
3. Run the evaluation set:
   `python run.py --set review`
4. Verify the outputs (they will generate in the `outputs/` folder):
   `python scripts/check_outputs.py`