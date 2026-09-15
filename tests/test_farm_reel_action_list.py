import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from sp_farms.app.farm_reel_action_list import (
    ACTION_GROUPS,
    FarmReelActionListWorkspace,
)
from sp_farms.application.automation_builder import (
    AutomationBuilderService,
    InMemoryAutomationPresetRepository,
)
from sp_farms.domain.automation_builder import AutomationStepType


def application() -> QApplication:
    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    return QApplication([])


def test_action_list_exposes_every_authorized_step_once() -> None:
    application()
    service = AutomationBuilderService(InMemoryAutomationPresetRepository())
    view = FarmReelActionListWorkspace(service)

    exposed = [step for _group, steps in ACTION_GROUPS for step in steps]

    assert len(exposed) == len(set(exposed))
    assert set(exposed) == set(AutomationStepType)
    assert len(view._tree_items) == len(AutomationStepType)
    view.close()


def test_common_flow_builds_valid_non_content_preset() -> None:
    application()
    service = AutomationBuilderService(InMemoryAutomationPresetRepository())
    view = FarmReelActionListWorkspace(service)

    view._select_common_flow()
    view.set_target_accounts(("account-1",))
    preset = view._build_preset()

    assert preset.target_rules.account_ids == ("account-1",)
    assert len(preset.steps) == 6
    assert service.validate_preset(preset) == []
    view.close()


def test_publish_text_requires_content() -> None:
    application()
    service = AutomationBuilderService(InMemoryAutomationPresetRepository())
    view = FarmReelActionListWorkspace(service)

    view._selected_steps = [AutomationStepType.PUBLISH_TEXT]
    preset = view._build_preset()
    errors = service.validate_preset(preset)

    assert any("Publish Text" in error for error in errors)
    view.close()
