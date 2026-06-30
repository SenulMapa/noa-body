"""hud.py — turn a TANI status event into a Halo display update.

The Halo is a 256x256 ROUND display. Everything here stays well inside the
circle (>=30px margins) so nothing clips. Drawing is Lua over send_lua — the
exact same calls run on real hardware and on the Python emulator.
"""

GREEN, RED, GREY, AMBER, WHITE = 0x36FF7A, 0xFF5B5B, 0x888888, 0xFFCC00, 0xFFFFFF

# bar geometry (centered, round-safe): x=40..216, 176px wide
BAR_X, BAR_Y, BAR_W, BAR_H = 40, 152, 176, 14


def _esc(s):
    # Lua source is latin-1 and the Halo font is ASCII, but TANI output isn't —
    # it'll contain em-dashes, smart quotes, emoji. Normalize the common ones,
    # drop the rest, then neutralize chars that would break a single-quoted Lua string.
    s = (s or "").replace("—", "-").replace("–", "-")
    s = s.encode("ascii", "ignore").decode("ascii")
    return s.replace("'", " ").replace("\\", " ")[:26]


def event_to_lua(event):
    """Map one status event -> a Halo draw call.
    Three zones, modeled on the noa_layout overlay: a status dot, the summary
    line, and a progress bar. This is the part that says 'a HUD is a status
    surface, not a terminal.'"""
    status = event.get("status", "running")
    dot = {"running": AMBER, "done": GREEN, "error": RED}.get(status, GREY)
    body = GREEN if status != "error" else RED
    filled = "true"  # solid disc; the color carries the state
    p = max(0.0, min(1.0, event.get("progress") or 0))
    fill_w = max(1, int(BAR_W * p))
    return (
        "frame.display.clear();"
        f"frame.display.circle(40,40,8,0x{dot:06X},{filled});"
        f"frame.display.text('{_esc(event.get('step'))}',62,34,0x{GREY:06X});"
        f"frame.display.text('{_esc(event.get('summary'))}',30,118,0x{body:06X});"
        f"frame.display.rect({BAR_X},{BAR_Y},{BAR_W},{BAR_H},0x{GREY:06X},false);"
        f"frame.display.rect({BAR_X},{BAR_Y},{fill_w},{BAR_H},0x{GREEN:06X},true);"
        "print(0)"
    )


async def render(frame, event):
    """Push one status update to the glasses (or emulator)."""
    await frame.send_lua(event_to_lua(event), await_print=True)
