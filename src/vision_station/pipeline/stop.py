"""The signal that an inspection cannot go on (FR-INS-6)."""

from vision_station.core.errors import CATALOG, ErrorCode


class Stop(Exception):
    """The inspection cannot go on; carries the error code and the ERROR text for the operator."""

    def __init__(self, code: ErrorCode, reason: str | None = None):
        super().__init__(reason if reason is not None else CATALOG[code].text)
        self.code = code
