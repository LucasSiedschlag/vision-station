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
    """Every error response: a message in the language of the request (Accept-Language), a machine code, and optional details."""

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
    number: int | None = None  # the machine's job number (R3)
    content_hash: str | None = None  # of the saved version's files: exactly which version decided (TD-22)


class CameraOut(BaseModel):
    connected: bool
    last_frame_age_s: float | None = None
    last_error: str | None = None


Unit = Literal["fraction", "count", "score"]


class CriterionOut(BaseModel):
    """One check of a tool. `<tool type>.<code>` is its reason code when it fails."""

    code: str
    kind: Literal["min", "max", "rule"]
    measure: str | None = None
    value: float | None = None
    limit: float | None = None
    passed: bool
    score: float
    margin: float | None = None  # how far inside the limit, in the measure's unit (negative: outside); None for a rule


class ToolResultOut(BaseModel):
    id: str
    type: str
    version: int
    passed: bool
    score: float
    margin: float | None = None  # of the decisive criterion
    values: dict[str, float] = {}  # the measures, by name
    units: dict[str, Unit] = {}  # fraction is 0..1
    criteria: list[CriterionOut] = []
    affects_result: bool = True  # False: informative, never decides (FR-INS-13)
    error: str = ""  # an informative tool that could not run
    error_code: int = 0  # and its code (E301..E304)
    region: list[float] | None = None  # where the tool looked: x0, y0, x1, y1 as fractions of the frame


class ReasonCodeOut(BaseModel):
    tool: str
    code: str  # `<tool type>.<criterion>`, stable (architecture §10.3)


class FixtureOut(BaseModel):
    name: str
    x: float  # centre, fraction of the frame
    y: float
    angle: float | None = None  # None until the locators measure it (R1)
    scale: float | None = None
    score: float


class TriggerOut(BaseModel):
    source: Literal["image", "manual", "api", "machine"]
    reference: str = ""
    part_id: str = ""
    at: str | None = None  # ISO 8601 with offset


class ResultContract(BaseModel):
    """The result contract (architecture §10.3, TD-22). Every field is optional so older clients and records read."""

    sequence: int | None = None  # +1 per inspection, wraps at 2**32
    error_code: int | None = None  # ERROR: a code of the catalog; 0 otherwise; None on records from before the contract
    reason_codes: list[ReasonCodeOut] = []
    tools: list[ToolResultOut] = []
    fixtures: list[FixtureOut] = []
    trigger: TriggerOut | None = None
    acquired_at: str | None = None
    decided_at: str | None = None
    simulated: bool = False  # never signalled to a machine (FR-INT-12)


class ResultOut(ResultContract):
    outcome: Outcome
    reason: str
    scores: dict[str, float]
    duration_ms: int
    at: str | None = None  # when it was recorded (ISO 8601 with offset); None if results are not being recorded
    job: JobRefOut | None = None


class RecentResult(BaseModel):
    outcome: Outcome
    reason: str
    at: str
    record_id: str | None = None  # its picture is `/api/results/{record_id}/thumb`


class StateOut(BaseModel):
    state: StationState
    language: Literal["pt-BR", "en"] = "pt-BR"  # the station language: the operator screen speaks it (TD-30)
    message: str
    showing_result: bool = False  # the last verdict is still shown, also when the station is already Ready again
    detail: str
    warnings: list[str]
    job: JobRefOut
    last_result: ResultOut | None = None
    last_record_id: str | None = None
    camera: CameraOut
    counters: Counters
    recent: list[RecentResult]  # the last 10 results, oldest first
    markings: Literal["always", "on_fail", "never"] = "on_fail"  # when the operator screen draws the regions on the image (frontend.md §18)
    operator_markings: bool = True  # whether the operator may turn them on and off
    recording_failures: int
    version: str


class ToolInfo(BaseModel):
    name: str
    version: int


