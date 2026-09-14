"""app.py — UI + decider + LiteLLM + metering."""
import os
import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

import decider
import metering

LITELLM_URL = os.environ.get("LITELLM_URL", "http://localhost:4000")
LITELLM_KEY = os.environ.get("LITELLM_KEY", "sk-1234")

# per-model output caps: cap the SLOW local model, let fast Gemini run free
MAX_TOKENS = {"local-qwen": 512, "gemini-flash": 2048}

app = FastAPI(title="AI Token Economy — Phase 1")

class ChatIn(BaseModel):
    prompt: str
    mode: str = "decider"
    user_key: str = "tester-1"

MANUAL_MODELS = {
    "local": "local-qwen",
    "gemini": "gemini-flash",
    "groq": "groq-gpt-oss",
    "mistral": "mistral-14b",
    "openrouter": "openrouter-free",
}

@app.post("/chat")
async def chat(body: ChatIn):
    if body.mode == "decider":
        d = decider.decide(body.prompt)
        model, reason, rule, source = d.model, d.reason, d.rule, d.source
    else:
        model = MANUAL_MODELS.get(body.mode, decider.EXTERNAL_MODEL)
        reason = f"Manual override — you picked '{body.mode}'. Decider not used."
        rule, source = "manual", "manual"

    payload = {"model": model,
               "messages": [{"role": "user", "content": body.prompt}],
               "max_tokens": MAX_TOKENS.get(model, 1024)}
    headers = {"Authorization": f"Bearer {LITELLM_KEY}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=300) as client:
            r = await client.post(f"{LITELLM_URL}/chat/completions", json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
    except httpx.TimeoutException:
        return JSONResponse(status_code=504,
            content={"error": "Local model timed out — slow on CPU. Try a shorter prompt or smaller model.",
                     "chosen_model": model, "reason": reason})
    except Exception as e:
        return JSONResponse(status_code=502,
            content={"error": f"Call to LiteLLM failed: {type(e).__name__}: {e}",
                     "chosen_model": model, "reason": reason})

    answer = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {}) or {}

    metering.record(user_key=body.user_key, mode=body.mode,
                    requested_model=model, served_model=data.get("model", model),
                    decider_rule=rule, usage=usage, prompt_chars=len(body.prompt or ""),
                    routing_source=source)

    return {"answer": answer, "chosen_model": model, "reason": reason,
            "rule": rule, "routing_source": source,
            "usage": {"prompt_tokens": usage.get("prompt_tokens"),
                      "completion_tokens": usage.get("completion_tokens"),
                      "total_tokens": usage.get("total_tokens")}}

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

/* =========================================================
   THEME VARIABLES
   ========================================================= */

:root{

  /* Backgrounds */
  --bg:#F5F8F7;
  --surface:#FFFFFF;
  --surface-soft:#F8FAFA;

  /* Text */
  --ink:#24313A;
  --sub:#687780;
  --muted:#87949B;

  /* Primary */
  --primary:#315C68;
  --primary-dark:#274C57;
  --primary-soft:#EAF2F3;

  /* Teal */
  --teal:#3D7C80;
  --teal-soft:#EAF5F4;

  /* Success */
  --green:#4E8B69;
  --green-soft:#EEF7F1;

  /* Warning */
  --amber:#A47A43;
  --amber-soft:#FBF5EA;

  /* Borders */
  --line:#DDE6E5;
  --line-hover:#C8D7D6;

  /* Components */
  --answer-bg:#F8FAFA;
  --usage-bg:#F4F7F7;

  /* Shadows */
  --shadow:0 8px 30px rgba(38,65,70,.07);
  --shadow-soft:0 3px 14px rgba(38,65,70,.05);

  --radius:16px;
}


/* =========================================================
   DARK MODE
   ========================================================= */

body.dark{

  /* Backgrounds */
  --bg:#151D20;
  --surface:#1D272B;
  --surface-soft:#202C30;

  /* Text */
  --ink:#E4ECEC;
  --sub:#A7B5B8;
  --muted:#7F9094;

  /* Primary */
  --primary:#78AEB1;
  --primary-dark:#67999D;
  --primary-soft:#263A3D;

  /* Teal */
  --teal:#75AEB0;
  --teal-soft:#243638;

  /* Success */
  --green:#78AD8B;
  --green-soft:#22352A;

  /* Warning */
  --amber:#C4A06A;
  --amber-soft:#382F22;

  /* Borders */
  --line:#344347;
  --line-hover:#46585C;

  /* Components */
  --answer-bg:#202C30;
  --usage-bg:#263235;

  /* Shadows */
  --shadow:0 8px 30px rgba(0,0,0,.20);
  --shadow-soft:0 3px 14px rgba(0,0,0,.14);
}


/* =========================================================
   GLOBAL
   ========================================================= */

*{
  box-sizing:border-box;
}

html{
  scroll-behavior:smooth;
}

body{

  margin:0;
  min-height:100vh;

  font-family:
    Inter,
    ui-sans-serif,
    system-ui,
    -apple-system,
    BlinkMacSystemFont,
    "Segoe UI",
    Roboto,
    Arial,
    sans-serif;

  background:
    radial-gradient(
      circle at 50% -10%,
      rgba(61,124,128,.08),
      transparent 42%
    ),
    var(--bg);

  color:var(--ink);

  -webkit-font-smoothing:antialiased;
  text-rendering:optimizeLegibility;

  transition:
    background .25s ease,
    color .25s ease;
}


/* =========================================================
   MAIN CONTAINER
   ========================================================= */

.wrap{

  width:100%;
  max-width:920px;

  margin:0 auto;

  padding:36px 22px 70px;
}


/* =========================================================
   HEADER
   ========================================================= */

.header{

  text-align:center;

  margin-bottom:28px;
}


/* Brand */

.brand{

  display:inline-flex;

  align-items:center;

  gap:9px;

  margin-bottom:11px;

  color:var(--primary);

  font-size:12px;

  font-weight:800;

  letter-spacing:1.2px;

  text-transform:uppercase;
}


.brand-dot{

  width:9px;
  height:9px;

  border-radius:50%;

  background:var(--teal);

  box-shadow:
    0 0 0 5px rgba(61,124,128,.10);
}


/* Heading */

h1{

  margin:0;

  font-size:28px;

  line-height:1.2;

  letter-spacing:-.5px;

  font-weight:750;

  color:var(--ink);
}


/* Subtitle */

.sub{

  max-width:650px;

  margin:10px auto 0;

  color:var(--sub);

  font-size:14px;

  line-height:1.6;
}

.sub b{

  color:var(--primary);
}


/* =========================================================
   THEME TOGGLE
   ========================================================= */

.theme-toggle{

  display:flex;

  justify-content:flex-end;

  margin-bottom:15px;
}


.theme-toggle button{

  min-width:auto;

  display:inline-flex;

  align-items:center;

  justify-content:center;

  gap:7px;

  padding:8px 13px;

  border:1px solid var(--line);

  border-radius:20px;

  background:var(--surface);

  color:var(--sub);

  font-family:inherit;

  font-size:12px;

  font-weight:650;

  cursor:pointer;

  box-shadow:none;

  transition:
    background .2s ease,
    color .2s ease,
    border-color .2s ease;
}


.theme-toggle button:hover{

  background:var(--surface-soft);

  color:var(--ink);

  border-color:var(--line-hover);

  transform:none;

  box-shadow:none;
}


#themeIcon{

  font-size:15px;

  line-height:1;
}


