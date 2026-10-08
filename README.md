# ⚡ Jev DecisionOps v3 — Executable decision orchestration

A runnable, interview-focused demonstration of six decision use cases using **TypeSafe AI Jev** as the decision engine. The default mode is an **offline end-to-end simulation**: deterministic decision rules, real local retrieval, and extractive generation. Live Jev and OpenAI adapters remain opt-in and require credentials.

Version 2 adds a multi-step workflow API and dashboard: local retrieval → Jev passage scoring → model-tier routing → optional OpenAI generation → answer evaluation → confidence gating → sandbox remediation drafts.

## Architecture and six use cases

![Jev DecisionOps architecture and six Jev decision-model use cases](jev-decisionops-architecture-refined.png)

> **Diagram scope:** The refined diagram summarizes the six decision primitives and deterministic policy boundary. v2 implements local lexical retrieval, an optional OpenAI generation adapter, in-memory remediation drafts, and per-stage traces. Vector databases, externally executed tools, observability backends, and a real human approval service remain future integrations. The image is an architectural overview, not proof of credentialed live execution.

## Start (Python 3.10+, zero pip dependencies)

```bash
python app.py
# Default: offline simulation, no keys needed
# Open http://localhost:8765
```

The configured endpoint defaults to `https://api.typesafe.ai/v1/systemone` with `model: jev-latest`. Override `JEV_ENDPOINT` if your TypeSafe account specifies a different endpoint. The API shape is `{"model":"jev-latest", "state":"...", "questions":{"question_name":{"type":"choice|score|noul", ...}}}`. Keys stay server-side. Check endpoint/schema against your TypeSafe account's documentation before live demonstrations.

To rehearse **without a Jev key** (no real inference):

```bash
JEV_MODE=demo LLM_MODE=fixture python app.py
```

## Workflows

The six single-decision scenarios remain available. The v2 orchestration endpoint composes these decisions with retrieval, optional generation, evaluation and sandbox actions.

| Workload | Jev primitive | Downstream action |
|---|---|---|
| LLM model selection | choice | small / medium / large LLM tier (selection only) |
| Prompt screening | choice | allow / review / block |
| Tool-call risk | choice | allow-if-authorized / approve / deny; hardcoded deny-list always wins |
| Passage reranking | score | ordinal passage relevance (single passage demo) |
| Answer evaluation | score + noul | answer quality and grounding signals |
| Confidence-driven autonomy | choice + confidence | proceed / confirm / human review |

## System boundary

```mermaid
flowchart TD
    A[Workflow request] --> B[Jev prompt screening]
    B -->|Allowed| C[Local lexical retrieval]
    B -->|Blocked or uncertain| R[Block or review]
    C --> D[Jev passage scoring]
    D --> E[Jev model routing]
    E --> F[OpenAI or fixture answer]
    F --> G[Jev answer evaluation]
    G -->|Insufficient quality| R
    G -->|Passed| H[Jev confidence decision]
    H -->|Review or confirm| R
    H -->|Proceed| I[Grounded answer]
    I -->|Incident workflow| J[Jev sandbox tool gate]
    J -->|Allowed| K[In-memory issue draft]
    J -->|Approval needed| R
```

**Not implemented:** published GitHub issues or production tool actions, vector retrieval infrastructure, a human approval service, distributed tracing, or production access control. Live OpenAI inference is implemented as an optional adapter; credentialed live end-to-end execution remains unverified. The demo does not manufacture evidence of these integrations. Before production: validate Jev's response contract and confidence scales against your account, create labeled datasets, measure per-task precision/recall and calibration, add authentication and RBAC, secret management, audit retention, retries, monitoring, and human-review queues.

## Interview narration (5–7 min)

1. Show the decision boundaries and distinction between Jev and generative LLMs.
2. Run prompt routing (safe input), then a prompt injection against guardrails.
3. Run a destructive `github.delete_repository` request: even if the classifier were wrong, application policy blocks it.
4. Score retrieved context; evaluate a generated response against a reference.
5. Show confidence escalation and inspect the complete typed input/output trace.
6. Compare real latency and spend only after collecting reliable live benchmarks. Do **not** claim 10–100× savings based on fixtures.

