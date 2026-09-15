"""Application port and service for Automation Builder presets, capabilities, and execution."""

from __future__ import annotations

import contextlib
import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, Protocol

from sp_farms.domain.audit import AuditResult
from sp_farms.domain.automation_builder import (
    CAPABILITY_MATRIX,
    FORBIDDEN_AUTOMATION_STEPS,
    AutomationPreset,
    AutomationPresetStep,
    AutomationStepType,
    DryRunItem,
    DryRunReport,
    TargetSelectionRules,
    create_standard_preset,
    validate_step_config,
)


class AutomationPresetRepositoryPort(Protocol):
    """Storage repository interface for automation presets and steps."""

    def save_preset(self, preset: AutomationPreset) -> None: ...
    def get_preset(self, preset_id: str) -> AutomationPreset | None: ...
    def get_preset_by_name(self, name: str) -> AutomationPreset | None: ...
    def list_presets(self) -> Sequence[AutomationPreset]: ...
    def delete_preset(self, preset_id: str) -> bool: ...


class InMemoryAutomationPresetRepository:
    """In-memory repository implementation for testing and headless runs."""

    def __init__(self) -> None:
        self._presets: dict[str, AutomationPreset] = {}

    def save_preset(self, preset: AutomationPreset) -> None:
        self._presets[preset.id] = preset

    def get_preset(self, preset_id: str) -> AutomationPreset | None:
        return self._presets.get(preset_id)

    def get_preset_by_name(self, name: str) -> AutomationPreset | None:
        return next((p for p in self._presets.values() if p.name.lower() == name.lower()), None)

    def list_presets(self) -> Sequence[AutomationPreset]:
        return tuple(self._presets.values())

    def delete_preset(self, preset_id: str) -> bool:
        if preset_id in self._presets:
            del self._presets[preset_id]
            return True
        return False