/* =========================================================
   CARDS
   ========================================================= */

.card{

  background:var(--surface);

  border:1px solid var(--line);

  border-radius:var(--radius);

  padding:22px;

  margin-bottom:18px;

  box-shadow:var(--shadow-soft);

  transition:
    background .25s ease,
    border-color .25s ease,
    box-shadow .25s ease;
}


.card:hover{

  box-shadow:var(--shadow);
}


/* =========================================================
   LABELS
   ========================================================= */

label{

  display:block;

  font-size:11px;

  font-weight:800;

  color:var(--teal);

  letter-spacing:1px;

  text-transform:uppercase;

  margin-bottom:9px;
}


/* =========================================================
   PROMPT TEXTAREA
   ========================================================= */

textarea{

  display:block;

  width:100%;

  min-height:120px;

  margin:0;

  padding:15px 16px;

  border:1px solid var(--line);

  border-radius:12px;

  background:var(--surface-soft);

  color:var(--ink);

  font-size:15px;

  line-height:1.55;

  font-family:inherit;

  resize:vertical;

  outline:none;

  transition:
    border-color .2s ease,
    box-shadow .2s ease,
    background .2s ease,
    color .2s ease;
}


textarea::placeholder{

  color:var(--muted);
}


textarea:hover{

  border-color:var(--line-hover);
}


textarea:focus{

  background:var(--surface);

  border-color:#8EAFB0;

  box-shadow:
    0 0 0 4px rgba(61,124,128,.09);
}


/* =========================================================
   MODEL TITLE
   ========================================================= */

