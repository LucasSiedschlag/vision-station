"""A job as the files of one `.vjob`: the job definition, the camera profile and the rest."""

from collections.abc import Mapping
from dataclasses import dataclass, field

import yaml
from pydantic import ValidationError

from vision_station.core.calibration import CALIBRATION_FILE
from vision_station.core.jobfiles import JobFileError, parse_calibration
from vision_station.jobs import CameraProfile, Job, dump_job, dump_profile, parse_job
from vision_station.store.archive import MANIFEST, check_path
from vision_station.store.errors import FormatError
from vision_station.locators import LocatorError, check_job_locator
from vision_station.tools import ToolError, check_job_tools

JOB_FILE = "job.yaml"


@dataclass(frozen=True)
class JobBundle:
    job: Job
    profile: CameraProfile
    # camera/raw/*, models/*, reference/*, tests/*: kept as they are, by relative path
    extra: Mapping[str, bytes] = field(default_factory=dict)
    content_hash: str | None = None  # of the saved version it was loaded from (archive.content_hash); None for a draft

    def files(self) -> dict[str, bytes]:
        files = {
            JOB_FILE: dump_job(self.job).encode("utf-8"),
            self.job.acquisition.image.profile: dump_profile(self.profile).encode("utf-8"),
        }
        for name, data in self.extra.items():
            check_path(name)
            if name in files or name == MANIFEST:
                raise FormatError(f"extra file collides with a reserved name: {name}")
            files[name] = data
        return files


# A job holds data, never code (FR-PLT-12): files only in the folders of data a job has, and never one that could run.
DATA_FOLDERS = ("camera/", "reference/", "tests/", "locator/", "patterns/", "models/")
CODE_EXTENSIONS = frozenset({
    ".py", ".pyc", ".pyd", ".pyw", ".dll", ".so", ".dylib", ".exe", ".com", ".msi", ".bat", ".cmd", ".ps1", ".psm1", ".vbs", ".wsf",
    ".sh", ".bash", ".js", ".mjs", ".jar", ".class", ".php", ".pl", ".rb", ".lua", ".scr", ".lnk", ".cpl", ".reg", ".jsx", ".ts",
})


def check_data_only(files: Mapping[str, bytes], profile_path: str) -> None:
    """Refuse a job with a file that is not data: logic ships in the program, versioned per tool type (FR-PLT-12)."""
    for name in files:
        lower = name.lower()
        if lower == JOB_FILE or name == profile_path:
            continue
        extension = "." + lower.rsplit(".", 1)[-1] if "." in lower.rsplit("/", 1)[-1] else ""
        if extension in CODE_EXTENSIONS:
            raise FormatError(f"a job holds data, not code: {name} is refused")
        if not lower.startswith(DATA_FOLDERS):
            raise FormatError(f"a job holds data in its own folders ({', '.join(DATA_FOLDERS)}): {name} is refused")


def bundle_from_files(files: Mapping[str, bytes], check_tools: bool = True) -> JobBundle:
    """Validate the files of a job. Refuses what the software cannot run, instead of running it differently."""
    if JOB_FILE not in files:
        raise FormatError(f"{JOB_FILE} is missing")
    try:
        job = parse_job(files[JOB_FILE].decode("utf-8"))
    except (ValidationError, yaml.YAMLError, UnicodeDecodeError) as exc:
        raise FormatError(f"{JOB_FILE} is not valid: {exc}") from exc
    profile_path = check_path(job.acquisition.image.profile)
    if profile_path == JOB_FILE or profile_path not in files:
        raise FormatError(f"camera profile file is missing: {job.acquisition.image.profile}")
    calibration = job.acquisition.image.calibration
    if calibration is not None and (check_path(calibration) not in files or calibration in (JOB_FILE, profile_path)):
        raise FormatError(f"calibration file is missing: {calibration}")
    if (calibration is not None and calibration != CALIBRATION_FILE) or (calibration is None and CALIBRATION_FILE in files):
        # the tools read it by this name (JobFiles.scale), so the job's block must say the same
        raise FormatError(f"the calibration of a job is {CALIBRATION_FILE}, named in acquisition.image.calibration")
    if calibration is not None:
        try:
            parse_calibration(files[calibration])
        except JobFileError as exc:
            raise FormatError(f"calibration file is not valid: {exc}") from exc
    try:
        profile = CameraProfile.model_validate(yaml.safe_load(files[profile_path]))
    except (ValidationError, yaml.YAMLError) as exc:
        raise FormatError(f"{profile_path} is not valid: {exc}") from exc
    check_data_only(files, profile_path)
    if check_tools:
        try:
            check_job_locator(job, files)
            check_job_tools(job, files)
        except (ToolError, LocatorError) as exc:
            raise FormatError(f"job cannot run on this software: {exc}") from exc
    extra = {n: d for n, d in files.items() if n not in (JOB_FILE, profile_path)}
    return JobBundle(job=job, profile=profile, extra=extra)
