"""Executable, dependency-free decision-orchestration workflows. All network actions opt-in.

Jev decides; deterministic application policy authorizes. In fixture mode no live inference
is claimed. Workflow trace contains sanitized metadata (never credentials).
"""
import json
import os
import time
import uuid
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from app import decide

DOCS = [
    {"id": "runbook-rollback", "text": "To rollback a failed deployment, restore the previous approved artifact, run smoke tests, and notify the on-call engineer."},
    {"id": "runbook-release", "text": "Before deployment, confirm CI tests passed and obtain production change approval."},
    {"id": "runbook-incident", "text": "For latency incidents, compare p95 before and after the release, inspect traces, and revert when the rollback criteria are met."},
]

@dataclass
class Trace:
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    events: list = field(default_factory=list)

    def record(self, stage, **details):
        event = {"stage": stage, "timestamp": round(time.time(), 3), **details}
        self.events.append(event)
        return event


def llm_generate(prompt, context, model_tier, trace, mode=None):
    mode = (mode or os.getenv("LLM_MODE", "fixture")).lower()
    if mode == "fixture":
        trace.record("llm", provider="fixture", model_tier=model_tier)
        return "According to the runbook: restore the previously approved artifact, run smoke tests, and notify the on-call engineer."
    if mode != "openai":
        raise ValueError("LLM_MODE must be fixture or openai")
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY required for live LLM execution")
    models = {"small": os.getenv("LLM_SMALL_MODEL", "gpt-4.1-mini"),
              "medium": os.getenv("LLM_MEDIUM_MODEL", "gpt-4.1"),
              "large": os.getenv("LLM_LARGE_MODEL", "gpt-4.1")}
    model = models.get(model_tier, models["large"])
    body = json.dumps({"model": model, "messages": [{"role": "system", "content": "Answer only using the supplied context. If insufficient, say you do not know."}, {"role": "user", "content": f"Context:\n{context}\n\nQuestion:\n{prompt}"}], "temperature": 0}).encode()
    req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=body, method="POST", headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.load(response)
    answer = data["choices"][0]["message"]["content"]
    trace.record("llm", provider="openai", model=model, usage=data.get("usage", {}))
    return answer


def retrieve(query, documents=None, top_k=3):
    """Local lexical retriever (real retrieval over bundled documents; not a vector DB)."""
    import re
    tokens = lambda s: set(re.findall(r"[a-z0-9]+", s.lower()))
    q = tokens(query)
    scored = []
    for doc in documents if documents is not None else DOCS:
        overlap = len(q.intersection(tokens(doc["text"])))
        scored.append({**doc, "retrieval_score": overlap})
    return sorted(scored, key=lambda d: (-d["retrieval_score"], d["id"]))[:top_k]


def execute_tool(name, args, *, approval=False):
    """Allowlisted sandbox actions only; never performs destructive GitHub/production writes."""
    if name == "draft_remediation_issue":
        return {"status": "drafted", "title": "Investigate deployment regression", "description": str(args.get("description", ""))[:500]}
    if name == "write_local_report":
        if not approval:
            return {"status": "approval_required", "executed": False}
        report_dir = Path(os.getenv("REPORT_DIR", "/tmp/jev-decisionops-reports")).resolve()
        report_dir.mkdir(parents=True, exist_ok=True)
        filename = "report-" + uuid.uuid4().hex + ".json"
        (report_dir / filename).write_text(json.dumps({"summary": str(args.get("summary", ""))[:500]}))
        return {"status": "written", "file": filename}
    return {"status": "denied", "reason": "Tool is not on the sandbox allowlist", "executed": False}