.mode-title{

  display:flex;

  align-items:center;

  justify-content:space-between;

  margin-top:20px;

  margin-bottom:10px;
}


.mode-title label{

  margin:0;
}


.mode-title span{

  font-size:12px;

  color:var(--sub);
}


/* =========================================================
   MODEL SELECTOR
   ========================================================= */

.modes{

  display:grid;

  grid-template-columns:
    repeat(3,1fr);

  gap:9px;

  margin-bottom:18px;
}


.mode{

  position:relative;

  text-align:center;

  padding:12px 8px;

  border:1px solid var(--line);

  border-radius:10px;

  background:var(--surface);

  color:var(--sub);

  cursor:pointer;

  user-select:none;

  font-size:13px;

  font-weight:650;

  transition:
    transform .15s ease,
    border-color .2s ease,
    background .2s ease,
    color .2s ease,
    box-shadow .2s ease;
}


.mode:hover{

  transform:translateY(-1px);

  border-color:var(--line-hover);

  color:var(--primary);

  box-shadow:
    0 3px 10px rgba(38,65,70,.05);
}


.mode.active{

  border-color:#82A5A6;

  color:var(--primary-dark);

  background:var(--primary-soft);

  box-shadow:
    inset 0 0 0 1px rgba(61,124,128,.08),
    0 3px 10px rgba(38,65,70,.05);
}


body.dark .mode.active{

  color:#B8D1D2;

  border-color:#5D8588;
}


.mode.active::before{

  content:"";

  position:absolute;

  top:7px;
  right:7px;

  width:6px;
  height:6px;

  border-radius:50%;

  background:var(--teal);
}


/* =========================================================
   SEND BUTTON
   ========================================================= */

.send-row{

  display:flex;

  justify-content:flex-end;
}


button{

  min-width:110px;

  border:0;

  border-radius:10px;

  padding:12px 24px;

  background:var(--primary);

  color:#fff;

  font-family:inherit;

  font-size:14px;

  font-weight:700;

  cursor:pointer;

  box-shadow:
    0 4px 12px rgba(49,92,104,.16);

  transition:
    background .2s ease,
    transform .15s ease,
    box-shadow .2s ease;
}


button:hover:not(:disabled){

  background:var(--primary-dark);

  transform:translateY(-1px);

  box-shadow:
    0 6px 16px rgba(49,92,104,.20);
}


button:active:not(:disabled){

  transform:translateY(0);
}


button:disabled{

  opacity:.55;

  cursor:default;

  box-shadow:none;
}


/* =========================================================
   RESULT CARD
   ========================================================= */

#result{

  animation:fadeUp .3s ease;
}


@keyframes fadeUp{

  from{

    opacity:0;

    transform:translateY(6px);
  }

  to{

    opacity:1;

    transform:translateY(0);
  }
}


/* =========================================================
   DECISION
   ========================================================= */

.decision{

  display:none;

  border:1px solid #D7E8DC;

  border-left:4px solid var(--green);

  background:var(--green-soft);

  padding:13px 15px;

  border-radius:10px;

  color:#4C6556;

  font-size:13px;

  line-height:1.5;

  margin-bottom:20px;

  transition:
    background .25s ease,
    border-color .25s ease,
    color .25s ease;
}


body.dark .decision{

  color:#B5CCBB;
}


.decision.show{

  display:block;
}


.decision.manual{

  border-color:#EADFCB;

  border-left-color:var(--amber);

  background:var(--amber-soft);

  color:#705C3D;
}


body.dark .decision.manual{

  color:#D1BA8F;
}


/* =========================================================
   MODEL PILL
   ========================================================= */

.pill{

  display:inline-flex;

  align-items:center;

  background:var(--green);

  color:#fff;

  border-radius:20px;

  padding:4px 11px;

  margin-right:7px;

  font-size:11px;

  font-weight:800;

  letter-spacing:.2px;

  vertical-align:middle;
}


.decision.manual .pill{

  background:var(--amber);
}


/* =========================================================
   ANSWER
   ========================================================= */

.answer{

  white-space:pre-wrap;

  min-height:30px;

  padding:15px;

  border:1px solid var(--line);

  border-radius:10px;

  background:var(--answer-bg);

  color:var(--ink);

  font-size:15px;

  line-height:1.65;

  margin-top:7px;

  transition:
    background .25s ease,
    border-color .25s ease,
    color .25s ease;
}


/* =========================================================
   USAGE
   ========================================================= */

.usage{

  display:flex;

  flex-wrap:wrap;

  gap:10px;

  margin-top:14px;
}


