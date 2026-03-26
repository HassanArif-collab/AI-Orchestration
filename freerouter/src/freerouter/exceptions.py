"""
exceptions.py — FreeRouter exception classes.

Context: Defines exceptions used across FreeRouter modules.
Kept in a separate file to avoid circular imports between router.py and adapters.

Imported by: router.py, adapters/apifreellm.py, proxy_server.py
"""


class RouterError(Exception):
    """Raised when a provider request fails and fallback is needed."""
    pass
