# Vision Station — Integration with other programs

| | |
|---|---|
| Document | 06 — Integration (FR-INT-1) |
| Version | 0.1 |
| Date | 2026-10-15 |
| Status | Implemented (VIA-0043) |

How another program on the same PC uses Vision Station as its vision system: it asks for an inspection, gets the result and its pictures, and shows the live camera. The other program owns its own screen, devices and process; Vision Station owns the camera, the jobs and the decision. Nothing of the other program goes into Vision Station.

```
other program ── HTTP / WebSocket on 127.0.0.1:8765 ── Vision Station ── camera
```

The camera is opened **only** by Vision Station. A USB camera serves one program at a time, so the other program never opens it: it takes the live view and the pictures from the API below.

## 1. Rules

- **Local only.** The API listens on `127.0.0.1` (system configuration `network`). These endpoints need **no login**, like the operator's trigger; everything else in the API needs a Supervisor or Maintainer login.
- **Never a pass by default.** The caller passes a part only on `status: done` with `result.outcome: PASS`. Anything else (`FAIL`, `ERROR`, `expired`, a 409, a timeout, Vision Station not answering) is not a pass.
- **One inspection at a time.** A request is accepted only when the station is `Ready` or `WaitingStill`; otherwise 409 with the state.
- **The job decides.** Which tools run, with which limits, is the active job (made and verified on Vision Station's own screens). The caller does not send parameters.

## 2. Station state

`GET /api/state` → `state` (`Starting`, `Preparing`, `Ready`, `WaitingStill`, `Inspecting`, `ShowingResult`, `CameraLost`, `Fault`, `Paused`), `message` (Portuguese, for a screen), `detail`, `job` (the active one), `camera` (`connected`, `last_frame_age_s`, `last_error`), `last_result`, `counters`.

Use it to show the operator why the vision step is not available ("Câmera desconectada", "Nenhum job ativo…").

## 3. Inspections

### Request

```
POST /api/inspections            {"reference": "caixa-0017"}      reference: optional, up to 100 characters
→ 202 {"id": "9f2c…", "reference": "caixa-0017", "status": "pending", "requested_at": "2026-10-15T14:32:07.120-03:00", …}
→ 409 {"detail": "A estação não está pronta", "code": "station_not_ready", "state": "Inspecting", "message": "Inspecionando…"}
```

The id is Vision Station's; `reference` is the caller's own id and comes back unchanged. The station inspects a frame captured **after** the request (FR-ACQ-6).

### Result

```
GET /api/inspections/{id}?wait_s=10                 wait_s: 0–30, waits for the result up to that long
→ 200 {
    "id": "9f2c…", "reference": "caixa-0017",
    "status": "done",                               pending | done | expired
    "result": {"outcome": "FAIL", "reason": "Faixa ausente em 40% da emenda", "scores": {"faixa": 0.6}, "duration_ms": 310, "at": "…"},
    "record_id": "20261015T143207-4be5ea",          in Vision Station's results, when recorded
    "job": {"id": "…", "name": "…", "version": 7},
    "frame_url": "/api/inspections/9f2c…/frame.jpg",
    "overlay_url": "/api/inspections/9f2c…/overlay.jpg",
    "message": null
  }
→ 404 {"code": "inspection_not_found"}            unknown id, or no longer kept (the last 50 are kept)
```

- `expired`: the request did not turn into an inspection within 30 s (the station stopped, the camera was lost, a job change). `message` says the station's state. Treat it as an error.
- `reason` is the job's text in Portuguese, ready for an operator screen.

### Pictures

`GET /api/inspections/{id}/frame.jpg` (the frame inspected) and `/overlay.jpg` (the same with the regions: green passed, red failed). Kept in memory with the request, up to 1920 px wide, so they exist even when Vision Station's own records keep only a sample of PASS images. They can be used directly in an `<img>` of another page.

## 4. Live view

- `GET /api/snapshot.jpg`: the newest frame, reduced (about 960 px), for a still preview.
- `WS /api/live`: binary messages are JPEG frames (at most 10 per second); text messages are JSON events (`status` every few seconds, `state` on each change, `result` with `record_id`). The schema is `LiveMessage` in `/api/openapi.json`.

## 5. A page of another program

A browser page served by another program (for example `http://localhost:8800`) is a different origin. Vision Station refuses browser requests from origins it does not know, so list the page's origin in `system.yaml`:

```yaml
network:
  allowed_origins: ['http://localhost:8800']      # exact origin, no path; takes effect after a restart
```

Then the page may call the endpoints above with `fetch` (CORS) and open `WS /api/live`. Images in `<img>` work without it. A program that calls Vision Station from its own server (not from the browser) needs nothing: requests without an `Origin` header are accepted.

## 6. Example (Python, from the other program's server)

```python
import requests

VS = "http://127.0.0.1:8765"

def check_with_vision(reference: str) -> tuple[bool, str, str | None]:
    """(passed, reason for the operator, overlay URL). Anything but a PASS is not a pass."""
    try:
        r = requests.post(f"{VS}/api/inspections", json={"reference": reference}, timeout=2)
        if r.status_code == 409:
            return False, r.json()["message"], None
        r.raise_for_status()
        body = requests.get(f"{VS}/api/inspections/{r.json()['id']}", params={"wait_s": 10}, timeout=15).json()
    except requests.RequestException:
        return False, "Sistema de visão sem resposta", None
    if body["status"] != "done":
        return False, body.get("message") or "Inspeção não concluída", None
    result = body["result"]
    return result["outcome"] == "PASS", result["reason"], body["overlay_url"] and f"{VS}{body['overlay_url']}"
```
