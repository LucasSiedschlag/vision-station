"""A job as the files of one `.vjob`: the job definition, the camera profile and the rest."""

from collections.abc import Mapping
from dataclasses import dataclass, field

import yaml
from pydantic import ValidationError

from vision_station.jobs import CameraProfile, Job, dump_job, parse_job
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

    def files(self) -> dict[str, bytes]:
        files = {
            JOB_FILE: dump_job(self.job).encode("utf-8"),
            self.job.camera_profile: yaml.safe_dump(self.profile.model_dump(mode="json"), sort_keys=False).encode("utf-8"),
        }
        for name, data in self.extra.items():
            check_path(name)
            if name in files or name == MANIFEST:
                raise FormatError(f"extra file collides with a reserved name: {name}")
            files[name] = data
        return files


def bundle_from_files(files: Mapping[str, bytes], check_tools: bool = True) -> JobBundle:
    """Validate the files of a job. Refuses what the software cannot run, instead of running it differently."""
    if JOB_FILE not in files:
        raise FormatError(f"{JOB_FILE} is missing")
    try:
        job = parse_job(files[JOB_FILE].decode("utf-8"))
    except (ValidationError, yaml.YAMLError, UnicodeDecodeError) as exc:
        raise FormatError(f"{JOB_FILE} is not valid: {exc}") from exc
    profile_path = check_path(job.camera_profile)
    if profile_path == JOB_FILE or profile_path not in files:
        raise FormatError(f"camera profile file is missing: {job.camera_profile}")
    try:
        profile = CameraProfile.model_validate(yaml.safe_load(files[profile_path]))
    except (ValidationError, yaml.YAMLError) as exc:
        raise FormatError(f"{profile_path} is not valid: {exc}") from exc
    if check_tools:
        try:
            check_job_locator(job, files)
            check_job_tools(job, files)
        except (ToolError, LocatorError) as exc:
            raise FormatError(f"job cannot run on this software: {exc}") from exc
    extra = {n: d for n, d in files.items() if n not in (JOB_FILE, profile_path)}
    return JobBundle(job=job, profile=profile, extra=extra)
