"""
Module discovery utilities for the WindowsNotifier runtime.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Tuple

from shared.manifest_schema import (
    ManifestValidationError,
    load_and_validate_manifest,
    parse_iso8601_utc,
)
from shared.module_definition import ModuleDefinition
from core.module_id import compute_module_id
from core.registry_store import ConditionState, ModuleStatus, RegistryStore

DEFAULT_SCAN_INTERVAL_SECONDS = 300

@dataclass(slots=True)
class LoadResult:
    modules: List[ModuleDefinition]
    errors: List[Tuple[Path, Exception]]


def scan_modules(
    modules_dir: Path,
    *,
    registry: RegistryStore | None = None,
    now: datetime | None = None,
    scan_interval_seconds: int = DEFAULT_SCAN_INTERVAL_SECONDS,
) -> LoadResult:
    """
    Inspect module subdirectories, validate manifests, resolve identities, and
    filter according to registry state.
    """
    registry = registry or RegistryStore()
    modules: List[ModuleDefinition] = []
    errors: List[Tuple[Path, Exception]] = []
    current_time = now or datetime.now(timezone.utc)

    try:
        subdirs = [p for p in modules_dir.iterdir() if p.is_dir()]
    except FileNotFoundError:
        return LoadResult(modules=[], errors=[])

    for module_path in sorted(subdirs):
        manifest_path = module_path / "manifest.json"
        if not manifest_path.exists():
            errors.append((module_path, FileNotFoundError(f"Missing manifest.json in {module_path}")))
            continue

        try:
            manifest = load_and_validate_manifest(manifest_path)
            module = ModuleDefinition(root=module_path, manifest=manifest)
            key = module.module_key or module_path.name
            new_hash = compute_module_id(module)
            stored_hash = registry.get_module_hash(key)
            stored_schedule = registry.get_schedule(key)

            override_schedule = False
            if stored_schedule:
                try:
                    module.scheduled_utc = parse_iso8601_utc(stored_schedule)
                except ManifestValidationError:
                    override_schedule = True
            else:
                override_schedule = True

            if stored_hash != new_hash:
                registry.set_module_hash(key, new_hash)
                registry.mark_first_seen(key, title=module.title, category=module.category)
                if module.is_conditional:
                    registry.set_condition_state(key, ConditionState.WAITING)
                    registry.set_condition_next_run(key, current_time)
                else:
                    registry.clear_condition_tracking(key)
                status = ModuleStatus.PENDING
                override_schedule = True
            else:
                status = registry.get_status(key)

            if override_schedule:
                registry.set_schedule(key, module.scheduled_utc)
        except (ManifestValidationError, OSError, FileNotFoundError) as exc:
            errors.append((module_path, exc))
            continue

        try:
            if status in {ModuleStatus.COMPLETED, ModuleStatus.EXPIRED}:
                _safe_delete_folder(module_path)
                continue

            if module.is_expired(reference=current_time):
                registry.mark_expired(key)
                _safe_delete_folder(module_path)
                continue

            if status is None:
                registry.mark_first_seen(key, title=module.title, category=module.category)

            if module.is_conditional:
                ready = _handle_condition_module(
                    module=module,
                    key=key,
                    registry=registry,
                    module_path=module_path,
                    current_time=current_time,
                    scan_interval_seconds=scan_interval_seconds,
                    errors=errors,
                )
                if not ready:
                    continue

            modules.append(module)
        except OSError as exc:
            errors.append((module_path, exc))

    return LoadResult(modules=modules, errors=errors)


def _safe_delete_folder(path: Path) -> None:
    """Attempt to delete a module folder, ignoring missing-directory errors."""
    try:
        for child in path.iterdir():
            if child.is_dir():
                _safe_delete_folder(child)
            else:
                child.unlink(missing_ok=True)
        path.rmdir()
    except FileNotFoundError:
        pass


def _handle_condition_module(
    *,
    module: ModuleDefinition,
    key: str,
    registry: RegistryStore,
    module_path: Path,
    current_time: datetime,
    scan_interval_seconds: int,
    errors: List[Tuple[Path, Exception]] | None = None,
) -> bool:
    if not module.condition_script_path or not module.condition_script_path.exists():
        message = "Condition script missing."
        registry.set_condition_error(key, message)
        if errors is not None:
            errors.append((module_path, RuntimeError(message)))
        _safe_delete_folder(module_path)
        return False

    state = registry.get_condition_state(key)
    if state == ConditionState.ERROR:
        _safe_delete_folder(module_path)
        return False
    if state == ConditionState.TRIGGERED:
        return True

    next_run = registry.get_condition_next_run(key)
    if next_run and next_run > current_time:
        return False

    timeout = max(5, min(module.condition_interval_minutes * 60, scan_interval_seconds) - 5)

    result = _run_condition_script(module.condition_script_path, timeout, module_path)
    if result is None:
        message = "Condition script failed to execute."
        registry.set_condition_error(key, message)
        if errors is not None:
            errors.append((module_path, RuntimeError(message)))
        _safe_delete_folder(module_path)
        return False

    exit_code, stdout, stderr = result

    if exit_code == 1:
        registry.set_condition_state(key, ConditionState.TRIGGERED)
        return True

    if exit_code == 0:
        registry.set_condition_state(key, ConditionState.WAITING)
        next_check = current_time + timedelta(minutes=module.condition_interval_minutes)
        registry.set_condition_next_run(key, next_check)
        return False

    message = f"Condition script exited with code {exit_code}. Stdout: {stdout[-200:]}, Stderr: {stderr[-200:]}."
    registry.set_condition_error(key, message)
    if errors is not None:
        errors.append((module_path, RuntimeError(message)))
    _safe_delete_folder(module_path)
    return False


def _run_condition_script(script: Path, timeout: int, module_path: Path) -> Tuple[int, str, str] | None:
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(module_path),
        )
        return completed.returncode, completed.stdout.strip(), completed.stderr.strip()
    except (OSError, subprocess.SubprocessError):
        return None
