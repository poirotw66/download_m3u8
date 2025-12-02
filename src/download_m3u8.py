"""Backwards compatibility shim for legacy imports.

The new implementation lives inside the `download_m3u8` package. This module
keeps older scripts working while the codebase transitions to the package form.
"""

from download_m3u8 import (  # noqa: F401
    clear_seleniumwire_cache,
    download_aac_from_m3u8,
    download_from_csv,
    get_m3u8_url,
    increase_file_limit,
    process_csv,
)

__all__ = [
    "clear_seleniumwire_cache",
    "download_aac_from_m3u8",
    "download_from_csv",
    "get_m3u8_url",
    "increase_file_limit",
    "process_csv",
]

