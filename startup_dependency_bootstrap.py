"""Stdlib-only startup dependency verification and optional installation."""
from __future__ import annotations

import importlib.metadata
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RequirementStatus:
    """Result for one requirement entry."""

    requirement: str
    installed: bool
    error: str | None = None


@dataclass(frozen=True)
class DependencyBootstrapReport:
    """Summary returned by dependency bootstrap."""

    requirements_file: Path
    checked: int
    missing: tuple[str, ...]
    installed: tuple[str, ...]
    failed: tuple[RequirementStatus, ...]
    install_enabled: bool

    @property
    def ok(self) -> bool:
        return not self.failed and (self.install_enabled or not self.missing)


def bootstrap_requirements(
    requirements_file: str | Path = "requirements.txt",
    *,
    install_enabled: bool | None = None,
    dry_run: bool = False,
) -> DependencyBootstrapReport:
    """Verify requirements and optionally install missing packages."""

    root = Path(requirements_file)
    if not root.is_absolute():
        root = Path.cwd() / root

    enabled = _resolve_install_enabled(install_enabled)
    requirements = tuple(_iter_requirements(root))
    statuses = tuple(_check_requirement(req) for req in requirements)
    missing = tuple(status.requirement for status in statuses if not status.installed)

    installed: list[str] = []
    failed: list[RequirementStatus] = []

    if missing and enabled and not dry_run:
        for requirement in missing:
            try:
                _install_requirement(requirement)
                installed.append(requirement)
            except Exception as exc:  # pragma: no cover - exercised through mocks
                logger.error("Requirement install failed for %s: %s", requirement, exc)
                failed.append(RequirementStatus(requirement, False, str(exc)))
    elif missing:
        logger.warning(
            "Missing requirements detected but startup installation is disabled: %s",
            ", ".join(missing),
        )

    return DependencyBootstrapReport(
        requirements_file=root,
        checked=len(requirements),
        missing=missing,
        installed=tuple(installed),
        failed=tuple(failed),
        install_enabled=enabled,
    )


def _resolve_install_enabled(install_enabled: bool | None) -> bool:
    if install_enabled is not None:
        return install_enabled

    env_value = os.getenv("AUTO_INSTALL_REQUIREMENTS_ON_STARTUP")
    if env_value is not None:
        return env_value.strip().lower() in {"1", "true", "yes", "on"}

    config_path = Path("config") / "app_config.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        return bool(config.get("auto_install_requirements_on_startup", True))
    except Exception:
        return True


def _iter_requirements(path: Path) -> Iterable[str]:
    if not path.exists():
        logger.warning("Requirements file not found: %s", path)
        return ()

    requirements: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        line = line.split("#", 1)[0].strip()
        if line:
            requirements.append(line)
    return requirements


def _check_requirement(requirement: str) -> RequirementStatus:
    package_name = _package_name(requirement)
    try:
        importlib.metadata.version(package_name)
        return RequirementStatus(requirement=requirement, installed=True)
    except importlib.metadata.PackageNotFoundError:
        return RequirementStatus(requirement=requirement, installed=False)


def _install_requirement(requirement: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "pip", "install", requirement],
        check=True,
        text=True,
    )


def _package_name(requirement: str) -> str:
    name = requirement.strip()
    for separator in ("==", ">=", "<=", "~=", "!=", ">", "<"):
        if separator in name:
            name = name.split(separator, 1)[0]
            break
    if "[" in name:
        name = name.split("[", 1)[0]
    return name.strip()