.usage-item{

  display:flex;

  align-items:center;

  gap:6px;

  padding:8px 11px;

  background:var(--usage-bg);

  border:1px solid var(--line);

  border-radius:8px;

  color:var(--sub);

  font-size:12px;

  transition:
    background .25s ease,
    border-color .25s ease;
}


.usage-item b{

  color:var(--ink);

  font-size:13px;
}


/* =========================================================
   FOOTER
   ========================================================= */

.muted{

  text-align:center;

  color:var(--muted);

  font-size:12px;

  line-height:1.6;

  margin-top:22px;
}


a{

  color:var(--teal);

  font-weight:650;

  text-decoration:none;
}


a:hover{

  text-decoration:underline;
}


/* =========================================================
   MOBILE
   ========================================================= */

@media(max-width:600px){

  .wrap{

    padding:28px 15px 50px;
  }


  h1{

    font-size:24px;
  }


  .card{

    padding:17px;

    border-radius:14px;
  }


  .mode-title{

    align-items:flex-start;

    flex-direction:column;

    gap:5px;
  }


  .modes{

    grid-template-columns:
      repeat(2,1fr);
  }


  .send-row{

    justify-content:stretch;
  }


  .send-row button{

    width:100%;
  }


  .usage{

    flex-direction:column;
  }


  .usage-item{

    justify-content:space-between;
  }


  .theme-toggle{

    justify-content:center;
  }

}


/* =========================================================
   REDUCED MOTION
   ========================================================= */

@media(prefers-reduced-motion:reduce){

  *,
  *::before,
  *::after{

    animation-duration:.01ms !important;

    animation-iteration-count:1 !important;

    transition:none !important;

    scroll-behavior:auto !important;
  }
}

</style>
</head>


<body>


<div class="wrap">


  <!-- =====================================================
       HEADER
       ===================================================== -->

  <div class="header">


    <!-- Theme Toggle -->

    <div class="theme-toggle">

      <button
        id="themeToggle"
        type="button"
        onclick="toggleTheme()"
        aria-label="Toggle light and dark mode"
      >

        <span id="themeIcon">☾</span>

        <span id="themeText">Dark mode</span>

      </button>

    </div>


    <!-- Brand -->

    <div class="brand">

      <span class="brand-dot"></span>

      AI Token Economy

    </div>


    <!-- Title -->

    <h1>
      Phase 1 Console
    </h1>


    <!-- Subtitle -->

    <div class="sub">

      Choose a model or let the
      <b>Model Decider</b>
      intelligently select the right model for your prompt.

    </div>


  </div>


  <!-- =====================================================
       PROMPT CARD
       ===================================================== -->

  <div class="card">


    <label for="prompt">
      Your prompt
    </label>


    <textarea
      id="prompt"
      placeholder="Try something simple like “Hi there” or a technical task like “Write a Python function to sort a list”"
      autocomplete="off"
    ></textarea>


    <!-- Model heading -->

    <div class="mode-title">

      <label>
        Model
      </label>

      <span>
        Select how your request should be handled
      </span>

    </div>


    <!-- Models -->

    <div class="modes" id="modes">


      <div
        class="mode"
        data-mode="local"
      >
        local-qwen
      </div>


      <div
        class="mode"
        data-mode="gemini"
      >
        gemini
      </div>


      <div
        class="mode"
        data-mode="groq"
      >
        groq
      </div>


      <div
        class="mode"
        data-mode="mistral"
      >
        mistral
      </div>


      <div
        class="mode"
        data-mode="openrouter"
      >
        openrouter
      </div>


      <div
        class="mode active"
        data-mode="decider"
      >
        model-decider
      </div>


    </div>


    <!-- Send -->

    <div class="send-row">

      <button
        id="send"
        onclick="send()"
      >
        Send
      </button>

    </div>


  </div>


  <!-- =====================================================
       RESULT CARD
       ===================================================== -->

  <div
    class="card"
    id="result"
    style="display:none"
  >


    <!-- Model decision -->

    <div
      class="decision"
      id="decision"
    ></div>


    <!-- Answer -->

    <label>
      Answer
    </label>


    <div
      class="answer"
      id="answer"
    ></div>


    <!-- Token usage -->

    <div
      class="usage"
      id="usage"
    ></div>


  </div>


  <!-- =====================================================
       FOOTER
       ===================================================== -->

  <div class="muted">

    Raw usage is being logged
    (no conversion yet).

    See

    <a
      href="/usage"
      target="_blank"
      rel="noopener noreferrer"
    >
      /usage
    </a>

    for the metering table.

  </div>


