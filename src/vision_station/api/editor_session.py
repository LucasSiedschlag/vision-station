"""The editor's live session: the draft on every new camera frame (FR-UI-12, document 05 §9.5, §19.1).

One WebSocket, `/api/editor/live`, for one maintainer at a time. The page opens it, says who it is in its first
message, sends the draft (the files once, the job and the profile at each change) and gets back, at most a few times a
second, a text message with the result of the draft on the newest frame and then that frame as a JPEG. The
station is paused while the session lasts and resumes when it ends, unless something else had paused it first.

The newest settings win: a run is never queued behind another one, and a frame that arrives while the draft is being
measured is simply the next one. A draft that is refused, a lost camera and a station that is busy are messages,
never a closed socket.
"""

import asyncio
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from pydantic import ValidationError

from vision_station.algorithms import metrics
from vision_station.api import schemas as m
from vision_station.cameras import Frame
from vision_station.core.i18n import render, using

SESSION_JOB_ID = "00000000-0000-4000-8000-0000000000e1"  # a draft in a session has no identity of its own: it is never saved
IDLE_S = 600.0  # a session that hears nothing for this long ends and resumes the station (document 05 §9.5)
DEFAULT_FPS = 4.0  # document 05 §19.1: tier R up to 5 runs per second, tier M 2; a project sets it in the performance settings


@dataclass
class SessionEnv:
    """What the session needs from the application, handed in so this module does not depend on it."""

    deps: Any
    build: Callable[..., Any]  # build(draft, *, job_id, version, parent, author, extra=None) -> JobBundle, or raises Problem
    result_out: Callable[[Any, Any], Any]
    encode: Callable[[Any, int, int], bytes]
    origin_allowed: Callable[[str | None], bool]
    language: Callable[[Any], str]  # the language a socket asks for
    Problem: type
    state: dict[str, Any]  # shared between sessions: `busy`


# the states a pause takes the station out of: it is running, or about to run, an inspection
_PAUSABLE = ("Ready", "WaitingStill", "ShowingResult", "Preparing", "Inspecting")


async def pause_station(controller: Any, loop: asyncio.AbstractEventLoop, wait_s: float = 3.0) -> bool:
    """Pause the station and say whether it is the session's pause. A pause is only taken from some states (an
    inspection in progress ends first), so it is asked again until it holds. A station that is not running, in Fault,
    CameraLost or Starting, has nothing to pause and nothing the session may resume later: *Tentar de novo* is the
    person's, so it is left alone."""
    deadline = loop.time() + wait_s
    while loop.time() < deadline:
        state = controller.state.value
        if state == "Paused":
            return True
        if state not in _PAUSABLE:
            return False
        controller.pause()
        await asyncio.sleep(0.05)
    return False


def _message(**fields: Any) -> str:
    return json.dumps(fields, ensure_ascii=False)


