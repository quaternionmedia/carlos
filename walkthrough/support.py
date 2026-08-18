"""What the walkthrough pages need that prose cannot hold.

This is not a demo harness. Per the one-executable-walkthrough record, a demo
harness beside the tests is a second copy wearing a different hat: the artifact
a reader sees has to come out of the same execution as an assertion about what
the code did, driving the real production component.

So the helpers here start the real server, drive the real page in a real
browser, and record what they saw. They assert nothing themselves — the pages
do that, in the same run that produces the picture.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MEDIA = Path(__file__).resolve().parent / "media"

# How long to wait for the server to answer before calling it unreachable.
# Generous, because a cold start on Windows imports FastAPI first.
STARTUP_TIMEOUT = 40.0


class Unreachable(RuntimeError):
    """The runtime a runtime-bound page needs is not there.

    Raised rather than skipped, deliberately. A skip is not a pass: a page that
    vanishes into a skip count when its browser is missing reports green for a
    demonstration nobody ran.
    """


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class LiveApp:
    """The real application, served on a port of its own.

    A port of its own rather than 8000: a developer's own server is usually up,
    and a page that quietly measured *that* would be testing whatever code
    happened to be running rather than the code in the tree.
    """

    def __init__(self) -> None:
        self.port = _free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.process: subprocess.Popen | None = None

    def start(self) -> "LiveApp":
        self.process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "src.main:app",
             "--host", "127.0.0.1", "--port", str(self.port), "--log-level", "warning"],
            cwd=REPO,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        self._await_health()
        return self

    def _await_health(self) -> None:
        deadline = time.monotonic() + STARTUP_TIMEOUT
        last = None
        while time.monotonic() < deadline:
            if self.process and self.process.poll() is not None:
                detail = (self.process.stderr.read() or b"").decode(errors="replace")
                raise Unreachable(f"the server exited before answering:\n{detail}")
            try:
                with urllib.request.urlopen(f"{self.base}/healthz", timeout=1) as answer:
                    if answer.status == 200:
                        return
            except (urllib.error.URLError, OSError, TimeoutError) as error:
                last = error
            time.sleep(0.2)
        raise Unreachable(f"{self.base}/healthz never answered ({last})")

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()


class Shots:
    """A screenshot library that only ever records.

    **It never compares and never gates.** A test that diffs images fails on a
    font and gets switched off, and switching it off costs the assertions that
    were sitting beside it. Every bit of regression protection lives in the
    page's own assertions about what the app did; the picture is a byproduct of
    the render those assertions ran against.

    What it does assert is that it wrote what it said it wrote — fifteen lines
    that turn "somebody forgot" into a red build.
    """

    def __init__(self, page_slug: str) -> None:
        self.slug = page_slug
        self.written: list[Path] = []
        MEDIA.mkdir(parents=True, exist_ok=True)

    def take(self, page, name: str, **kwargs) -> str:
        path = MEDIA / f"{self.slug}-{name}.png"
        page.screenshot(path=str(path), **kwargs)
        if not path.exists() or path.stat().st_size == 0:
            raise AssertionError(f"screenshot {path.name} was not written")
        self.written.append(path)
        return path.name

    def recorded(self) -> list[str]:
        return [p.name for p in self.written]


def open_rack(app: LiveApp, browser, width: int = 1280, height: int = 860):
    """A real browser on the real page, with its console piped somewhere useful.

    A browser JS error never reaches the server log — the log is identical
    whether the page works perfectly or throws on every keypress. So the console
    is captured here and the pages assert it is empty, which is the only way
    this project has ever been able to make that claim.
    """
    page = browser.new_page(viewport={"width": width, "height": height})
    page.errors = []
    page.on("pageerror", lambda error: page.errors.append(str(error)))
    page.on("console", lambda message:
            page.errors.append(f"console.{message.type}: {message.text}")
            if message.type == "error" else None)

    page.goto(app.base, wait_until="networkidle")
    # The palette is the last thing the page builds, so its presence is the
    # signal that every script ran.
    page.wait_for_selector("#tool-palette", timeout=10_000)
    return page


def wedge_labels(page) -> list[str]:
    """Every label on the ring that is open, in ring order."""
    return page.locator(".rad-label").all_text_contents()


def pick(page, label: str) -> None:
    """Choose a menu item the way a hand does.

    The radial menu resolves a pointer position into a wedge - it listens on the
    document for movement and commits on release, and knows nothing about which
    element was under the cursor. So this moves the real pointer onto the
    label's own box and releases there, which is the gesture, rather than
    dispatching a synthetic click at an element.
    """
    target = page.locator(".rad-label", has_text=label).first
    target.wait_for(state="visible", timeout=5_000)
    box = target.bounding_box()
    if box is None:
        raise AssertionError(f"the ring has no wedge labelled {label!r}")
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.up()


def open_menu(page, x: int, y: int) -> None:
    """Right-click, which is one of the two ways to a menu."""
    page.mouse.move(x, y)
    page.mouse.click(x, y, button="right")
    page.wait_for_selector(".rad-wedge", timeout=5_000)