class AboutOut(BaseModel):
    version: str
    build: str  # version · git commit · build date (TD-15)
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
    message: str | None = None  # for an expired request, in the language of the request


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
    showing_result: bool = False  # see StateOut; a message with the same state says the held verdict ended


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
    updated_at: str  # when the latest version was saved
    author: str  # who saved it


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
    default_backup_folder: str = ""  # where backups go when no folder is chosen: the screen starts from it
    can_pick_folder: bool = False  # this PC can open its own folder chooser (Windows, API on this PC)


class BenchmarkHost(BaseModel):
    cpus: int
    machine: str
    system: str
    python: str
    opencv: str


class BenchmarkRunSettings(BaseModel):
    megapixels: list[float]
    repeats: int
    reference_mp: float


class BenchmarkMeasured(BaseModel):
    type: str  # `tool:color:1`, `locator:blob:2`
    ms: dict[str, float]  # the median time by megapixels
    budget_ms: float | None  # on the reference size; None: no budget declared
    within_budget: bool | None


class BenchmarkUnmeasured(BaseModel):
    type: str
    reason: str  # a code, see `reason_text`
    reason_text: str


class BenchmarkReport(BaseModel):
    """The last benchmark of this PC (FR-ADM-5, TD-28): times by tool, the tier and the proposed thread limit."""

    format: int
    at: str  # UTC, ISO 8601
    host: BenchmarkHost
    settings: BenchmarkRunSettings
    reference_ms: float
    tier: Literal["M", "R"] | None  # None: slower than tier M
    thread_limit: int  # proposed, not applied
    measured: list[BenchmarkMeasured]
    unmeasured: list[BenchmarkUnmeasured]
    over_budget: list[str]


class BenchmarkOut(BaseModel):
    report: BenchmarkReport | None  # None: this PC was never measured


class SystemSaved(BaseModel):
    changed: list[str]
    restart_required: list[str]


class FolderPickBody(BaseModel):
    initial: str | None = None  # the folder the chooser opens on


class FolderPickOut(BaseModel):
    path: str | None  # None: the person cancelled


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


class RecordOut(ResultContract):
    id: str
    at: str
    job_id: str
    job_name: str
    job_version: int
    outcome: Outcome
    reason: str
    scores: dict[str, float]
    timings: dict[str, float]  # seconds per step: quality, locate, tools, total
    tool_timings: dict[str, float] = {}  # seconds per tool id
    duration_ms: float
    image_path: str | None = None
    overlay_path: str | None = None
    sampled: bool
    correct_outcome: Literal["PASS", "FAIL"] | None = None
    corrected_at: str | None = None
    corrected_by: str | None = None
    job_hash: str | None = None
    simulated: bool | None = False  # None on a record from before the result contract: not known


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



# --- management: tools, jobs, camera, reference, users, audit, dataset (VIA-0026) ----------------------


class CriterionSpecOut(BaseModel):
    """One measure of a tool that has limits: what a tolerance gauge draws (frontend.md §9.3)."""

    value: str  # the key of the result's values
    label: str
    unit: Literal["fraction", "count", "score"]
    range: list[float | None]  # [low, high]; a high of None: no natural top, the gauge takes it from the data
    limits: dict[Literal["min", "max"], str]  # the tool's parameters holding the limits
    direction: Literal["at_least", "at_most", "between"]
    level: Literal[1, 2, 3]


class TypeInfo(BaseModel):
    """A tool or locator type the editor can offer, with the JSON Schema of its parameters. The schema carries
    `x-level`, `x-group`, `x-widget`, `x-unit` and `x-tunable` on each parameter. `criteria` is empty for a locator."""

    name: str
    version: int
    description: str
    params_schema: dict[str, Any]
    criteria: list[CriterionSpecOut] = []


class TypesOut(BaseModel):
    tools: list[TypeInfo]
    locators: list[TypeInfo]
    builtin_rois: list[str]  # ROI names every job has without declaring them


class VersionInfo(BaseModel):
    version: int
    created_at: str
    author: str
    notes: str
    parent_version: int | None = None
    active: bool
    tuned: bool = False  # saved by a fine-tune of tolerances (FR-JOB-14)


class JobDetailOut(BaseModel):
    id: str
    name: str
    description: str
    versions: list[VersionInfo]  # newest first


class JobFileOut(BaseModel):
    path: str
    size: int
    sha256: str


