"""What a fine-tune may change (FR-JOB-14, document 05 §7.12).

The Supervisor can move a tool's tolerance limits (the parameters its type marks `x-tunable`) and add *Boa* and *Ruim*
samples to the reference set. Nothing else: not a region, a tool, the camera, the trigger, the quality gates, and not
a limit's neighbours (the colour range itself). The server compares the draft with the version it starts from and
refuses the save if anything else differs, whatever the screen sent (a stale draft, a hand-made request).
"""

from dataclasses import dataclass
from typing import Any

from vision_station.core.i18n import tr
from vision_station.jobs.camera_profile import CameraProfile, dump_profile
from vision_station.jobs.job import Job
from vision_station.tools import get_tool

SAMPLES = "tests/images/"
EXPECTED = "tests/expected.yaml"


class NotTunable(ValueError):
    """The draft changes things a fine-tune may not. `fields` names them, by path."""

    def __init__(self, fields: dict[str, str]):
        super().__init__(", ".join(fields))
        self.fields = fields


@dataclass(frozen=True)
class Change:
    tool: str
    param: str
    old: Any
    new: Any


def tunable_params(tool_type: str, version: int) -> set[str]:
    """The parameters of a tool type that carry `x-tunable`."""
    props = get_tool(tool_type, version).params.model_json_schema().get("properties", {})
    return {name for name, p in props.items() if p.get("x-tunable")}


def _bare(job: Job) -> dict[str, Any]:
    """The job without what a save sets itself (identity, version, notes) and without the tunable values."""
    data = job.model_dump(mode="json")
    data.pop("job", None)
    for tool in data.get("tools", []):
        for name in tunable_params(tool["type"], tool["version"]):
            tool.get("params", {}).pop(name, None)
    return data


def _differences(a: Any, b: Any, path: str = "") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        return [d for k in sorted(set(a) | set(b)) for d in _differences(a.get(k), b.get(k), f"{path}.{k}" if path else k)]
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in _differences(x, y, f"{path}.{i}")]
    return [] if a == b else [path]


def tolerance_changes(base: Job, new: Job, base_profile: CameraProfile, new_profile: CameraProfile) -> list[Change]:
    """The limits that changed between two versions, or `NotTunable` when anything else did."""
    wrong = {path: tr("Só os limites de tolerância podem mudar no ajuste fino") for path in _differences(_bare(base), _bare(new))}
    if dump_profile(base_profile) != dump_profile(new_profile):
        wrong["profile"] = tr("A câmera não pode mudar no ajuste fino")
    if wrong:
        raise NotTunable(wrong)
    out: list[Change] = []
    for before, after in zip(base.tools, new.tools):
        for name in sorted(tunable_params(before.type, before.version)):
            old, now = before.params.get(name), after.params.get(name)
            if old != now:
                out.append(Change(before.id, name, old, now))
    return out


def check_files(base_files: dict[str, bytes], new_files: dict[str, bytes]) -> None:
    """Only samples may be added: the images under `tests/images/` that are new, and the expected set with them. A
    file the base version has is never changed or removed (the references the job was verified on)."""
    wrong: dict[str, str] = {}
    for path, data in base_files.items():
        if path == EXPECTED:
            continue
        if new_files.get(path) != data:
            wrong[f"files.{path}"] = tr("Um arquivo do job não pode mudar no ajuste fino")
    for path in new_files:
        if path not in base_files and not path.startswith(SAMPLES) and path != EXPECTED:
            wrong[f"files.{path}"] = tr("No ajuste fino só se acrescentam amostras")
    if wrong:
        raise NotTunable(wrong)


def check_expected(base: bytes | None, new: bytes | None) -> None:
    """The reference set only grows: every case of the base version stays as it was, and a new one is *Boa* (PASS) or
    *Ruim* (FAIL), the two kinds the gauges tell apart."""
    from vision_station.verification import parse_expected

    before = {c.image: c for c in parse_expected(base).cases} if base else {}
    after = {c.image: c for c in parse_expected(new).cases} if new else {}
    wrong = {f"expected.{image}": tr("Uma amostra do job não pode mudar nem sair no ajuste fino") for image, case in before.items() if after.get(image) != case}
    wrong.update({f"expected.{image}": tr("Uma amostra nova é Boa ou Ruim") for image, case in after.items() if image not in before and case.outcome == "ERROR"})
    if wrong:
        raise NotTunable(wrong)
