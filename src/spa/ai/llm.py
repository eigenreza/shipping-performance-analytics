"""Model clients (Ollama on the laptop, Gemini free tier) with a call cache.

Every call is cached under a key built from the model, the prompt version and
the full request, in results/ai/model_calls.jsonl. Evaluations rerun offline
from the cache; a call that is not cached is only made when live=True.
The Gemini key is read from the GEMINI_API_KEY environment variable, sent in
a request header, and never logged or stored.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field

import requests

from spa.paths import RESULTS

CACHE_FILE = RESULTS / "ai" / "calls" / "demo_live.jsonl"
OLLAMA = "http://localhost:11434/api/chat"
GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class NotCached(RuntimeError):
    pass


class QuotaExhausted(RuntimeError):
    pass


@dataclass
class Reply:
    text: str = ""
    tool_calls: list[dict] = field(default_factory=list)  # [{"name": str, "args": dict}]
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0
    cached: bool = False
    raw: list = field(default_factory=list)  # provider parts, replayed as-is in later turns (Gemini thought signatures)


class Cache:
    def __init__(self, path=CACHE_FILE):
        self.path = path
        self.data: dict[str, dict] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    self.data[rec["key"]] = rec
        path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key(model: str, prompt_version: str, payload: dict) -> str:
        raw = json.dumps({"model": model, "prompt_version": prompt_version, "payload": payload}, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, key: str) -> dict | None:
        return self.data.get(key)

    def put(self, key: str, model: str, prompt_version: str, reply: Reply) -> None:
        rec = {"key": key, "model": model, "prompt_version": prompt_version, "reply": reply.__dict__}
        self.data[key] = rec
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")


def gemini_key() -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key and os.name == "nt":
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            key = winreg.QueryValueEx(k, "GEMINI_API_KEY")[0]
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return key


class Client:
    """One model behind a common chat interface with tool calling."""

    def __init__(self, model: str, prompt_version: str, cache: Cache, live: bool = False, min_interval_s: float = 0.0):
        self.model, self.prompt_version, self.cache, self.live = model, prompt_version, cache, live
        self.provider = "gemini" if model.startswith("gemini") else "ollama"
        self.min_interval_s = min_interval_s
        self._last = 0.0

    def chat(self, system: str, messages: list[dict], tools: list[dict] | None = None) -> Reply:
        payload = {"system": system, "messages": messages, "tools": tools or []}
        key = Cache.key(self.model, self.prompt_version, payload)
        hit = self.cache.get(key)
        if hit:
            r = Reply(**hit["reply"])
            r.cached = True
            return r
        if not self.live:
            raise NotCached(f"no cached reply for {self.model}")
        wait = self.min_interval_s - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        t = time.time()
        reply = self._gemini(system, messages, tools) if self.provider == "gemini" else self._ollama(system, messages, tools)
        self._last = time.time()
        reply.latency_s = round(time.time() - t, 3)
        self.cache.put(key, self.model, self.prompt_version, reply)
        return reply

    # ---------------------------------------------------------------- Ollama
    def _ollama(self, system, messages, tools) -> Reply:
        msgs = [{"role": "system", "content": system}]
        for m in messages:
            if m["role"] == "tool":
                msgs.append({"role": "tool", "content": json.dumps(m["content"], default=str)})
            elif m.get("tool_calls"):
                msgs.append({"role": "assistant", "content": m.get("content", ""),
                             "tool_calls": [{"function": {"name": c["name"], "arguments": c["args"]}} for c in m["tool_calls"]]})
            else:
                msgs.append({"role": m["role"], "content": m["content"]})
        body = {"model": self.model, "messages": msgs, "stream": False, "options": {"temperature": 0, "num_ctx": 8192, "seed": 7}}
        if tools:
            body["tools"] = [{"type": "function", "function": t} for t in tools]
        r = requests.post(OLLAMA, json=body, timeout=900)
        r.raise_for_status()
        j = r.json()
        msg = j.get("message", {})
        calls = [{"name": c["function"]["name"], "args": c["function"].get("arguments") or {}} for c in msg.get("tool_calls") or []]
        return Reply(text=msg.get("content", ""), tool_calls=calls, input_tokens=j.get("prompt_eval_count", 0),
                     output_tokens=j.get("eval_count", 0))

    # ---------------------------------------------------------------- Gemini
    def _gemini(self, system, messages, tools) -> Reply:
        contents = []
        for m in messages:
            if m["role"] == "user":
                contents.append({"role": "user", "parts": [{"text": m["content"]}]})
            elif m["role"] == "assistant" and m.get("raw"):
                contents.append({"role": "model", "parts": m["raw"]})
            elif m["role"] == "assistant":
                parts = []
                if m.get("content"):
                    parts.append({"text": m["content"]})
                for c in m.get("tool_calls") or []:
                    parts.append({"functionCall": {"name": c["name"], "args": c["args"]}})
                contents.append({"role": "model", "parts": parts})
            elif m["role"] == "tool":
                contents.append({"role": "user", "parts": [{"functionResponse": {"name": m["name"], "response": {"result": m["content"]}}}]})
        body = {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents,
                "generationConfig": {"temperature": 0}}
        if tools:
            body["tools"] = [{"functionDeclarations": tools}]
        for attempt in range(4):
            r = requests.post(GEMINI.format(model=self.model), headers={"x-goog-api-key": gemini_key()},
                              data=json.dumps(body, default=str), timeout=180)
            if r.status_code == 429:
                detail = r.text.lower()
                if "perday" in detail.replace("_", "").replace(" ", "") or "daily" in detail:
                    raise QuotaExhausted("daily free-tier quota reached")
                time.sleep(20 * (attempt + 1))
                continue
            if r.status_code >= 500:
                time.sleep(10 * (attempt + 1))
                continue
            r.raise_for_status()
            break
        else:
            raise QuotaExhausted("rate limit did not clear")
        j = r.json()
        cand = (j.get("candidates") or [{}])[0]
        parts = (cand.get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        calls = [{"name": p["functionCall"]["name"], "args": p["functionCall"].get("args") or {}} for p in parts if "functionCall" in p]
        u = j.get("usageMetadata", {})
        return Reply(text=text, tool_calls=calls, input_tokens=u.get("promptTokenCount", 0),
                     output_tokens=u.get("candidatesTokenCount", 0) + u.get("thoughtsTokenCount", 0), raw=parts)