async def run(ws: Any, env: SessionEnv) -> None:
    deps = env.deps
    if not env.origin_allowed(ws.headers.get("origin")):
        await ws.close(code=1008)
        return
    await ws.accept()
    loop = asyncio.get_running_loop()
    language = env.language(ws)
    inbox: asyncio.Queue[str | None] = asyncio.Queue()

    async def read() -> None:
        try:
            async for text in ws.iter_text():
                await inbox.put(text)
        except Exception:
            pass
        await inbox.put(None)  # the other end is gone

    reader: asyncio.Task[None] | None = None
    paused_by_us = False
    owns = False
    try:
        # the first message says who it is: a browser cannot put a token in the headers of a WebSocket
        try:
            first = json.loads(await asyncio.wait_for(ws.receive_text(), 10))
        except Exception:
            first = {}
        if first.get("type") != "hello" or deps.auth.role_of(first.get("token")) != "maintainer":
            with using(language):
                await ws.send_text(_message(type="error", code="login_required", message=render("É preciso entrar como Mantenedor")))
            await ws.close(code=1008)
            return
        if env.state.get("busy"):
            with using(language):
                await ws.send_text(_message(type="error", code="session_busy", message=render("Outra sessão do editor já está aberta")))
            await ws.close(code=1008)
            return
        env.state["busy"] = owns = True
        max_fps = float(getattr(deps, "editor_fps", DEFAULT_FPS))
        fps = min(max_fps, float(first.get("fps") or max_fps))
        station = deps.controller.state.value
        if station != "Paused":
            paused_by_us = await pause_station(deps.controller, loop)  # only a pause of ours is ours to end
        reader = asyncio.create_task(read())

        bundle: Any = None
        extra: dict[str, bytes] | None = None  # the files of the draft, kept between messages
        last_stamp: float | None = None
        sent_camera: bool | None = None
        frame_id = 0
        heard = loop.time()
        next_run = loop.time()
        await ws.send_text(_message(type="ready", fps=fps, paused_by_session=paused_by_us, station=deps.controller.state.value))

        def make(msg: dict[str, Any]) -> Any:
            """The bundle of a `draft` message. The files come only when they changed (a patch has none)."""
            nonlocal extra
            carries_files = "add_files" in msg or "remove_files" in msg or "base" in msg
            draft = m.JobDraft.model_validate(
                {"job": msg["job"], "profile": msg["profile"], "base": msg.get("base"), "add_files": msg.get("add_files") or {}, "remove_files": msg.get("remove_files") or []}
            )
            made = env.build(draft, job_id=SESSION_JOB_ID, version=1, parent=None, author="maintainer", extra=None if carries_files or extra is None else extra)
            if carries_files or extra is None:
                extra = dict(made.extra)
            return made

        def measure(current: Any, frame: Frame) -> bytes | None:
            result = replace(deps.inspect(current, frame), simulated=True)
            details = dict(result.details)
            anchor = details.get("anchor")
            with using(language):  # a thread of the pool does not inherit the language of the socket: say it here (TD-30)
                shown = env.result_out(result, None).model_dump(mode="json")
            body = dict(
                type="result", frame_id=frame_id, width=frame.image.shape[1], height=frame.image.shape[0], result=shown,
                regions=[m.RegionOut(**r).model_dump(mode="json") for r in details.get("regions", [])],
                anchor=anchor["rect"] if anchor else None, tools=details.get("tools", {}), timings=details.get("timings", {}),
            )
            measure.text = _message(**body)  # type: ignore[attr-defined]
            return env.encode(frame.image, deps.frame_width, deps.jpeg_quality)

        def frame_metrics(frame: Frame) -> str:
            """What the camera controls show of a frame (document 05 §19.5): the sharpness of the gates, the histogram and the clipping."""
            counts = metrics.histogram(frame.image)
            low, high = metrics.clipped(counts)
            return _message(type="metrics", frame_id=frame_id, sharpness=metrics.sharpness(frame.image), histogram=counts, clipped_low=low, clipped_high=high)

        while True:
            wait = max(0.0, next_run - loop.time())
            try:
                text = await asyncio.wait_for(inbox.get(), min(wait, 0.25) if wait else 0.0)
            except asyncio.TimeoutError:
                text = ""
            if text is None:
                return
            if text:
                heard = loop.time()
                try:
                    msg = json.loads(text)
                except ValueError:
                    continue
                kind = msg.get("type")
                if kind == "draft":
                    try:
                        bundle = await loop.run_in_executor(None, make, msg)
                        last_stamp = None  # measure the new draft on the frame already there
                        await ws.send_text(_message(type="draft_ok"))
                    except ValidationError as exc:
                        bundle = None
                        with using(language):
                            await ws.send_text(_message(type="draft_error", message=render("O job tem campos inválidos"), fields={".".join(str(p) for p in e["loc"]): e["msg"] for e in exc.errors()}))
                    except env.Problem as exc:  # type: ignore[misc]
                        bundle = None
                        with using(language):
                            await ws.send_text(_message(type="draft_error", message=render(exc.detail), fields=exc.extra.get("fields", {})))
                elif kind == "rate":
                    fps = max(0.2, min(max_fps, float(msg.get("fps") or fps)))
                elif kind == "close":
                    return
                continue
            now = loop.time()
            if now - heard > IDLE_S:
                await ws.send_text(_message(type="idle"))
                return
            if now < next_run:
                continue
            next_run = now + 1.0 / fps
            frame = deps.acquisition.latest()
            camera_ok = (not deps.acquisition.stalled()) and frame is not None
            if camera_ok != sent_camera:
                sent_camera = camera_ok
                with using(language):
                    await ws.send_text(_message(type="camera", connected=camera_ok, message="" if camera_ok else render("Câmera desconectada"), error=deps.acquisition.last_error))
            if not camera_ok or frame is None or frame.timestamp == last_stamp:
                continue
            last_stamp = frame.timestamp
            frame_id += 1
            await ws.send_text(await loop.run_in_executor(None, frame_metrics, frame))  # whatever the draft: step 1 has no tools yet
            if bundle is None:
                continue
            started = time.monotonic()
            try:
                with using(language):
                    jpeg = await loop.run_in_executor(None, measure, bundle, frame)
            except Exception as exc:  # a draft that cannot run on this picture is told, and the session goes on
                with using(language):
                    await ws.send_text(_message(type="run_error", frame_id=frame_id, message=f"{type(exc).__name__}: {exc}"))
                continue
            await ws.send_text(measure.text)  # type: ignore[attr-defined]
            await ws.send_bytes(jpeg)  # type: ignore[arg-type]
            next_run = max(next_run, started + 1.0 / fps)  # a slow run is not followed by a rush
    except Exception:
        # the other end vanished, or the server is stopping: the finally below leaves the station as it was
        pass
    finally:
        if reader is not None:
            reader.cancel()
        if paused_by_us:
            deps.controller.resume()
        if owns:
            env.state["busy"] = False
        try:
            await ws.close()
        except Exception:
            pass
