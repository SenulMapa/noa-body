"""app.py — Brilliant SDK host app: give Noa a body.

Runs a task through TANI and streams glanceable status to the Halo display.
The SAME code runs on real glasses and on the Python emulator — only the
`frame` object differs (the one-line swap below). That's the whole point:
you test on the emulator, Brilliant runs it on a Halo, identical code.

Usage:
    python app.py "build me a landing page"            # real Halo over BLE
    python app.py --emulator "build me a landing page" # no hardware, pygame window
"""
import argparse
import asyncio

import hud
import tani


async def make_frame(use_emulator):
    """The only difference between hardware and emulator lives here."""
    if use_emulator:
        from halo_emulator import HaloEmulator, EmulatorBrilliantMsg
        emu = HaloEmulator(sandbox_dir="./lua")
        return EmulatorBrilliantMsg(emu)
    from brilliant_msg import BrilliantMsg
    return BrilliantMsg()


async def main():
    ap = argparse.ArgumentParser(description="Stream TANI status to a Halo HUD.")
    ap.add_argument("task", nargs="*", help="the task to run")
    ap.add_argument("--emulator", action="store_true",
                    help="run against the Python emulator instead of real hardware")
    args = ap.parse_args()
    task = " ".join(args.task) or "build me a landing page for a coffee shop"

    frame = await make_frame(args.emulator)
    await frame.connect()  # scans + connects to the first Halo (or boots the emulator)
    print(f'connected — running: "{task}"')
    try:
        await frame.send_lua("frame.display.power_save(false);print(0)", await_print=True)

        async def on_status(event):
            # real TANI events may omit fields — never let that crash the render
            print(f"  {event.get('summary', '')}  ({int((event.get('progress') or 0) * 100)}%)")
            await hud.render(frame, event)

        result = await tani.run_task(task, on_status)
        await hud.render(frame, {"step": "done", "status": "done",
                                 "summary": result, "progress": 1.0})
        print(result)

        # On the emulator, save what's on screen as proof it rendered.
        if args.emulator and hasattr(frame, "get_framebuffer"):
            frame.get_framebuffer().save("hud.png")
            print("saved hud.png")

        await asyncio.sleep(4)  # leave the result on screen
    finally:
        await frame.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
