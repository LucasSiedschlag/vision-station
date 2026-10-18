"""The signal that an inspection cannot go on (FR-INS-6)."""

from vision_station.core.errors import CATALOG, ErrorCode


class Stop(Exception):
    """The inspection cannot go on; carries the error code and the ERROR text for the operator."""

    def __init__(self, code: ErrorCode, reason: str | None = None):
        self.text = CATALOG[code].text if reason is None else reason  # a Msg when it is meant for translation (TD-30)
        super().__init__(self.text)
        self.code = code
