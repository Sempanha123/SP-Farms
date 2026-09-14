"""Fake / in-memory Appium 2 driver adapter for comprehensive automated unit testing."""

import base64
from typing import Any

from sp_farms.application.appium_port import AppiumDriverPort
from sp_farms.domain.automation import (
    AppState,
    By,
    ElementRef,
    SessionNotCreatedError,
    UiAutomator2Capabilities,
)


class FakeAppiumDriver(AppiumDriverPort):
    """In-memory simulation of Appium 2 UiAutomator2 server."""

    def __init__(self) -> None:
        self.sessions: dict[str, UiAutomator2Capabilities] = {}
        self.app_states: dict[str, AppState] = {}
        self.current_activities: dict[str, str] = {}
        self.current_packages: dict[str, str] = {}
        self.page_sources: dict[str, str] = {}
        self.elements: dict[str, dict[str, ElementRef]] = {}  # session_id -> {selector: ElementRef}
        self.element_attributes: dict[str, dict[str, str]] = {}  # elem_id -> {attr: val}
        self.recorded_taps: list[dict[str, Any]] = []
        self.recorded_swipes: list[dict[str, Any]] = []
        self.recorded_inputs: list[dict[str, Any]] = []
        self.recorded_keys: list[dict[str, Any]] = []
        self.session_counter = 0
        self.fail_session_creation = False
        self.session_creation_error_msg = "Simulated session failure"

    def create_session(self, server_url: str, capabilities: UiAutomator2Capabilities) -> str:
        if self.fail_session_creation:
            raise SessionNotCreatedError(self.session_creation_error_msg)
        self.session_counter += 1
        session_id = f"fake-session-{self.session_counter}"
        self.sessions[session_id] = capabilities
        self.app_states[session_id] = AppState.RUNNING_IN_FOREGROUND
        self.current_packages[session_id] = capabilities.app_package or "com.facebook.katana"
        self.current_activities[session_id] = capabilities.app_activity or ".LoginActivity"
        self.elements[session_id] = {}
        return session_id

    def delete_session(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)
        self.elements.pop(session_id, None)

    def is_session_alive(self, session_id: str) -> bool:
        return session_id in self.sessions

    def activate_app(self, session_id: str, app_id: str) -> None:
        self.current_packages[session_id] = app_id
        self.app_states[session_id] = AppState.RUNNING_IN_FOREGROUND

    def terminate_app(self, session_id: str, app_id: str) -> bool:
        self.app_states[session_id] = AppState.NOT_RUNNING
        return True

    def query_app_state(self, session_id: str, app_id: str) -> AppState:
        return self.app_states.get(session_id, AppState.NOT_RUNNING)

    def get_current_activity(self, session_id: str) -> str:
        return self.current_activities.get(session_id, "")

    def get_current_package(self, session_id: str) -> str:
        return self.current_packages.get(session_id, "")

    def get_page_source(self, session_id: str) -> str:
        return self.page_sources.get(
            session_id, "<hierarchy><android.widget.FrameLayout /></hierarchy>"
        )

    def take_screenshot(self, session_id: str) -> bytes:
        # Minimal 1x1 PNG bytes
        return base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )

    def register_element(
        self, session_id: str, by: By, value: str, elem_id: str, text: str = ""
    ) -> ElementRef:
        elem = ElementRef(element_id=elem_id, by=by, value=value, text=text)
        if session_id not in self.elements:
            self.elements[session_id] = {}
        self.elements[session_id][f"{by.value}:{value}"] = elem
        return elem

    def find_element(self, session_id: str, by: By, value: str) -> ElementRef:
        key = f"{by.value}:{value}"
        session_elems = self.elements.get(session_id, {})
        if key in session_elems:
            return session_elems[key]
        # Auto-create mock element if not specifically primed
        elem_id = f"mock-elem-{len(session_elems) + 1}"
        elem = ElementRef(element_id=elem_id, by=by, value=value)
        session_elems[key] = elem
        return elem

    def find_elements(self, session_id: str, by: By, value: str) -> list[ElementRef]:
        key = f"{by.value}:{value}"
        session_elems = self.elements.get(session_id, {})
        if key in session_elems:
            return [session_elems[key]]
        return []

    def click(self, session_id: str, element_id: str) -> None:
        self.recorded_taps.append({"session_id": session_id, "element_id": element_id})

    def type_text(self, session_id: str, element_id: str, text: str) -> None:
        self.recorded_inputs.append(
            {"session_id": session_id, "element_id": element_id, "text": text}
        )
        session_elems = self.elements.get(session_id, {})
        for key, elem in list(session_elems.items()):
            if elem.element_id == element_id:
                updated = ElementRef(
                    element_id=elem.element_id,
                    by=elem.by,
                    value=elem.value,
                    bounds=elem.bounds,
                    text=text,
                    is_displayed=elem.is_displayed,
                    is_enabled=elem.is_enabled,
                )
                session_elems[key] = updated
                break

    def clear_text(self, session_id: str, element_id: str) -> None:
        session_elems = self.elements.get(session_id, {})
        for key, elem in list(session_elems.items()):
            if elem.element_id == element_id:
                updated = ElementRef(
                    element_id=elem.element_id,
                    by=elem.by,
                    value=elem.value,
                    bounds=elem.bounds,
                    text="",
                    is_displayed=elem.is_displayed,
                    is_enabled=elem.is_enabled,
                )
                session_elems[key] = updated
                break

    def get_element_text(self, session_id: str, element_id: str) -> str:
        for elem in self.elements.get(session_id, {}).values():
            if elem.element_id == element_id:
                return elem.text
        return ""

    def get_element_attribute(self, session_id: str, element_id: str, name: str) -> str | None:
        return self.element_attributes.get(element_id, {}).get(name)

    def is_element_displayed(self, session_id: str, element_id: str) -> bool:
        return True

    def is_element_enabled(self, session_id: str, element_id: str) -> bool:
        return True

    def tap_coordinates(self, session_id: str, x: int, y: int) -> None:
        self.recorded_taps.append({"session_id": session_id, "x": x, "y": y})

    def swipe(
        self,
        session_id: str,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration_ms: int = 800,
    ) -> None:
        self.recorded_swipes.append(
            {
                "session_id": session_id,
                "start": (start_x, start_y),
                "end": (end_x, end_y),
                "duration_ms": duration_ms,
            }
        )

    def press_key_code(self, session_id: str, keycode: int) -> None:
        self.recorded_keys.append({"session_id": session_id, "keycode": keycode})

    def press_back(self, session_id: str) -> None:
        self.recorded_keys.append({"session_id": session_id, "key": "BACK"})

    def execute_script(self, session_id: str, script: str, args: list[Any] | None = None) -> Any:
        return None
