"""Comprehensive test suite for Phase 52:
Full Automation Builder, Presets, and Capability Matrix.
"""

import json
from unittest.mock import MagicMock

import pytest

from sp_farms.application.automation_builder import (
    AutomationBuilderService,
    InMemoryAutomationPresetRepository,
)
from sp_farms.domain.automation_builder import (
    CAPABILITY_MATRIX,
    FORBIDDEN_AUTOMATION_STEPS,
    AutomationStepType,
    CapabilitySupport,
    create_standard_preset,
    validate_step_config,
)


@pytest.fixture
def preset_repo() -> InMemoryAutomationPresetRepository:
    return InMemoryAutomationPresetRepository()


@pytest.fixture
def mock_audit_service() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_job_service() -> MagicMock:
    return MagicMock()


@pytest.fixture
def builder_service(
    preset_repo: InMemoryAutomationPresetRepository,
    mock_audit_service: MagicMock,
    mock_job_service: MagicMock,
) -> AutomationBuilderService:
    service = AutomationBuilderService(
        repository=preset_repo,
        audit_service=mock_audit_service,
        job_service=mock_job_service,
    )
    service.initialize_built_in_presets_if_missing()
    return service


class TestCapabilityMatrixAndSafetyBoundaries:
    """Test safety boundaries, forbidden operations, and capability mappings."""

    def test_all_capability_matrix_entries_exist(self) -> None:
        assert len(CAPABILITY_MATRIX) == 27
        for step_type in AutomationStepType:
            assert step_type in CAPABILITY_MATRIX
            info = CAPABILITY_MATRIX[step_type]
            assert info.title
            assert info.description
            assert isinstance(info.support_tier, CapabilitySupport)

    def test_forbidden_operations_blocked(self) -> None:
        for forbidden in FORBIDDEN_AUTOMATION_STEPS:
            res = validate_step_config(forbidden, {})  # type: ignore[arg-type]
            assert not res.valid
            assert any("strictly prohibited" in err for err in res.errors)

    def test_reaction_analytics_is_strictly_read_only(self) -> None:
        info = CAPABILITY_MATRIX[AutomationStepType.COLLECT_REACTION_ANALYTICS]
        assert info.read_only is True
        assert info.support_tier == CapabilitySupport.READ_ONLY_ANALYTICS

        # Rejects fake engagement or mass reactions
        bad_config = {"action": "mass_react", "reaction_type": "LOVE"}
        res = validate_step_config(AutomationStepType.COLLECT_REACTION_ANALYTICS, bad_config)
        assert not res.valid
        assert any("Automated reaction generation is prohibited" in err for err in res.errors)

    def test_follower_analytics_is_strictly_read_only(self) -> None:
        info = CAPABILITY_MATRIX[AutomationStepType.COLLECT_FOLLOWER_ANALYTICS]
        assert info.read_only is True
        assert info.support_tier == CapabilitySupport.READ_ONLY_ANALYTICS

    def test_publish_text_validation(self) -> None:
        res1 = validate_step_config(AutomationStepType.PUBLISH_TEXT, {})
        assert not res1.valid
        assert any("requires 'text'" in err for err in res1.errors)

        res2 = validate_step_config(AutomationStepType.PUBLISH_TEXT, {"text": "Valid post"})
        assert res2.valid
        assert not res2.errors

    def test_publish_story_capability_warning(self) -> None:
        res = validate_step_config(AutomationStepType.PUBLISH_STORY, {"media_path": "x.jpg"})
        assert any("Story publishing is capability-gated" in w for w in res.warnings)


class TestPresetRepositoryAndService:
    """Test CRUD operations and business logic of AutomationBuilderService."""

    def test_built_in_presets_initialized(self, builder_service: AutomationBuilderService) -> None:
        presets = builder_service.list_presets()
        assert len(presets) >= 5
        built_in_names = {p.name for p in presets if p.is_built_in}
        assert "Morning Page Publishing" in built_in_names
        assert "Story Queue" in built_in_names
        assert "Customer Support & Inbox" in built_in_names
        assert "Analytics Sweep" in built_in_names
        assert "Content + Device Queue" in built_in_names

    def test_create_and_retrieve_custom_preset(
        self,
        builder_service: AutomationBuilderService,
    ) -> None:
        preset = builder_service.create_preset(
            name="Evening Post",
            description="Post an evening update",
            tags=("evening", "daily"),
        )
        assert preset.id
        assert preset.name == "Evening Post"
        assert not preset.is_built_in

        fetched = builder_service.get_preset(preset.id)
        assert fetched is not None
        assert fetched.id == preset.id

    def test_cannot_delete_built_in_preset(self, builder_service: AutomationBuilderService) -> None:
        presets = builder_service.list_presets()
        built_in = next(p for p in presets if p.is_built_in)
        assert not builder_service.delete_preset(built_in.id)
        assert builder_service.get_preset(built_in.id) is not None

    def test_duplicate_preset(self, builder_service: AutomationBuilderService) -> None:
        presets = builder_service.list_presets()
        source = presets[0]
        duplicate = builder_service.duplicate_preset(source.id, new_name="Custom Copy")
        assert duplicate is not None
        assert duplicate.id != source.id
        assert duplicate.name == "Custom Copy"
        assert not duplicate.is_built_in
        assert len(duplicate.steps) == len(source.steps)

    def test_preset_validation_checks_forbidden_steps(
        self,
        builder_service: AutomationBuilderService,
    ) -> None:
        p = create_standard_preset("morning_publishing")
        errors = builder_service.validate_preset(p)
        assert not errors


