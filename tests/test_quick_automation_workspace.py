import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton

from sp_farms.app.quick_automation_workspace import QuickAutomationWorkspace
from sp_farms.application.automation_builder import (
    AutomationBuilderService,
    InMemoryAutomationPresetRepository,
)


def application() -> QApplication:
    current = QApplication.instance()
    if isinstance(current, QApplication):
        return current
    return QApplication([])


def test_quick_mode_has_five_step_flow() -> None:
    application()
    service = AutomationBuilderService(InMemoryAutomationPresetRepository())
    view = QuickAutomationWorkspace(service)
    view.show()
    QApplication.processEvents()

    assert view.preset_combo.count() >= 5
    flow_buttons = [
        button
        for button in view.findChildren(QPushButton)
        if button.property("flowStep") is True
    ]
    assert len(flow_buttons) == 5
    assert view.steps.count() >= 1
    assert not view.grab().toImage().isNull()
    view.close()


def test_manual_targets_enable_fields() -> None:
    application()
    service = AutomationBuilderService(InMemoryAutomationPresetRepository())
    view = QuickAutomationWorkspace(service)

    view.use_preset_targets.setChecked(False)

    assert view.account_ids.isEnabled()
    assert view.destination_ids.isEnabled()
    view.close()
