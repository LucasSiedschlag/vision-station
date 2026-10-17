"""The signal that an inspection cannot go on (FR-INS-6)."""


class Stop(Exception):
    """The inspection cannot go on; carries the ERROR text for the operator."""
