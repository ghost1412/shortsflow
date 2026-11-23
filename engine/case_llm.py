"""The text model of the case explainer: the cloud chain first, the model on this PC when the cloud cannot answer.

`engine.script_gen.get_llm_response` tries Gemini, then other providers, and its built-in Ollama step gives up after 12 seconds, far too short for
a script or a 190-line animation scene. So when every cloud provider fails (a rate limit, no key, no network) `make_ask` asks the local Ollama
model with a long timeout instead. After one cloud failure the next calls go straight to the local model for a few minutes, so a rate-limited run
does not wait through the retries again for every request.

`--case llm=auto` (default): cloud, then local.  `llm=local`: the model on this PC only (nothing leaves it).  `llm=cloud`: no local fallback.
The local model is `LOCAL_LLM_MODEL` in `.env` (for animation code a larger one such as gemma3:12b does better than a 7B model).
"""
import time

COOLDOWN = 300          # seconds the cloud is skipped after it failed


def local_chat(prompt, system="", model=None, url=None, timeout=900, max_tokens=8000, temperature=0.4, num_ctx=16384, json_mode=False, post=None):
    """One reply from the local Ollama server (chat endpoint, no streaming, no format restriction so code is returned as written). Raises
    RuntimeError when the server cannot answer or the reply is empty. `json_mode=True` asks Ollama for valid JSON only (the script step; never
    for code). Off by default, and nothing outside the case pipeline calls this function. `post` replaces requests.post (tests)."""
    from engine import script_gen
    if post is None:
        import requests
        post = requests.post
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    payload = {"model": model or script_gen.LOCAL_LLM_MODEL, "messages": messages, "stream": False,
               "options": {"temperature": temperature, "num_predict": max_tokens, "num_ctx": num_ctx}}
    if json_mode:
        payload["format"] = "json"
    try:
        r = post(url or script_gen.LOCAL_LLM_URL, json=payload, timeout=timeout)
        r.raise_for_status()
        text = (r.json().get("message") or {}).get("content") or ""
    except Exception as e:
        raise RuntimeError(f"The local model did not answer ({' '.join(str(e).split())[:120]})")
    if not text.strip():
        raise RuntimeError("The local model returned an empty answer")
    return text


def make_ask(system, mode="auto", cloud=None, local=None, log=print, clock=time.monotonic, json_mode=False):
    """A function `ask(prompt)` for the case pipeline. `cloud(prompt, system)` and `local(prompt, system)` default to get_llm_response and
    local_chat (tests pass fakes). See the module text for `mode`. `json_mode=True` makes the local model answer in valid JSON (for a script
    asked as JSON); the cloud call is unchanged."""
    if cloud is None:
        def cloud(prompt, system):
            from engine.script_gen import get_llm_response
            return get_llm_response(prompt, system_prompt=system, max_tokens=16000, timeout=300)
    if local is None:
        def local(prompt, system):
            return local_chat(prompt, system, json_mode=json_mode)
    state = {"down_until": 0.0}

    def via_local(prompt):
        reply = local(prompt, system)
        ask.last_source = "local"                  # which model answered last: callers that keep the result (the icon library) trust a local answer less
        return reply

    def ask(prompt):
        if mode == "local":
            return via_local(prompt)
        if mode == "auto" and clock() < state["down_until"]:
            return via_local(prompt)
        try:
            reply = cloud(prompt, system)
            if str(reply or "").strip():
                ask.last_source = "cloud"
                return reply
            error = "an empty answer"
        except Exception as e:
            error = " ".join(str(e).split())[:140]
        if mode == "cloud":
            raise RuntimeError(f"The cloud text model failed: {error}")
        state["down_until"] = clock() + COOLDOWN
        log(f"[Log] The cloud text model did not answer ({error}); using the model on this PC from here on.")
        return via_local(prompt)
    ask.last_source = None
    return ask