class JobVersionOut(BaseModel):
    """One saved version, whole: what the editor opens."""

    id: str
    version: int
    job: dict[str, Any]  # job.yaml as JSON
    profile: dict[str, Any]  # the camera profile as JSON
    files: list[JobFileOut]  # the other files (reference, templates, models, reference set)
    reference: dict[str, Any] | None = None  # reference/reference.meta.yaml, when there is one
    expected: dict[str, Any] | None = None  # tests/expected.yaml, when there is one


class JobDraft(BaseModel):
    """A job being edited. Identity, version, author and date are set by the server on save."""

    job: dict[str, Any]
    profile: dict[str, Any]
    base: ActiveRef | None = None  # copy the other files from this saved version
    latest: int | None = None  # the newest version the editor saw; if newer ones exist, saving is refused (default: base)
    add_files: dict[str, str] = {}  # path -> base64 content (added or replaced)
    remove_files: list[str] = []
    notes: Annotated[str, Field(max_length=500)] = ""


class DraftCheckOut(BaseModel):
    ok: bool
    message: str | None = None  # for the whole draft, in the language of the request
    fields: dict[str, str] = {}  # path.to.field -> message


class SavedVersion(BaseModel):
    id: str
    version: int


class TuneOut(BaseModel):
    """A fine-tune saved as the next version, and what verifying it said. It is not active: the person activates it."""

    id: str
    version: int
    verified: bool
    problems: list[str]
    changes: list[str]  # "tool: parameter, old → new", in the language of the request


class DuplicateBody(BaseModel):
    version: Annotated[int, Field(ge=1)]
    name: Annotated[str, Field(min_length=1, max_length=120)]


class DraftTestBody(BaseModel):
    draft: JobDraft
    image: str | None = None  # base64 PNG or JPEG; None: the camera's newest frame


class RegionOut(BaseModel):
    tool: str
    roi: str
    rect: list[int]  # x0, y0, x1, y1 in pixels of the frame
    passed: bool
    affects_result: bool = True
    corners: list[list[float]] | None = None  # the outline in pixels, when the region is turned


class FixtureShape(BaseModel):
    """A fixture as the editor draws it: its upright box, the pose and, when turned, the outline (architecture §14)."""

    name: str = "anchor"
    rect: list[float]  # x0, y0, x1, y1 as fractions of the frame
    angle: float = 0.0
    scale: float = 1.0
    score: float = 1.0
    taught: list[float] | None = None  # the box it was taught with, before the angle and the scale: what regions are fractions of
    corners: list[list[float]] | None = None  # in pixels


class DraftTestOut(BaseModel):
    result: ResultOut
    regions: list[RegionOut]
    anchor: list[float] | None = None  # x0, y0, x1, y1 as fractions of the frame: the first fixture's upright box
    fixtures: list[FixtureShape] = []
    tools: dict[str, Any]  # each tool's details (measures, codes read, matches)
    timings: dict[str, Any]
    width: int
    height: int
    overlay: str  # base64 JPEG of the frame with the regions drawn


class LocateSampleOut(BaseModel):
    """The fixtures of a draft on one picture of its reference set: where each was found, or why not (the anchor step)."""

    image: str  # path inside the job
    kind: Literal["reference", "good", "bad", "error"]
    width: int
    height: int
    fixtures: list[FixtureShape]  # the ones found, in order; fewer than the job has when it stopped
    found: bool  # all of them, inside their ranges
    error_code: int = 0
    reason: str = ""  # in the language of the request


class LocateOut(BaseModel):
    ok: bool
    message: str | None = None
    fields: dict[str, str] = {}
    samples: list[LocateSampleOut] = []


class CaseRunOut(BaseModel):
    """One sample run through a draft: what the job said against what was expected (Validar, frontend.md §4.3)."""

    image: str  # path inside the job, tests/images/<name>.png
    expected: Outcome
    outcome: Outcome | None  # None: it could not be run
    ok: bool
    message: str  # "<image>: <what>", in the language of the request
    reason: str = ""
    duration_ms: int | None = None


