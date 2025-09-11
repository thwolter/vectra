class RlsNotEnforcedError(Exception):
    """Raised when the connected database role bypasses RLS or row_security is off."""

    pass