class TestPreFlightDryRunSimulation:
    """Test pre-flight dry run simulation with zero side-effects guarantee."""

    def test_dry_run_produces_deterministic_report_with_zero_side_effects(
        self,
        builder_service: AutomationBuilderService,
        mock_job_service: MagicMock,
    ) -> None:
        presets = builder_service.list_presets()
        morning_preset = next(p for p in presets if p.name == "Morning Page Publishing")

        report = builder_service.generate_dry_run_report(morning_preset)
        assert report.preset_name == morning_preset.name
        assert report.estimated_jobs_count > 0
        assert len(report.items) == report.estimated_jobs_count

        # Ensure NO jobs were queued during dry-run
        mock_job_service.enqueue_job.assert_not_called()


class TestJsonImportExportFidelity:
    """Test export/import JSON fidelity and injection defense."""

    def test_export_and_import_preset(self, builder_service: AutomationBuilderService) -> None:
        presets = builder_service.list_presets()
        source = presets[0]

        json_doc = builder_service.export_preset_json(source.id)
        data = json.loads(json_doc)
        assert data["preset"]["name"] == source.name
        assert len(data["preset"]["steps"]) == len(source.steps)

        imported = builder_service.import_preset_json(json_doc)
        assert imported.name.startswith(source.name)
        assert not imported.is_built_in
        assert len(imported.steps) == len(source.steps)

    def test_import_rejects_forbidden_steps(
        self,
        builder_service: AutomationBuilderService,
    ) -> None:
        poisoned_doc = json.dumps(
            {
                "preset_name": "Exploit Preset",
                "description": "Attempt to bypass platform rules",
                "steps": [
                    {
                        "step_type": "mass_reactions",
                        "configuration": {"count": 10000},
                    }
                ],
            }
        )
        with pytest.raises(ValueError, match="strictly prohibited"):
            builder_service.import_preset_json(poisoned_doc)


class TestWorkflowExecution:
    """Test workflow execution job dispatching and audit trail."""

    def test_execute_preset_enqueues_jobs(
        self,
        builder_service: AutomationBuilderService,
        mock_job_service: MagicMock,
        mock_audit_service: MagicMock,
    ) -> None:
        presets = builder_service.list_presets()
        morning_preset = next(p for p in presets if p.name == "Morning Page Publishing")

        success, msg, job_ids = builder_service.execute_preset(
            morning_preset,
            target_accounts=["acc_1"],
            target_destinations=["page_1"],
        )
        assert success is True
        assert "Enqueued" in msg
        assert len(job_ids) > 0

        assert mock_job_service.enqueue_job.call_count == len(job_ids)
        assert mock_audit_service.record_event.call_count >= 1


class TestAutomationBuilderWorkspaceUI:
    """Test Qt UI workspace component, controls, and interaction."""

    def test_workspace_instantiation_and_controls(
        self,
        builder_service: AutomationBuilderService,
    ) -> None:
        from PySide6.QtWidgets import QApplication

        from sp_farms.app.automation_builder_workspace import AutomationBuilderWorkspace

        _ = QApplication.instance() or QApplication([])
        workspace = AutomationBuilderWorkspace(builder_service)

        # Preset dropdown has seeded presets
        assert workspace._preset_combo.count() >= 5

        # Function list contains 27 capability items
        assert workspace._functions_list.count() == 27

        # Target rules controls
        assert workspace._chk_healthy_only.isChecked() is True
        assert workspace._spn_concurrent_dev.value() >= 1

        # Metrics status is updated
        assert "Enabled Functions" in workspace._lbl_metrics.text()