</div>


<script>

/* =========================================================
   THEME MANAGEMENT
   ========================================================= */


/*
 * Read previously selected theme.
 *
 * If nothing has been saved, light mode is used.
 */

const savedTheme =
  localStorage.getItem("ai-theme");


if(savedTheme === "dark"){

  document.body.classList.add("dark");

  updateThemeButton(true);

}


/*
 * Toggle between light and dark.
 */

function toggleTheme(){

  const isDark =
    document.body.classList.toggle("dark");


  /*
   * Remember user's choice.
   */

  localStorage.setItem(
    "ai-theme",
    isDark ? "dark" : "light"
  );


  updateThemeButton(isDark);

}


/*
 * Update the toggle icon and text.
 */

function updateThemeButton(isDark){

  const icon =
    document.getElementById("themeIcon");

  const text =
    document.getElementById("themeText");


  if(isDark){

    icon.textContent = "☀";

    text.textContent = "Light mode";

  }
  else{

    icon.textContent = "☾";

    text.textContent = "Dark mode";

  }

}


/* =========================================================
   MODEL SELECTION
   ========================================================= */


let mode = "decider";


document
  .querySelectorAll(".mode")
  .forEach(el => {


    el.onclick = () => {


      /*
       * Remove active state
       * from every model.
       */

      document
        .querySelectorAll(".mode")
        .forEach(m =>
          m.classList.remove("active")
        );


      /*
       * Activate selected model.
       */

      el.classList.add("active");


      /*
       * Store selected model.
       */

      mode =
        el.dataset.mode;

    };

  });


/* =========================================================
   SEND CHAT REQUEST
   ========================================================= */

async function send(){


  const prompt =
    document
      .getElementById("prompt")
      .value
      .trim();


  const btn =
    document.getElementById("send");


  /*
   * Don't send empty prompts.
   */

  if(!prompt){

    document
      .getElementById("prompt")
      .focus();

    return;

  }


  /*
   * Disable button while request
   * is being processed.
   */

  btn.disabled = true;

  btn.textContent = "Working…";


  try{


    /*
     * Call backend.
     */

    const res =
      await fetch("/chat", {

        method:"POST",

        headers:{
          "Content-Type":"application/json"
        },

        body:JSON.stringify({

          prompt:prompt,

          mode:mode

        })

      });


    /*
     * Parse response.
     */

    const d =
      await res.json();


    /*
     * Display result card.
     */

    document
      .getElementById("result")
      .style.display = "block";


    /* =====================================================
       MODEL DECISION
       ===================================================== */

    const dec =
      document.getElementById("decision");


    dec.className =
      "decision show" +
      (
        d.rule === "manual"
          ? " manual"
          : ""
      );


    dec.innerHTML =
      '<span class="pill">' +
      (d.chosen_model || "?") +
      '</span>' +
      (d.reason || "");


    /* =====================================================
       ANSWER
       ===================================================== */

    document
      .getElementById("answer")
      .textContent =
        d.answer ||
        (
          "ERROR: " +
          (d.error || "unknown")
        );


    /* =====================================================
       TOKEN USAGE
       ===================================================== */

    const u =
      d.usage || {};


    document
      .getElementById("usage")
      .innerHTML =


      '<div class="usage-item">' +

        'Prompt ' +

        '<b>' +

        (u.prompt_tokens ?? '-') +

        '</b> tokens' +

      '</div>' +


      '<div class="usage-item">' +

        'Completion ' +

        '<b>' +

        (u.completion_tokens ?? '-') +

        '</b> tokens' +

      '</div>' +


      '<div class="usage-item">' +

        'Total ' +

        '<b>' +

        (u.total_tokens ?? '-') +

        '</b> tokens' +

      '</div>';


    /*
     * Bring result into view.
     */

    document
      .getElementById("result")
      .scrollIntoView({

        behavior:"smooth",

        block:"nearest"

      });


  }


  catch(e){


    alert(
      "Request failed: " + e
    );


  }


  finally{


    /*
     * Re-enable button.
     */

    btn.disabled = false;

    btn.textContent = "Send";

  }

}


/* =========================================================
   CTRL + ENTER TO SEND
   ========================================================= */

document
  .getElementById("prompt")
  .addEventListener(
    "keydown",
    function(event){

      if(
        event.key === "Enter" &&
        (event.ctrlKey || event.metaKey)
      ){

        event.preventDefault();

        send();

      }

    }
  );

</script>


</body>
</html>
"""




