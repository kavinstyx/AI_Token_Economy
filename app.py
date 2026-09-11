"""
app.py — the Phase 1 spine + brain, tied together.

Flow:
  UI  ->  /chat  ->  decider (if mode=decider)  ->  LiteLLM  ->  metering  ->  UI

Run:
  export LITELLM_URL=http://localhost:4000     # your running LiteLLM gateway
  export LITELLM_KEY=sk-1234                    # the master_key from litellm_config.yaml
  uvicorn app:app --reload --port 8000
Then open http://localhost:8000
"""

import os
import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

import decider
import metering

LITELLM_URL = os.environ.get("LITELLM_URL", "http://localhost:4000")
LITELLM_KEY = os.environ.get("LITELLM_KEY", "sk-1234")

app = FastAPI(title="AI Token Economy — Phase 1 Decider")
metering.init_db()


class ChatIn(BaseModel):
    prompt: str
    mode: str = "decider"          # "local" | "gemini" | "decider"
    user_key: str = "tester-1"     # stand-in for a real user identity


# map the UI's manual modes to concrete model names
MANUAL_MODELS = {
    "local": decider.LOCAL_MODEL,
    "gemini": decider.EXTERNAL_MODEL,
}


@app.post("/chat")
async def chat(body: ChatIn):
    # 1) DECIDE which model to use
    if body.mode == "decider":
        d = decider.decide(body.prompt)
        model, reason, rule = d.model, d.reason, d.rule
    else:
        model = MANUAL_MODELS.get(body.mode, decider.EXTERNAL_MODEL)
        reason = f"Manual override — you picked '{body.mode}'. Decider not used."
        rule = "manual"

    # 2) CALL LiteLLM with the chosen model
    payload = {"model": model, "messages": [{"role": "user", "content": body.prompt}], "max_tokens": 512}
    headers = {"Authorization": f"Bearer {LITELLM_KEY}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=300) as client:
            r = await client.post(f"{LITELLM_URL}/chat/completions",
                                  json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
    except httpx.TimeoutException:
        return JSONResponse(status_code=504,
            content={"error": "Local model timed out — it is slow on CPU. Try a shorter prompt or a smaller model.", "model": model, "reason": reason})
    except Exception as e:
        return JSONResponse(status_code=502,
            content={"error": f"Call to LiteLLM failed: {e}", "model": model, "reason": reason})

    answer = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {}) or {}

    # 3) METER (raw only — no conversion)
    metering.record(
        user_key=body.user_key, mode=body.mode,
        requested_model=model, served_model=data.get("model", model),
        decider_rule=rule, usage=usage, prompt_chars=len(body.prompt or ""),
    )

    # 4) RETURN answer + the decision + the raw usage (so the UI can show all of it)
    return {
        "answer": answer,
        "chosen_model": model,
        "reason": reason,
        "rule": rule,
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        },
    }


@app.get("/usage")
async def usage():
    return {"summary": metering.summary(), "recent": metering.recent(20)}


@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML_PAGE


