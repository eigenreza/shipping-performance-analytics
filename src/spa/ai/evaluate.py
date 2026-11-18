"""Evaluation of the AI analyst and the insight writer.

Analyst: the 40 frozen questions (spa.ai.questions); accuracy per model with
Wilson 95% intervals, separately for the development and test splits, plus
latency and tokens. Insight writer: three findings for each of five pages per
model; share of findings fully supported and share with an unsupported
number, with examples of both.

Model calls come from the cache (results/ai/model_calls.jsonl); with
live=True missing calls are made. A model whose free quota runs out is
stopped and its coverage recorded, never waited for.
"""

from __future__ import annotations

import json
import re
import statistics

import duckdb

from spa.ai import analyst, insights
from spa.ai.llm import Cache, Client, NotCached, QuotaExhausted
from spa.ai.questions import QUESTIONS
from spa.analysis.run_all import wilson
from spa.paths import RESULTS, WAREHOUSE

OUT = RESULTS / "ai"
MODELS = {
    "qwen2.5:7b-instruct": {"label": "Qwen 2.5 7B (local, Ollama)", "interval": 0.0},
    "llama3.2:3b": {"label": "Llama 3.2 3B (local, Ollama)", "interval": 0.0},
    "gemini-3.5-flash-lite": {"label": "Gemini 3.5 Flash Lite (free tier)", "interval": 4.5},
}


def norm_text(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower()).split().__str__()


def _words(s: str) -> list[str]:
    return re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower()).split()


def parse_number(s: str) -> float | None:
    if s is None:
        return None
    m = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", s.replace(" ", ""))
    if not m:
        return None
    v = float(m.group(0).replace(",", ""))
    if "%" in s:
        v /= 100
    return v


def score(kind: str, gold, answer: str | None) -> bool:
    if answer is None:
        return False
    if kind == "number":
        v = parse_number(answer)
        if v is None or gold is None:
            return False
        g = float(gold)
        options = [v, v / 100] if abs(g) <= 1.5 and abs(v) > 1.5 else [v]
        for x in options:
            if abs(g) < 1 and abs(x - g) <= 0.0005:
                return True
            if abs(x - g) <= 0.005 * abs(g):
                return True
        return False
    gw, aw = _words(str(gold)), _words(answer)
    if not gw:
        return False
    return aw == gw or any(aw[i:i + len(gw)] == gw for i in range(len(aw) - len(gw) + 1))


def gold_answers() -> dict[str, object]:
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    try:
        return {qid: con.sql(sql).fetchall()[0][0] for qid, _, _, _, sql in QUESTIONS}
    finally:
        con.close()


def run_analyst(model: str, cache: Cache, live: bool) -> dict:
    gold = gold_answers()
    client = Client(model, analyst.PROMPT_VERSION, cache, live=live, min_interval_s=MODELS[model]["interval"])
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    items, stopped = [], None
    try:
        for qid, split, question, kind, _ in QUESTIONS:
            if stopped:
                break
            try:
                a = analyst.ask(client, question, con)
            except (NotCached, QuotaExhausted) as e:  # ask() records these as errors; kept for safety
                stopped = str(e)
                break
            if a.error and ("NotCached" in a.error or "QuotaExhausted" in a.error):
                stopped = a.error
                break
            g = gold[qid]
            items.append({
                "id": qid, "split": split, "question": question, "type": kind,
                "gold": round(g, 6) if isinstance(g, float) else g, "answer": a.value, "correct": score(kind, g, a.value),
                "text": a.text, "sql": a.sql, "tool_calls": a.tool_calls, "steps": a.steps, "error": a.error,
                "latency_s": a.latency_s, "input_tokens": a.input_tokens, "output_tokens": a.output_tokens,
            })
            print(f"  {model} {qid}: {'ok ' if items[-1]['correct'] else 'BAD'} answer={a.value!r} gold={items[-1]['gold']!r}", flush=True)
    finally:
        con.close()
    return {"model": model, "label": MODELS[model]["label"], "items": items, "stopped": stopped,
            "coverage": f"{len(items)} of {len(QUESTIONS)} questions"}