def run_workflow(question, *, scenario="rag_answer", llm_mode=None, documents=None, approval=False):
    """Real orchestration: risk -> retrieval -> Jev rerank -> route -> LLM -> Jev eval -> escalation.

    `incident` scenario additionally produces a local remediation issue draft.
    """
    if not isinstance(question, str) or not question.strip() or len(question) > 6000:
        raise ValueError("question must be 1–6000 nonblank characters")
    if scenario not in ("rag_answer", "incident"):
        raise ValueError("Unknown workflow scenario")
    trace = Trace()
    trace.record("start", scenario=scenario, jev_mode=os.getenv("JEV_MODE", "live"), llm_mode=llm_mode or os.getenv("LLM_MODE", "fixture"))
    guard = decide("guardrails", question)
    trace.record("jev_guardrail", outcome=guard["policy"]["action"], provenance=guard["provenance"])
    if guard["policy"]["action"] != "CONTINUE":
        return {"run_id": trace.run_id, "status": "blocked_or_review", "policy": guard["policy"], "trace": trace.events}
    passages = retrieve(question, documents)
    trace.record("retrieve", document_ids=[x["id"] for x in passages], backend="lexical")
    ranked = []
    for passage in passages:
        judged = decide("reranking", f"Question: {question}\nPassage: {passage['text']}")
        raw = judged["response"]["answers"].get("relevance", {}).get("score", 0)
        score = float(raw) if isinstance(raw, (int, float)) else 0.0
        ranked.append({**passage, "jev_score": score})
    ranked.sort(key=lambda d: (-d["jev_score"], -d["retrieval_score"], d["id"]))
    trace.record("jev_rerank", ranking=[{"id": x["id"], "score": x["jev_score"]} for x in ranked])
    context = "\n".join(x["text"] for x in ranked[:2])
    routing = decide("routing", question)
    tier = routing["response"]["answers"].get("route", {}).get("choice", "large")
    if tier not in ("small", "medium", "large"):
        tier = "large"
    trace.record("jev_route", model_tier=tier)
    answer = llm_generate(question, context, tier, trace, mode=llm_mode)
    evaluation = decide("evals", f"Question: {question}\nReference: {context}\nAnswer: {answer}")
    quality = evaluation["response"]["answers"].get("quality", {}).get("score", 0)
    grounded = evaluation["response"]["answers"].get("grounded", {}).get("noul", 0)
    trace.record("jev_evaluate", quality=quality, grounded=grounded)
    # Safety policy: unfamiliar values fail closed, Jev's score alone is not a guarantee.
    permitted = isinstance(quality, (float, int)) and quality >= 3 and isinstance(grounded, (float, int)) and grounded >= .8
    confidence = decide("confidence", f"Question: {question}\nProposed answer: {answer}\nEvaluation: quality={quality}, grounded={grounded}") if permitted else None
    confidence_policy = confidence["policy"]["action"] if confidence else "HUMAN REVIEW"
    trace.record("jev_confidence", outcome=confidence_policy, provenance=confidence["provenance"] if confidence else "skipped_due_to_evaluation")
    permitted = permitted and confidence_policy == "PROCEED"
    status = "completed" if permitted else "human_review"
    result = {"run_id": trace.run_id, "status": status, "answer": answer if permitted else None,
              "evaluation": {"quality": quality, "grounded": grounded},
              "sources": [x["id"] for x in ranked[:2]], "trace": trace.events}
    if scenario == "incident":
        tool_name = "draft_remediation_issue"
        gate = decide("tools", f"Tool: {tool_name}; action: prepare a non-published local draft; actor: demo; environment: sandbox") if permitted else None
        gate_action = gate["policy"]["action"] if gate else "BLOCK"
        trace.record("jev_tool_gate", outcome=gate_action, provenance=gate["provenance"] if gate else "skipped_pending_review")
        result["tool"] = execute_tool(tool_name, {"description": question + " | " + answer}) if gate_action == "ALLOW IF AUTHORIZED" else {"status": "skipped_pending_approval", "executed": False}
        trace.record("tool", outcome=result["tool"]["status"])
    trace.record("finish", status=status)
    return result
