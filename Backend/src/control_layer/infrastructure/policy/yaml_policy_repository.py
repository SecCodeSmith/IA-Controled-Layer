from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Any

import yaml

from control_layer.domain.exceptions import PolicyValidationError
from control_layer.domain.models.policy import PolicyDocument
from control_layer.domain.policy.parser import parse_policy_document

logger = logging.getLogger(__name__)


class YamlPolicyRepository:
    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._lock = asyncio.Lock()
        self._document: PolicyDocument | None = None
        self._raw_yaml: str = ""
        self._status: str = "ERROR"
        self._error: str | None = None
        self._reload_count = 0
        self._load_sync()

    def _read_and_parse(self) -> tuple[PolicyDocument, str]:
        try:
            raw_yaml = self._path.read_text(encoding="utf-8")
        except OSError as exc:
            raise PolicyValidationError(f"cannot read policy file: {exc}") from exc
        try:
            data = yaml.safe_load(raw_yaml) or {}
        except yaml.YAMLError as exc:
            raise PolicyValidationError(f"invalid YAML: {exc}") from exc
        source_hash = hashlib.sha256(raw_yaml.encode("utf-8")).hexdigest()
        document = parse_policy_document(data, source_hash)
        return document, raw_yaml

    def _load_sync(self) -> None:
        try:
            document, raw_yaml = self._read_and_parse()
        except PolicyValidationError as exc:
            self._status = "ERROR"
            self._error = str(exc)
            logger.error("Policy load failed, keeping last good document: %s", exc)
            return
        self._reload_count += 1
        self._document = document
        self._raw_yaml = raw_yaml
        self._status = "LOADED"
        self._error = None

    async def current(self) -> PolicyDocument:
        async with self._lock:
            if self._document is None:
                raise PolicyValidationError(self._error or "policy not loaded")
            return self._document

    async def reload(self) -> PolicyDocument:
        async with self._lock:
            await asyncio.to_thread(self._load_sync)
            if self._document is None:
                raise PolicyValidationError(self._error or "policy not loaded")
            return self._document

    async def status(self) -> dict[str, Any]:
        async with self._lock:
            return {
                "version": self._document.version if self._document else None,
                "status": self._status,
                "loaded_at": self._document.loaded_at if self._document else None,
                "source": str(self._path),
                "error": self._error,
                "raw_yaml": self._raw_yaml,
                "reload_count": self._reload_count,
            }