def summarize_analyst(run: dict) -> dict:
    out = {"model": run["model"], "label": run["label"], "coverage": run["coverage"], "stopped": run["stopped"]}
    for split in ("dev", "test"):
        xs = [i for i in run["items"] if i["split"] == split]
        k = sum(i["correct"] for i in xs)
        lo, hi = wilson(k, len(xs)) if xs else (None, None)
        out[split] = {"answered": len(xs), "correct": k, "accuracy": round(k / len(xs), 3) if xs else None,
                      "low": round(lo, 3) if xs else None, "high": round(hi, 3) if xs else None}
    xs = run["items"]
    if xs:
        out["median_latency_s"] = round(statistics.median(i["latency_s"] for i in xs), 1)
        out["mean_input_tokens"] = round(statistics.mean(i["input_tokens"] for i in xs))
        out["mean_output_tokens"] = round(statistics.mean(i["output_tokens"] for i in xs))
        out["mean_steps"] = round(statistics.mean(i["steps"] for i in xs), 2)
        out["errors"] = sum(1 for i in xs if i["error"])
        out["tool_error_share"] = round(sum(1 for i in xs for t in i["tool_calls"] if not t["ok"]) /
                                        max(1, sum(len(i["tool_calls"]) for i in xs)), 3)
    return out


def run_insights(model: str, cache: Cache, live: bool) -> dict:
    client = Client(model, insights.PROMPT_VERSION, cache, live=live, min_interval_s=MODELS[model]["interval"])
    pages, stopped = [], None
    for page, ctx in insights.contexts().items():
        try:
            pages.append(insights.write(client, page, ctx))
        except (NotCached, QuotaExhausted) as e:
            stopped = str(e)
            break
    findings = [f for p in pages for f in p["findings"]]
    n = len(findings)
    sup = sum(f["status"] == "supported" for f in findings)
    uns = sum(f["status"] == "unsupported" for f in findings)
    return {"model": model, "label": MODELS[model]["label"], "pages": pages, "stopped": stopped,
            "findings": n, "supported": sup, "unsupported": uns, "no_numbers": n - sup - uns,
            "share_supported": round(sup / n, 3) if n else None, "share_unsupported": round(uns / n, 3) if n else None}


def model_cache(model: str) -> Cache:
    return Cache(OUT / "calls" / f"{model.replace(':', '_')}.jsonl")


def run(live: bool = False, models: list[str] | None = None) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {"questions": len(QUESTIONS), "dev": sum(q[1] == "dev" for q in QUESTIONS), "test": sum(q[1] == "test" for q in QUESTIONS),
               "analyst": [], "insights": []}
    for model in models or list(MODELS):
        cache = model_cache(model)
        r = run_analyst(model, cache, live)
        (OUT / f"analyst_{model.replace(':', '_')}.json").write_text(json.dumps(r, indent=2, default=str), encoding="utf-8")
        summary["analyst"].append(summarize_analyst(r))
        ins = run_insights(model, cache, live)
        (OUT / f"insights_{model.replace(':', '_')}.json").write_text(json.dumps(ins, indent=2, default=str), encoding="utf-8")
        summary["insights"].append({k: v for k, v in ins.items() if k != "pages"})
    return summarize()


def summarize() -> dict:
    """Build evaluation_summary.json from the per-model result files that exist."""
    summary = {"questions": len(QUESTIONS), "dev": sum(q[1] == "dev" for q in QUESTIONS),
               "test": sum(q[1] == "test" for q in QUESTIONS), "analyst": [], "insights": []}
    for model in MODELS:
        f = OUT / f"analyst_{model.replace(':', '_')}.json"
        g = OUT / f"insights_{model.replace(':', '_')}.json"
        if f.exists() and g.exists():
            summary["analyst"].append(summarize_analyst(json.loads(f.read_text(encoding="utf-8"))))
            ins = json.loads(g.read_text(encoding="utf-8"))
            summary["insights"].append({k: v for k, v in ins.items() if k != "pages"})
    (OUT / "evaluation_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return summary
