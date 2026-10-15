"""Request and response models of the API. They define the OpenAPI document, and the web interface's
TypeScript types are generated from it (docs/frontend.md §9), so a field changes here first."""

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel as _BaseModel, ConfigDict, Field

from vision_station.system.config import CameraSettings, SystemConfig

Outcome = Literal["PASS", "FAIL", "ERROR"]
Role = Literal["operator", "supervisor", "maintainer"]
StationState = Literal["Starting", "Preparing", "Ready", "WaitingStill", "Inspecting", "ShowingResult", "CameraLost", "Fault", "Paused"]
ImportStatus = Literal["added", "already_present", "renumbered"]


class BaseModel(_BaseModel):
    """In responses every field is always present (a default only fills a gap on the Python side),
    so the generated TypeScript types do not mark them optional."""

    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class Problem(BaseModel):
    """Every error response: a Portuguese message, a machine code, and optional details."""

    detail: str
    code: str
    problems: list[str] | None = None  # why a verification failed
    fields: dict[str, str] | None = None  # field path -> message, for validation errors
    verified: bool | None = None


# --- station --------------------------------------------------------------------------------


class Counters(BaseModel):
    PASS: int = 0
    FAIL: int = 0
    ERROR: int = 0
    total: int = 0


class JobRefOut(BaseModel):
    id: str
    name: str
    version: int


class CameraOut(BaseModel):
    connected: bool
    last_frame_age_s: float | None = None
    last_error: str | None = None


class ResultOut(BaseModel):
    outcome: Outcome
    reason: str
    scores: dict[str, float]
    duration_ms: int
    at: str | None = None  # when it was recorded (ISO 8601 with offset); None if results are not being recorded


class RecentResult(BaseModel):
    outcome: Outcome
    reason: str
    at: str


class StateOut(BaseModel):
    state: StationState
    message: str
    detail: str
    warnings: list[str]
    job: JobRefOut
    last_result: ResultOut | None = None
    last_record_id: str | None = None
    camera: CameraOut
    counters: Counters
    recent: list[RecentResult]  # the last 10 results, oldest first
    recording_failures: int
    version: str


class ToolInfo(BaseModel):
    name: str
    version: int


class AboutOut(BaseModel):
    version: str
    job_format: int
    tools: list[ToolInfo]


class LastResultOut(ResultOut):
    record_id: str | None = None


class InspectionRequest(BaseModel):
    reference: Annotated[str, Field(max_length=100)] = ""  # the caller's own id (a box, an order line); comes back as is


class InspectionOut(BaseModel):
    """An inspection another program asked for (FR-INT-1). `expired` means it never ran: treat it as an error."""

    id: str
    reference: str
    status: Literal["pending", "done", "expired"]
    requested_at: str
    result: ResultOut | None = None
    record_id: str | None = None  # in the result store, when it was recorded
    job: JobRefOut | None = None
    frame_url: str | None = None  # the inspection frame, JPEG
    overlay_url: str | None = None  # the frame with the regions drawn (green passed, red failed)
    message: str | None = None  # Portuguese, for an expired request


class Accepted(BaseModel):
    accepted: bool


class Sent(BaseModel):
    sent: str


# --- live socket (not part of the REST paths; exported into the OpenAPI document as LiveMessage) ----


class StatusMessage(StateOut):
    type: Literal["status"] = "status"


class StateMessage(BaseModel):
    type: Literal["state"] = "state"
    state: StationState
    previous: StationState | None = None
    message: str


class ResultMessage(ResultOut):
    type: Literal["result"] = "result"
    job: JobRefOut
    record_id: str | None = None


LiveMessage = Annotated[Union[StatusMessage, StateMessage, ResultMessage], Field(discriminator="type")]


# --- login ----------------------------------------------------------------------------------------


class LoginBody(BaseModel):
    role: Literal["supervisor", "maintainer"]
    password: str


class LoginOut(BaseModel):
    token: str
    role: Role
    expires_in_s: float


class WhoAmI(BaseModel):
    role: Role


class Ok(BaseModel):
    ok: bool


# --- jobs ---------------------------------------------------------------------------------------


class JobListItem(BaseModel):
    id: str
    name: str
    versions: list[int]
    latest: int


class ActiveRef(BaseModel):
    id: str
    version: int


class JobsOut(BaseModel):
    jobs: list[JobListItem]
    active: ActiveRef | None = None


class ActivateBody(BaseModel):
    override_reason: str | None = None


class ActivateOut(BaseModel):
    activated: bool
    verified: bool
    warnings: list[str]
    override: bool


class ImportItem(BaseModel):
    id: str
    version: int
    status: ImportStatus
    original_version: int


class ImportOut(BaseModel):
    kind: Literal["job", "backup"]
    imported: list[ImportItem]
    active_was: ActiveRef | None = None
    has_system_config: bool | None = None


# --- system configuration (maintainer) -------------------------------------------------------------


class SystemOut(BaseModel):
    config: SystemConfig
    data_root: str  # read-only on the screen
    restart_pending: list[str]  # sections saved but not in effect until the program restarts
    camera_drivers: list[str]
    last_backup_error: str | None = None


class SystemSaved(BaseModel):
    changed: list[str]
    restart_required: list[str]


class FolderCheckBody(BaseModel):
    path: Annotated[str, Field(min_length=1)]


class CameraCheckBody(CameraSettings):
    pass


class CheckOut(BaseModel):
    ok: bool
    message: str
    width: int | None = None
    height: int | None = None
    free_gb: float | None = None


class BackupOut(BaseModel):
    name: str
    size: int


# --- results --------------------------------------------------------------------------------------


class RecordOut(BaseModel):
    id: str
    at: str
    job_id: str
    job_name: str
    job_version: int
    outcome: Outcome
    reason: str
    scores: dict[str, float]
    timings: dict[str, float]
    duration_ms: float
    image_path: str | None = None
    overlay_path: str | None = None
    sampled: bool
    correct_outcome: Literal["PASS", "FAIL"] | None = None
    corrected_at: str | None = None
    corrected_by: str | None = None


class ResultsOut(BaseModel):
    total: int
    results: list[RecordOut]


class IncorrectBody(BaseModel):
    correct: Literal["PASS", "FAIL"]
    by: str = ""


class CollectionBody(BaseModel):
    enabled: bool


class CollectionOut(BaseModel):
    job_id: str
    enabled: bool
    dataset_images: int

