from __future__ import annotations

import glob
import posixpath
import re
from functools import lru_cache

from control_layer.domain.models.resource import PathDecision, PathScope

_DRIVE_RE = re.compile(r"^[A-Za-z]:")
_TRAVERSAL_REASON = "absolute or traversal path"


@lru_cache(maxsize=256)
def _compile(pattern: str) -> re.Pattern[str]:
    return re.compile(
        glob.translate(pattern, recursive=True, include_hidden=True, seps="/"), re.IGNORECASE
    )


def _is_absolute_or_traversal(path: str) -> bool:
    return (
        path.startswith("/")
        or _DRIVE_RE.match(path) is not None
        or ".." in path.split("/")
    )


def _first_match(candidate: str, patterns: list[str]) -> str | None:
    return next((p for p in patterns if _compile(p).match(candidate)), None)


def path_allowed(path: str, scope: PathScope) -> PathDecision:
    slashed = path.replace("\\", "/")
    if _is_absolute_or_traversal(slashed):
        return PathDecision(allowed=False, path=path, reason=_TRAVERSAL_REASON)

    candidate = posixpath.normpath(slashed)
    denied_by = _first_match(candidate, scope.deny)
    if denied_by is not None:
        return PathDecision(
            allowed=False, path=path, pattern=denied_by, reason=f"denied by pattern {denied_by}"
        )
    if scope.allow and _first_match(candidate, scope.allow) is None:
        return PathDecision(allowed=False, path=path, reason="not in allow list")
    return PathDecision(allowed=True, path=path, reason="allowed")
