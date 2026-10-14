class StoreError(Exception):
    """Base of every error about job files, backups and the job store."""


class FormatError(StoreError):
    """The file is not a job or backup file this software can read."""


class IntegrityError(StoreError):
    """A file is damaged: a checksum does not match, or an entry is missing or unexpected."""
