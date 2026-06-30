"""tani.py — the agentic worker behind the glasses.

run_task() does the work and calls on_status() with one event per step:
    {step, status: "running"|"done"|"error", summary, progress: 0..1}
and returns the final headline string.

Two modes, chosen by the TANI_API env var:
  • TANI_API set   → real TANI. Mints a short-lived GUEST token (no signup, no
                     secret in this repo), then streams a live run over SSE.
  • TANI_API unset → offline demo steps, so the emulator/hardware demo runs with
                     zero backend. This is the default for a fresh clone.

>>> INTEGRATION POINT <<<
The real path expects two endpoints on TANI's backend — see README "Guest access".
If TANI already streams in a different shape, adapt _real_run() to it; everything
upstream (app.py, hud.py, noa_tani_tool.py) is unchanged.
"""
import asyncio
import json
import os
import threading
import urllib.request

TANI_API = os.environ.get("TANI_API")  # e.g. https://api.tani.dev — unset = demo mode

FAKE_STEPS = [
    "understanding the request",
    "planning the approach",
    "writing the code",
    "running tests",
]


async def run_task(task, on_status):
    if TANI_API:
        return await _real_run(task, on_status)
    return await _demo_run(task, on_status)


# --------------------------------------------------------------------------- demo
async def _demo_run(task, on_status):
    n = len(FAKE_STEPS)
    for i, summary in enumerate(FAKE_STEPS):
        await on_status({"step": f"step {i + 1}/{n}", "status": "running",
                         "summary": summary, "progress": i / n})
        await asyncio.sleep(1.4)  # simulate work
    return f"done - {task[:26]}"


# ----------------------------------------------------------------------- real TANI
async def _real_run(task, on_status):
    """Get an ephemeral guest token, then stream a real run to on_status().
    SSE is read on a worker thread and handed to the asyncio loop via a queue,
    so on_status (which awaits BLE writes) stays on the main loop."""
    token = await asyncio.get_event_loop().run_in_executor(None, _guest_token)
    loop = asyncio.get_event_loop()
    q = asyncio.Queue()

    def producer():
        try:
            for ev in _sse_post(f"{TANI_API}/run", {"task": task}, token):
                loop.call_soon_threadsafe(q.put_nowait, ev)
        except Exception as e:
            loop.call_soon_threadsafe(q.put_nowait,
                {"step": "error", "status": "error", "summary": str(e)[:26], "progress": 0})
        finally:
            loop.call_soon_threadsafe(q.put_nowait, None)  # end sentinel

    threading.Thread(target=producer, daemon=True).start()

    result = "done"
    while True:
        ev = await q.get()
        if ev is None:
            break
        if ev.get("status") in ("done", "error"):
            result = ev.get("summary", result)
        await on_status(ev)
    return result


def _guest_token():
    """POST /guest -> {token, expires_in}. The token is short-lived and
    rate-limited server-side; nothing secret is stored in this repo."""
    data = _post_json(f"{TANI_API}/guest")
    return data["token"]


def _post_json(url, body=None, token=None):
    payload = json.dumps(body or {}).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _sse_post(url, body, token):
    """POST a task and yield each SSE `data:` event as a dict."""
    payload = json.dumps(body).encode()
    req = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "Accept": "text/event-stream",
    })
    with urllib.request.urlopen(req, timeout=600) as r:
        for raw in r:
            line = raw.decode("utf-8").strip()
            if line.startswith("data:"):
                chunk = line[5:].strip()
                if chunk:
                    try:
                        yield json.loads(chunk)
                    except json.JSONDecodeError:
                        pass