## API source references

- https://www.jevtypesafeai.com/how-to-use (community guide reproducing official endpoint shape)
- https://www.jevtypesafeai.com/jev/api (community API guide)

**Note:** Community documentation may differ from your actual TypeSafe account's contract. The default endpoint has not been tested with a real key by this repository author.

## Executable orchestrated workflows (v2)

The new `orchestration.py` adds **local lexical retrieval**, Jev-based per-passage scoring, Jev LLM-tier selection, an optional real OpenAI LLM call, Jev answer evaluation, fail-closed outcome escalation, and a **sandbox-only** remediation-issue drafting tool. It emits a per-stage structured trace. This is an executable orchestration pipeline, **not** a production deployment.

```bash
# Interactive end-to-end simulation (safe requests complete; unsupported requests escalate)
JEV_MODE=demo LLM_MODE=fixture python app.py
# Use the new POST /api/workflow endpoint, for instance:
curl -s localhost:8765/api/workflow -H 'Content-Type: application/json' \
  -d '{"question":"How to rollback a failed deployment?","scenario":"rag_answer"}'

# Live Jev + live OpenAI (requires verified Jev endpoint/response contract)
TYPESAFE_API_KEY=... OPENAI_API_KEY=... JEV_MODE=live LLM_MODE=openai python app.py
```

**Offline demo:** `JEV_MODE=demo` uses input-dependent deterministic rules rather than live inference. Safe runbook requests complete, prompt-injection examples block before generation, and unsupported or uncertain requests withhold the answer for review. `LLM_MODE=fixture` selects and copies a relevant passage from the supplied context rather than returning a constant answer. The UI shows each executed stage, source text, evaluation, outcome and explicit provenance. Incident runs create a downloadable JSON draft; no GitHub issue is published. You can download the full trace as JSON. Legacy `JEV_MODE=fixture` remains available for fixed-response regression tests and deliberately blocks at screening. These illustrative rules are not a production risk classifier.

Tests: `python -m unittest -v`. The authenticated live path requires API credentials and external network access. Never commit credentials.

### Orchestration policy details

For an approved response, Jev evaluates answer quality and grounding, then provides a **confidence decision** which must pass the deterministic `PROCEED` threshold; low scores or uncertain decisions escalate without returning the drafted answer. In the incident scenario, Jev additionally assesses the sandbox draft tool, and a deterministic allowlist enforces the final action. All stages appear in the audit trace. CI runs all 16 tests without API credentials. Five new offline end-to-end tests use the actual simulator and orchestration without mocking decisions; live-provider behavior is still unverified.

`GET /health`, `GET /api/scenarios`, `POST /api/decide` (single decision) and `POST /api/workflow` (multi-step workflow) are available. The server binds to `127.0.0.1` by default and is not designed to be internet-exposed. No real human approval backend, vector database, persistent trace store, or production authorization layer is included. For deployment, add authentication, rate limiting, secret management, prompt-injection robustness tests, schema validation, and durable audit storage.

## Run the end-to-end UI

1. Run `python app.py` and open `http://localhost:8765`.
2. Click **Rollback answer**, then **Run end-to-end workflow**. Expect **Completed**, a runbook answer, evidence and nine pipeline stages.
3. Click **Latency incident**, then run. Expect **Completed** and a sandbox draft. Use **Download incident draft** to save it.
4. Click **Blocked request**, then run. Expect **Blocked**, with no generation or tool execution.
5. Click **Missing evidence**, then run. Expect **Human review required** and no released answer.
6. Use **Download trace** or expand **Full workflow trace** to inspect provenance and all executed stages.

The six individual decision labs remain below the main workflow. Mode is controlled by the server; the UI cannot switch on live providers or expose keys. The optional `npm run dev` command starts the same Python app in offline mode on port 4173 for supervised browser previews; normal local use requires only Python. `HOST` defaults to loopback; keep that default for local use.
