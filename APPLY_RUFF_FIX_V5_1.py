from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
APP = ROOT / "sp_farms" / "app"


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"[OK] {label}: already fixed")
        return
    if old not in text:
        print(f"[WARN] {label}: exact block not found; skipped")
        return
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[FIX] {label}")


def main() -> None:
    if not APP.exists():
        raise SystemExit(
            "Run this script from the SP-Farms repository root "
            "(the folder containing sp_farms/)."
        )

    farm = APP / "farm_reel_action_list.py"
    main_window = APP / "main_window.py"
    quick = APP / "quick_automation_workspace.py"
    workspaces = APP / "workspaces.py"

    replace_once(
        farm,
        '''        self.delay.setToolTip(
            "Stored in the step configuration and applied by workers that support delayed execution."
        )
''',
        '''        self.delay.setToolTip(
            "Stored in the step configuration and applied by workers that "
            "support delayed execution."
        )
''',
        "farm_reel_action_list tooltip line length",
    )

    replace_once(
        farm,
        '''            self._add_check("launch_app", "Launch preferred app:", bool(cfg.get("launch_app", True)))
''',
        '''            self._add_check(
                "launch_app",
                "Launch preferred app:",
                bool(cfg.get("launch_app", True)),
            )
''',
        "farm_reel_action_list restore checkbox line length",
    )

    replace_once(
        farm,
        '''        verification = QLabel(
            "Verification/checkpoint: workflow pauses for operator action, then resumes after successful verification."
        )
''',
        '''        verification = QLabel(
            "Verification/checkpoint: workflow pauses for operator action, "
            "then resumes after successful verification."
        )
''',
        "farm_reel_action_list verification label line length",
    )

    replace_once(
        main_window,
        '''                    self.quick_automation_workspace.action_list_requested.connect(
                        lambda: automation_tabs.setCurrentWidget(
                            self.action_list_workspace
                        )
                        if self.action_list_workspace is not None
                        else None
                    )
''',
        '''                    self.quick_automation_workspace.action_list_requested.connect(
                        lambda tabs=automation_tabs: tabs.setCurrentWidget(
                            self.action_list_workspace
                        )
                        if self.action_list_workspace is not None
                        else None
                    )
''',
        "main_window bind Action List automation_tabs",
    )

    replace_once(
        main_window,
        '''                    self.quick_automation_workspace.advanced_requested.connect(
                        lambda: automation_tabs.setCurrentWidget(
                            self.automation_builder_workspace
                        )
                        if self.automation_builder_workspace is not None
                        else None
                    )
''',
        '''                    self.quick_automation_workspace.advanced_requested.connect(
                        lambda tabs=automation_tabs: tabs.setCurrentWidget(
                            self.automation_builder_workspace
                        )
                        if self.automation_builder_workspace is not None
                        else None
                    )
''',
        "main_window bind Advanced Builder automation_tabs",
    )

    replace_once(
        quick,
        '''        enabled = sorted((step for step in preset.steps if step.enabled), key=lambda step: step.order)
''',
        '''        enabled = sorted(
            (step for step in preset.steps if step.enabled),
            key=lambda step: step.order,
        )
''',
        "quick_automation_workspace sorted line length",
    )

    replace_once(
        workspaces,
        '''        self.start_all_btn.setEnabled(
            bool(devices)
            and any(device.capabilities.can_start_stop and not device.is_online for device in devices)
        )
''',
        '''        self.start_all_btn.setEnabled(
            bool(devices)
            and any(
                device.capabilities.can_start_stop and not device.is_online
                for device in devices
            )
        )
''',
        "workspaces start-all line length",
    )

    replace_once(
        workspaces,
        '''            if device.capabilities.can_start_stop
            and ((action == "start" and not device.is_online) or (action == "stop" and device.is_online))
''',
        '''            if device.capabilities.can_start_stop
            and (
                (action == "start" and not device.is_online)
                or (action == "stop" and device.is_online)
            )
''',
        "workspaces device action line length",
    )

    cmd = [
        sys.executable,
        "-m",
        "ruff",
        "check",
        "sp_farms",
        "tests/test_farm_reel_action_list.py",
        "--fix",
    ]
    print("\n[RUN]", " ".join(cmd))
    result = subprocess.run(cmd, check=False)

    if result.returncode != 0:
        print(
            "\nRuff still reports remaining issues above. "
            "Run the same command without --fix after reviewing them."
        )
    else:
        print("\n[PASS] Ruff check completed with no remaining errors.")

    print("\nNext run:")
    print(
        r".\.venv\Scripts\python.exe -m pytest "
        r"tests/test_design_system.py tests/test_main_window.py "
        r"tests/test_farm_reel_action_list.py -q"
    )


if __name__ == "__main__":
    main()