# --------------------------- minimal UI (single page) ---------------------------
HTML_PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>AI Token Economy — Phase 1</title>
<style>
  :root{ --ink:#1A2233; --sub:#5B6472; --blue:#1E3A73; --teal:#1C7293;
         --green:#2E9E5B; --amber:#8A5A12; --line:#D8E0E8; --bg:#F3F7FA; }
  *{box-sizing:border-box}
  body{font-family:system-ui,Segoe UI,Roboto,Arial,sans-serif;margin:0;background:var(--bg);color:var(--ink)}
  .wrap{max-width:860px;margin:0 auto;padding:28px 20px 60px}
  h1{font-size:22px;margin:0 0 2px}
  .sub{color:var(--sub);font-size:14px;margin-bottom:22px}
  .card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:18px;margin-bottom:16px;
        box-shadow:0 1px 3px rgba(20,40,60,.06)}
  label{font-size:12px;font-weight:700;color:var(--teal);letter-spacing:.4px;text-transform:uppercase}
  textarea{width:100%;min-height:90px;margin-top:8px;padding:12px;border:1px solid var(--line);
           border-radius:8px;font-size:15px;font-family:inherit;resize:vertical}
  .modes{display:flex;gap:8px;margin:14px 0}
  .mode{flex:1;text-align:center;padding:10px;border:1.5px solid var(--line);border-radius:8px;
        cursor:pointer;font-size:14px;font-weight:600;color:var(--sub);background:#fff;user-select:none}
  .mode.active{border-color:var(--blue);color:var(--blue);background:#EEF3FC}
  button{background:var(--blue);color:#fff;border:0;border-radius:8px;padding:12px 22px;
         font-size:15px;font-weight:700;cursor:pointer}
  button:disabled{opacity:.5;cursor:default}
  .decision{border-left:4px solid var(--green);background:#F4FBF6;padding:12px 14px;border-radius:6px;
            font-size:14px;margin-bottom:12px;display:none}
  .decision.show{display:block}
  .decision.manual{border-left-color:var(--amber);background:#FDF7EC}
  .pill{display:inline-block;background:var(--blue);color:#fff;border-radius:20px;padding:2px 12px;
        font-size:13px;font-weight:700;margin-right:6px}
  .answer{white-space:pre-wrap;font-size:15px;line-height:1.5;margin-top:6px}
  .usage{display:flex;gap:18px;margin-top:14px;color:var(--sub);font-size:13px}
  .usage b{color:var(--ink);font-size:15px}
  .muted{color:var(--sub);font-size:12px;margin-top:18px}
  a{color:var(--teal)}
</style>
</head>
<body>
<div class="wrap">
  <h1>AI Token Economy — Phase 1 Console</h1>
  <div class="sub">Pick a mode, send a prompt. In <b>Decider</b> mode the backend chooses the model for you.</div>

  <div class="card">
    <label>Your prompt</label>
    <textarea id="prompt" placeholder="Try: 'Hi there'  vs  'Write a python function to sort a list'"></textarea>

    <div class="modes" id="modes">
      <div class="mode" data-mode="local">local-qwen</div>
      <div class="mode" data-mode="gemini">gemini-api</div>
      <div class="mode active" data-mode="decider">model-decider</div>
    </div>

    <button id="send" onclick="send()">Send</button>
  </div>

  <div class="card" id="result" style="display:none">
    <div class="decision" id="decision"></div>
    <label>Answer</label>
    <div class="answer" id="answer"></div>
    <div class="usage" id="usage"></div>
  </div>

  <div class="muted">
    Raw usage is being logged (no conversion yet). See <a href="/usage" target="_blank">/usage</a> for the metering table.
  </div>
</div>

<script>
let mode = "decider";
document.querySelectorAll(".mode").forEach(el=>{
  el.onclick = ()=>{
    document.querySelectorAll(".mode").forEach(m=>m.classList.remove("active"));
    el.classList.add("active");
    mode = el.dataset.mode;
  };
});

async function send(){
  const prompt = document.getElementById("prompt").value;
  const btn = document.getElementById("send");
  btn.disabled = true; btn.textContent = "Working…";
  try{
    const res = await fetch("/chat", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({prompt, mode})
    });
    const d = await res.json();
    document.getElementById("result").style.display = "block";

    const dec = document.getElementById("decision");
    dec.className = "decision show" + (d.rule === "manual" ? " manual" : "");
    dec.innerHTML = '<span class="pill">'+ (d.chosen_model||"?") +'</span>' + (d.reason||"");

    document.getElementById("answer").textContent = d.answer || ("ERROR: "+(d.error||"unknown"));
    const u = d.usage || {};
    document.getElementById("usage").innerHTML =
      'Prompt: <b>'+(u.prompt_tokens??'-')+'</b>&nbsp;tokens' +
      '&nbsp;&nbsp;Completion: <b>'+(u.completion_tokens??'-')+'</b>' +
      '&nbsp;&nbsp;Total: <b>'+(u.total_tokens??'-')+'</b>';
  }catch(e){
    alert("Request failed: "+e);
  }finally{
    btn.disabled = false; btn.textContent = "Send";
  }
}
</script>
</body>
</html>
"""