class VerifyOut(BaseModel):
    """The draft on every sample of its reference set: the same run that activation does (design rule 4)."""

    ok: bool  # every sample as expected (and there is at least one)
    message: str | None = None  # the draft was refused, or there is nothing to run
    fields: dict[str, str] = {}
    cases: list[CaseRunOut] = []
    max_ms: int | None = None  # the slowest sample


class DiffOut(BaseModel):
    id: str
    version: int
    against: int
    diff: str  # unified diff of job.yaml and the camera profile


class SettingResult(BaseModel):
    status: str  # applied, not_supported, out_of_range, failed...
    detail: str = ""


class CameraStateOut(BaseModel):
    connected: bool
    last_error: str | None = None
    profile: dict[str, Any] | None = None  # the profile in use
    applied: bool  # the profile in use was written to the camera
    settings: dict[str, SettingResult]  # per setting, from the last write
    station_paused: bool


class BatchSampleOut(BaseModel):
    """One picture of the draft's samples run through it: the reference, a *Boa*, a *Ruim* or one that should give ERROR."""

    image: str  # path inside the job
    kind: Literal["reference", "good", "bad", "error"]
    expected: Outcome | None = None  # None for the reference
    ok: bool  # as expected (the reference: a pass)
    message: str  # in the language of the request
    result: ResultOut | None = None  # None: it could not be run


class ToolSeparationOut(BaseModel):
    """How well one tool alone keeps the good samples apart from the bad ones."""

    tool: str
    good_total: int
    good_passed: int
    bad_total: int
    bad_failed: int


class BatchOut(BaseModel):
    """The draft on all its samples (frontend.md §9.4): what feeds the dots of the gauges and the separation line."""

    ok: bool  # the draft was accepted and could be run
    message: str | None = None
    fields: dict[str, str] = {}
    samples: list[BatchSampleOut] = []
    tools: list[ToolSeparationOut] = []
    good_total: int = 0  # *Boa* samples, and how many came out as expected
    good_ok: int = 0
    bad_total: int = 0
    bad_ok: int = 0
    max_ms: int | None = None


class LimitProposalOut(BaseModel):
    """A limit the samples suggest for one side of one criterion of one tool (FR-UI-14)."""

    tool: str
    criterion: str  # the measure's name, a key of the tool's values
    label: str
    param: str  # the tool parameter that holds the limit
    side: Literal["min", "max"]
    unit: Literal["fraction", "count", "score"]
    current: float | None
    proposed: float | None  # None: nothing is proposed, `reason` says why
    reason: Literal["", "few_good", "overlap", "bounds"]
    basis: Literal["gap", "from_good", ""]
    worst_good: float | None
    nearest_bad: float | None
    margin_good: float | None
    margin_bad: float | None
    good_n: int
    bad_n: int


class LimitsOut(BaseModel):
    ok: bool
    message: str | None = None
    fields: dict[str, str] = {}
    proposals: list[LimitProposalOut] = []


class SuggestLimitsBody(BaseModel):
    draft: JobDraft
    tool: str | None = None  # only this tool; None: all of them


class SuggestColourBody(BaseModel):
    include: Annotated[list[str], Field(min_length=1, max_length=20)]  # base64 PNG or JPEG crops of the image: the colour
    exclude: Annotated[list[str], Field(max_length=20)] = []  # and what must stay out of the range


class ColourProposalOut(BaseModel):
    """A color range for the color tool, from the pixels the person dragged over (FR-UI-13). OpenCV scales (hue 0..179)."""

    ok: bool
    message: str | None = None
    hue: tuple[int, int] | None = None  # None: any hue (grays, black, white)
    s_min: int = 0
    s_max: int = 255
    v_min: int = 0
    v_max: int = 255
    pixels: int = 0
    kept: float = 0.0  # share of the sampled colour inside the range
    leak: float | None = None  # share of the excluded pixels inside it; None: nothing was excluded


class ExposureStepOut(BaseModel):
    exposure_us: float
    saturated_percent: float