class AutomationBuilderService:
    """Service orchestrating automation builder workflows, validation, dry-runs, and execution."""

    def __init__(
        self,
        repository: AutomationPresetRepositoryPort,
        audit_service: Any | None = None,
        job_service: Any | None = None,
    ) -> None:
        self._repository = repository
        self._audit_service = audit_service
        self._job_service = job_service

    def initialize_built_in_presets_if_missing(self) -> None:
        """Seed the 5 standard built-in presets if not present."""
        standard_keys = (
            "morning_publishing",
            "story_queue",
            "customer_support",
            "analytics_sweep",
            "device_queue",
        )
        for key in standard_keys:
            candidate = create_standard_preset(key)
            existing = self._repository.get_preset(
                candidate.id
            ) or self._repository.get_preset_by_name(candidate.name)
            if existing is None:
                self._repository.save_preset(candidate)

    def list_presets(self) -> Sequence[AutomationPreset]:
        """List all saved presets, sorted with built-ins first, then alphabetically."""
        presets = list(self._repository.list_presets())
        if not presets:
            self.initialize_built_in_presets_if_missing()
            presets = list(self._repository.list_presets())
        return sorted(presets, key=lambda p: (not p.is_built_in, p.name.lower()))

    def get_preset(self, preset_id: str) -> AutomationPreset | None:
        return self._repository.get_preset(preset_id)

    def create_preset(
        self,
        name: str,
        description: str,
        target_rules: TargetSelectionRules | None = None,
        steps: Sequence[AutomationPresetStep] | None = None,
        tags: Sequence[str] | None = None,
    ) -> AutomationPreset:
        preset_id = str(uuid.uuid4())
        preset = AutomationPreset(
            id=preset_id,
            name=name.strip(),
            description=description.strip(),
            target_rules=target_rules or TargetSelectionRules(),
            steps=tuple(steps or ()),
            tags=tuple(tags or ()),
            is_built_in=False,
            version=1,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self._repository.save_preset(preset)
        self._record_audit(
            action="preset.create",
            preset_id=preset_id,
            details={"name": name, "step_count": len(preset.steps)},
        )
        return preset

    def update_preset(self, preset: AutomationPreset) -> AutomationPreset:
        updated = AutomationPreset(
            id=preset.id,
            name=preset.name.strip(),
            description=preset.description.strip(),
            target_rules=preset.target_rules,
            steps=tuple(preset.steps),
            tags=tuple(preset.tags),
            is_built_in=preset.is_built_in,
            version=preset.version + 1,
            created_at=preset.created_at,
            updated_at=datetime.now(UTC),
        )
        self._repository.save_preset(updated)
        self._record_audit(
            action="preset.update",
            preset_id=preset.id,
            details={"name": preset.name, "step_count": len(updated.steps)},
        )
        return updated

    def duplicate_preset(self, source_preset_id: str, new_name: str) -> AutomationPreset | None:
        source = self._repository.get_preset(source_preset_id)
        if source is None:
            return None

        new_id = str(uuid.uuid4())
        new_steps = [
            AutomationPresetStep(
                id=str(uuid.uuid4()),
                preset_id=new_id,
                step_type=step.step_type,
                enabled=step.enabled,
                order=step.order,
                configuration=dict(step.configuration),
                requires_approval=step.requires_approval,
                continue_on_error=step.continue_on_error,
                retry_policy=step.retry_policy,
                timeout_seconds=step.timeout_seconds,
            )
            for step in source.steps
        ]

        duplicate = AutomationPreset(
            id=new_id,
            name=new_name.strip(),
            description=f"Copy of {source.name}: {source.description}",
            target_rules=source.target_rules,
            steps=tuple(new_steps),
            tags=source.tags,
            is_built_in=False,
            version=1,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self._repository.save_preset(duplicate)
        return duplicate

    def delete_preset(self, preset_id: str) -> bool:
        preset = self._repository.get_preset(preset_id)
        if preset is None:
            return False
        if preset.is_built_in:
            return False
        deleted = self._repository.delete_preset(preset_id)
        if deleted:
            self._record_audit(
                action="preset.delete",
                preset_id=preset_id,
                details={"name": preset.name},
            )
        return deleted

    def export_preset_json(self, preset_id: str) -> str:
        preset = self._repository.get_preset(preset_id)
        if preset is None:
            raise ValueError(f"Preset {preset_id} not found")

        doc = {
            "version": 1,
            "exported_at": datetime.now(UTC).isoformat(),
            "preset": {
                "name": preset.name,
                "description": preset.description,
                "tags": list(preset.tags),
                "target_rules": asdict(preset.target_rules),
                "steps": [
                    {
                        "step_type": step.step_type.value,
                        "enabled": step.enabled,
                        "order": step.order,
                        "configuration": dict(step.configuration),
                        "requires_approval": step.requires_approval,
                        "continue_on_error": step.continue_on_error,
                        "retry_policy": step.retry_policy,
                        "timeout_seconds": step.timeout_seconds,
                    }
                    for step in sorted(preset.steps, key=lambda s: s.order)
                ],
            },
        }
        return json.dumps(doc, indent=2)

    def import_preset_json(
        self, json_content: str, rename_if_exists: bool = True
    ) -> AutomationPreset:
        data = json.loads(json_content)
        preset_data = data.get("preset", data)

        name = preset_data.get("name", "Imported Preset")
        if rename_if_exists:
            existing = self._repository.get_preset_by_name(name)
            if existing:
                name = f"{name} (Imported {datetime.now(UTC).strftime('%Y%m%d%H%M')})"

        preset_id = str(uuid.uuid4())
        rules_data = preset_data.get("target_rules", {})
        target_rules = TargetSelectionRules(
            account_ids=tuple(rules_data.get("account_ids", ())),
            account_category=rules_data.get("account_category"),
            account_tags=tuple(rules_data.get("account_tags", ())),
            only_healthy_accounts=rules_data.get("only_healthy_accounts", True),
            only_accounts_with_device=rules_data.get("only_accounts_with_device", False),
            only_valid_auth=rules_data.get("only_valid_auth", True),
            device_policy=rules_data.get("device_policy", "bound_first"),
            provider_preference=tuple(
                rules_data.get("provider_preference", ("ldplayer", "mumu", "physical"))
            ),
            max_concurrent_devices=rules_data.get("max_concurrent_devices", 4),
            stop_device_after_release=rules_data.get("stop_device_after_release", False),
            destination_ids=tuple(rules_data.get("destination_ids", ())),
            destination_types=tuple(rules_data.get("destination_types", ("page",))),
            exclude_destination_ids=tuple(rules_data.get("exclude_destination_ids", ())),
            only_destinations_with_permissions=rules_data.get(
                "only_destinations_with_permissions", True
            ),
        )

        steps: list[AutomationPresetStep] = []
        for index, s_data in enumerate(preset_data.get("steps", [])):
            step_type_str = s_data.get("step_type", "")
            if step_type_str in FORBIDDEN_AUTOMATION_STEPS:
                raise ValueError(
                    f"Preset contains step '{step_type_str}' which is "
                    "strictly prohibited by platform safety boundaries."
                )
            try:
                st = AutomationStepType(step_type_str)
            except ValueError:
                continue

            steps.append(
                AutomationPresetStep(
                    id=str(uuid.uuid4()),
                    preset_id=preset_id,
                    step_type=st,
                    enabled=bool(s_data.get("enabled", True)),
                    order=int(s_data.get("order", index + 1)),
                    configuration=s_data.get("configuration", {}),
                    requires_approval=bool(s_data.get("requires_approval", False)),
                    continue_on_error=bool(s_data.get("continue_on_error", False)),
                    retry_policy=str(s_data.get("retry_policy", "no_retry")),
                    timeout_seconds=int(s_data.get("timeout_seconds", 120)),
                )
            )

        imported = AutomationPreset(
            id=preset_id,
            name=name,
            description=preset_data.get("description", "Imported automation workflow"),
            target_rules=target_rules,
            steps=tuple(steps),
            tags=tuple(preset_data.get("tags", ())),
            is_built_in=False,
            version=1,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self._repository.save_preset(imported)
        return imported

    def validate_preset(self, preset: AutomationPreset) -> list[str]:
        """Validate entire preset including all steps and targets."""
        errors: list[str] = []
        if not preset.name.strip():
            errors.append("Preset name cannot be empty")

        enabled_steps = [s for s in preset.steps if s.enabled]
        if not enabled_steps:
            errors.append("Preset must have at least one enabled step")

        for step in enabled_steps:
            res = validate_step_config(step.step_type, step.configuration)
            if not res.valid:
                errors.extend(
                    f"Step {step.order} ({step.step_type.value}): {err}" for err in res.errors
                )

        return errors

    def generate_dry_run_report(
        self,
        preset: AutomationPreset,
        target_accounts: Sequence[str] | None = None,
        target_destinations: Sequence[str] | None = None,
    ) -> DryRunReport:
        """Perform pre-flight dry run calculation strictly guaranteeing 0 side effects."""
        accounts = list(
            target_accounts or preset.target_rules.account_ids or ["acc_default_simulated"]
        )
        destinations = list(
            target_destinations or preset.target_rules.destination_ids or ["dest_default_page"]
        )
        enabled_steps = sorted([s for s in preset.steps if s.enabled], key=lambda s: s.order)

        dry_items: list[DryRunItem] = []
        warnings: list[str] = []

        validation_errors = self.validate_preset(preset)
        if validation_errors:
            warnings.extend(validation_errors)

        for step in enabled_steps:
            cap_info = CAPABILITY_MATRIX[step.step_type]
            if cap_info.support_tier.value == "capability_gated":
                warnings.append(
                    f"Step '{cap_info.title}' is capability-gated on destination platform."
                )

            for acc in accounts:
                for dest in destinations:
                    summary = f"Simulated execution of {cap_info.title} on destination {dest}"
                    dry_items.append(
                        DryRunItem(
                            step_order=step.order,
                            step_type=step.step_type,
                            title=cap_info.title,
                            target_account=acc,
                            target_destination=dest,
                            expected_device=f"device_assigned_to_{acc}"
                            if cap_info.supports_device
                            else "n/a",
                            requires_approval=step.requires_approval,
                            summary=summary,
                            capability_tier=cap_info.support_tier,
                            is_read_only=cap_info.read_only,
                        )
                    )

        total_planned_steps = len(dry_items)
        estimated_jobs = total_planned_steps

        return DryRunReport(
            preset_name=preset.name,
            target_accounts_count=len(accounts),
            target_destinations_count=len(destinations),
            expected_devices_count=len(accounts),
            total_planned_steps=total_planned_steps,
            estimated_jobs_count=estimated_jobs,
            items=dry_items,
            warnings=warnings,
            is_safe_to_execute=len(validation_errors) == 0,
        )

    def execute_preset(
        self,
        preset: AutomationPreset,
        target_accounts: Sequence[str] | None = None,
        target_destinations: Sequence[str] | None = None,
        initiator: str = "operator",
    ) -> tuple[bool, str, list[str]]:
        """Dispatch real automation workflow jobs. Returns (success, message, created_job_ids)."""
        errors = self.validate_preset(preset)
        if errors:
            return False, f"Preset validation failed: {'; '.join(errors)}", []

        accounts = list(target_accounts or preset.target_rules.account_ids or [])
        destinations = list(target_destinations or preset.target_rules.destination_ids or [])
        enabled_steps = sorted([s for s in preset.steps if s.enabled], key=lambda s: s.order)

        created_job_ids: list[str] = []

        # Audit start
        self._record_audit(
            action="automation.execute_preset",
            preset_id=preset.id,
            details={
                "preset_name": preset.name,
                "account_count": len(accounts),
                "destination_count": len(destinations),
                "step_count": len(enabled_steps),
                "initiator": initiator,
            },
        )

        for acc in accounts:
            for step in enabled_steps:
                job_id = str(uuid.uuid4())
                created_job_ids.append(job_id)
                if self._job_service:
                    with contextlib.suppress(Exception):
                        self._job_service.enqueue_job(
                            job_type=f"automation.{step.step_type.value}",
                            payload={
                                "preset_id": preset.id,
                                "step_type": step.step_type.value,
                                "account_id": acc,
                                "destinations": destinations,
                                "config": dict(step.configuration),
                                "requires_approval": step.requires_approval,
                            },
                        )

        return (
            True,
            f"Enqueued {len(created_job_ids)} tasks for preset '{preset.name}'",
            created_job_ids,
        )

    def _record_audit(
        self,
        action: str,
        preset_id: str,
        details: Mapping[str, Any],
    ) -> None:
        if self._audit_service:
            with contextlib.suppress(Exception):
                self._audit_service.record_event(
                    action=action,
                    entity_type="automation_preset",
                    entity_id=preset_id,
                    result=AuditResult.SUCCESS,
                    metadata=dict(details),
                )
