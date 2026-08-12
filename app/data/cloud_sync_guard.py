"""Cloud-sync folder detection (PROJECT_SPEC.md section 44).

If the folder financial data gets saved into looks like it lives inside a
cloud-sync client (OneDrive/Dropbox/Google Drive/iCloud), warn about it.
Never move anything automatically — just tell the user, every time this is
checked, so it can't be dismissed once and forgotten while still applying.
"""
from __future__ import annotations

from pathlib import Path

CLOUD_SYNC_MARKERS = ["onedrive", "dropbox", "google drive", "googledrive", "icloud drive", "icloud"]


def detect_cloud_sync_marker(path: Path) -> str | None:
    """Returns the matched marker substring if `path` appears to live
    inside a cloud-sync folder, else None."""
    lowered = str(path).lower()
    for marker in CLOUD_SYNC_MARKERS:
        if marker in lowered:
            return marker
    return None