class AutoExposureOut(BaseModel):
    """What *Auto uma vez* found (FR-ACQ-11). The camera is left on `value_us`; the editor writes it in the draft as a
    fixed exposure."""

    value_us: float
    saturated_percent: float  # what that exposure gives in the measuring region
    target_percent: float
    reached: bool  # within a point of the target; False: the best the range allowed
    limit: Literal["", "max", "min"]  # "max": still short of the target at the maximum exposure; "min": over it at the shortest
    steps: list[ExposureStepOut]


class ReferenceBody(BaseModel):
    image: str | None = None  # base64 PNG or JPEG; None: the camera's newest frame


class ReferenceOut(BaseModel):
    files: dict[str, str]  # path -> base64, to add to the draft (reference image and its measures)
    brightness: float
    sharpness: float
    width: int
    height: int


class ReferenceCaseBody(BaseModel):
    draft: JobDraft
    image: str | None = None
    name: Annotated[str, Field(min_length=1, max_length=60, pattern=r"^[A-Za-z0-9_-]+$")]


class ReferenceCaseOut(BaseModel):
    path: str  # tests/images/<name>.png
    image: str  # base64 PNG, to add to the draft
    result: ResultOut  # what the draft says about it now: the editor confirms or corrects it as the expected one


class BackupItem(BaseModel):
    name: str
    size: int
    created_at: str


class BackupsOut(BaseModel):
    folder: str | None
    backups: list[BackupItem]  # newest first


class SetupStepOut(BaseModel):
    id: Literal["maintainer_password", "camera", "performance", "supervisor_password", "machine", "backup", "first_job"]
    state: Literal["done", "todo", "unavailable"]
    detail: str | None = None  # why it is not done, or what is done; the reason for an unavailable step


class SetupStatusOut(BaseModel):
    steps: list[SetupStepOut]
    needs_setup: bool  # the Maintainer has no password, the camera sends nothing, or there is no job
    maintainer_password_missing: bool  # the wizard is open without a login while this is true


class SetupCameraOut(BaseModel):
    name: str  # as the PC lists it
    driver: str
    connection: dict[str, Any]  # goes into `camera.connection` of the system configuration
    model: str | None  # the id of the validated model (it names the picture), None when not validated
    validated: bool


class SetupCamerasOut(BaseModel):
    available: bool  # false: this PC cannot list cameras (not Windows, or the library is missing)
    cameras: list[SetupCameraOut]


class SetupOpenOut(BaseModel):
    open: bool  # the Maintainer has no password and the API listens on this PC only


class SetupPasswordBody(BaseModel):
    password: str  # the length rule is the server's, so the refusal comes with a readable reason


class UserOut(BaseModel):
    role: Literal["supervisor", "maintainer"]
    has_password: bool
    changed_at: str | None = None


class UsersOut(BaseModel):
    users: list[UserOut]


class PasswordBody(BaseModel):
    password: Annotated[str, Field(min_length=8, max_length=200)]
    current_password: str | None = None  # a supervisor changing their own password confirms the old one


class RevokedOut(BaseModel):
    revoked: int


class AuditEvent(BaseModel):
    at: str
    kind: str
    data: dict[str, Any]


class AuditOut(BaseModel):
    events: list[AuditEvent]  # newest first
    total: int


class ReasonCodeCount(BaseModel):
    code: str  # `<tool type>.<criterion>`
    count: int


class ReasonCodesOut(BaseModel):
    codes: list[ReasonCodeCount]


class DatasetImage(BaseModel):
    id: str
    result: str | None  # what the station said when it was collected; None: from a correction
    label: Literal["PASS", "FAIL"] | None  # what the person said it should be, when they corrected it
    source: Literal["collected", "corrected"]
    added_at: str


class DatasetImagesOut(BaseModel):
    total: int
    images: list[DatasetImage]


class DatasetJob(BaseModel):
    job_id: str
    name: str
    collecting: bool
    images: int


class DatasetOut(BaseModel):
    jobs: list[DatasetJob]
    total: int


class DatasetExportBody(BaseModel):
    job_id: str | None = None  # None: every job


class DatasetExportOut(BaseModel):
    dataset_id: str
    folder: str
    count: int
