# ============================================================================
#  Drop-in tool for noa-assistant: gives Noa a "body" via TANI.
#
#  Matches the EXACT shape used in noa-assistant/assistant/gpt_assistant.py
#  (and claude_assistant.py). Integration is two edits + this file:
#
#    1. In gpt_assistant.py, append RUN_TANI_TOOL_GPT to the `TOOLS` list and add
#       `RUN_TANI_TOOL_NAME: handle_tani_task` to the `tool_functions` dict.
#    2. In claude_assistant.py, append RUN_TANI_TOOL_CLAUDE to its `TOOLS` list
#       and the same entry to its `tool_functions` dict.
#
#  Noa then decides on its own when to hand a multi-step job to TANI; the result
#  is spoken back, while app.py / hud.py stream live status to the Halo display.
# ============================================================================
import tani

RUN_TANI_TOOL_NAME = "run_tani_task"

# --- OpenAI tool-use format (for gpt_assistant.py TOOLS list) ---
# The `description` is the most important line here: it's what the model reads to
# decide WHEN to reach for TANI instead of answering itself. Tune it.
RUN_TANI_TOOL_GPT = {
    "type": "function",
    "function": {
        "name": RUN_TANI_TOOL_NAME,
        "description": (
            "Hand a multi-step build, coding, or autonomous task to TANI, an "
            "agentic worker that operates over several minutes and streams progress "
            "to the user's display. Use this ONLY for real work the user wants DONE "
            "(e.g. 'build me a landing page', 'refactor this repo', 'research X and "
            "draft a report') — NOT for quick questions you can answer yourself."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "the task to perform, in plain language"}
            },
            "required": ["task"],
        },
    },
}

# --- Anthropic tool-use format (for claude_assistant.py TOOLS list) ---
RUN_TANI_TOOL_CLAUDE = {
    "name": RUN_TANI_TOOL_NAME,
    "description": RUN_TANI_TOOL_GPT["function"]["description"],
    "input_schema": RUN_TANI_TOOL_GPT["function"]["parameters"],
}


async def handle_tani_task(task: str = "", **kwargs) -> str:
    """Async handler registered in noa-assistant's `tool_functions` dict.
    Runs the task via TANI and returns the short headline Noa speaks back.
    (Live status to the glasses is driven separately by app.py / hud.render.)
    Signature mirrors noa-assistant's other tool handlers: str in, str out."""
    async def _silent(_event):
        pass
    try:
        return await tani.run_task(task, _silent)
    except Exception as e:  # surface failures to Noa instead of swallowing them
        return f"TANI hit an error: {e}"
