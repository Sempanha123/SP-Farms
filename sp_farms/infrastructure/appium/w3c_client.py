"""W3C WebDriver & Appium 2 UiAutomator2 HTTP REST client."""

import base64
import logging
from typing import Any

import httpx

from sp_farms.application.appium_port import AppiumDriverPort
from sp_farms.domain.automation import (
    AppiumConnectionError,
    AppState,
    AutomationError,
    By,
    ElementNotFoundError,
    ElementRef,
    SessionNotCreatedError,
    StaleElementReferenceError,
    UiAutomator2Capabilities,
)

logger = logging.getLogger(__name__)

# W3C / Appium locator mapping
_LOCATOR_STRATEGY_MAP = {
    By.ID: "id",
    By.XPATH: "xpath",
    By.ACCESSIBILITY_ID: "accessibility id",
    By.CLASS_NAME: "class name",
    By.ANDROID_UIAUTOMATOR: "-android uiautomator",
}

# AppState mapping from Appium integer codes:
# 0: not installed, 1: not running, 2: background suspended, 3: background, 4: foreground
_APP_STATE_MAP = {
    0: AppState.NOT_INSTALLED,
    1: AppState.NOT_RUNNING,
    2: AppState.RUNNING_IN_BACKGROUND_SUSPENDED,
    3: AppState.RUNNING_IN_BACKGROUND,
    4: AppState.RUNNING_IN_FOREGROUND,
}


class W3CAppiumClient(AppiumDriverPort):
    """Standard W3C / Appium 2 HTTP client implementation."""

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self._timeout = timeout_seconds
        self._http = httpx.Client(timeout=timeout_seconds)
        self._session_servers: dict[str, str] = {}

    def _url(self, session_id: str, path: str) -> str:
        server_url = self._session_servers.get(session_id, "http://127.0.0.1:4723")
        clean_base = server_url.rstrip("/")
        clean_path = path.lstrip("/")
        return f"{clean_base}/{clean_path}"

    def create_session(self, server_url: str, capabilities: UiAutomator2Capabilities) -> str:
        url = f"{server_url.rstrip('/')}/session"
        payload = capabilities.to_w3c_payload()
        try:
            res = self._http.post(url, json=payload)
        except Exception as e:
            raise AppiumConnectionError(
                f"Failed to connect to Appium 2 server at {server_url}: {e}"
            ) from e

        if res.status_code != 200:
            raise SessionNotCreatedError(
                f"Appium session creation failed (HTTP {res.status_code}): {res.text}"
            )

        data = res.json()
        val = data.get("value", {})
        session_id = val.get("sessionId") or data.get("sessionId")
        if not session_id:
            raise SessionNotCreatedError(f"No sessionId returned from Appium: {data}")

        session_id_str = str(session_id)
        self._session_servers[session_id_str] = server_url
        logger.info(
            "Created Appium 2 session %s on %s (device udid=%s)",
            session_id_str,
            server_url,
            capabilities.udid,
        )
        return session_id_str

    def delete_session(self, session_id: str) -> None:
        url = self._url(session_id, f"/session/{session_id}")
        try:
            self._http.delete(url)
            logger.info("Deleted Appium session %s", session_id)
        except Exception as e:
            logger.warning("Error deleting Appium session %s: %s", session_id, e)
        finally:
            self._session_servers.pop(session_id, None)

    def is_session_alive(self, session_id: str) -> bool:
        if session_id not in self._session_servers:
            return False
        url = self._url(session_id, f"/session/{session_id}/timeouts")
        try:
            res = self._http.get(url)
            return res.status_code == 200
        except Exception:
            return False

    def activate_app(self, session_id: str, app_id: str) -> None:
        url = self._url(session_id, f"/session/{session_id}/appium/device/activate_app")
        res = self._http.post(url, json={"appId": app_id})
        if res.status_code != 200:
            raise AutomationError(f"Failed to activate app {app_id}: {res.text}")

    def terminate_app(self, session_id: str, app_id: str) -> bool:
        url = self._url(session_id, f"/session/{session_id}/appium/device/terminate_app")
        res = self._http.post(url, json={"appId": app_id})
        if res.status_code == 200:
            data = res.json()
            return bool(data.get("value", True))
        return False

    def query_app_state(self, session_id: str, app_id: str) -> AppState:
        url = self._url(session_id, f"/session/{session_id}/appium/device/app_state")
        res = self._http.post(url, json={"appId": app_id})
        if res.status_code == 200:
            code = res.json().get("value", 0)
            return _APP_STATE_MAP.get(code, AppState.UNKNOWN)
        return AppState.UNKNOWN

    def get_current_activity(self, session_id: str) -> str:
        url = self._url(session_id, f"/session/{session_id}/appium/device/current_activity")
        res = self._http.get(url)
        if res.status_code == 200:
            return str(res.json().get("value", ""))
        return ""

    def get_current_package(self, session_id: str) -> str:
        url = self._url(session_id, f"/session/{session_id}/appium/device/current_package")
        res = self._http.get(url)
        if res.status_code == 200:
            return str(res.json().get("value", ""))
        return ""

    def get_page_source(self, session_id: str) -> str:
        url = self._url(session_id, f"/session/{session_id}/source")
        res = self._http.get(url)
        if res.status_code == 200:
            return str(res.json().get("value", ""))
        return ""

    def take_screenshot(self, session_id: str) -> bytes:
        url = self._url(session_id, f"/session/{session_id}/screenshot")
        res = self._http.get(url)
        if res.status_code == 200:
            b64_str = res.json().get("value", "")
            return base64.b64decode(b64_str)
        raise AutomationError(f"Failed to capture screenshot: {res.text}")

    def find_element(self, session_id: str, by: By, value: str) -> ElementRef:
        url = self._url(session_id, f"/session/{session_id}/element")
        strategy = _LOCATOR_STRATEGY_MAP.get(by, "id")
        res = self._http.post(url, json={"using": strategy, "value": value})
        if res.status_code != 200:
            raise ElementNotFoundError(f"Element not found by {by.value}='{value}': {res.text}")

        data = res.json().get("value", {})
        # W3C element identifier format is "element-6066-11e4-a52e-4f735466cecf"
        elem_id = (
            data.get("element-6066-11e4-a52e-4f735466cecf")
            or data.get("ELEMENT")
            or str(data)
        )
        return ElementRef(element_id=elem_id, by=by, value=value)

    def find_elements(self, session_id: str, by: By, value: str) -> list[ElementRef]:
        url = self._url(session_id, f"/session/{session_id}/elements")
        strategy = _LOCATOR_STRATEGY_MAP.get(by, "id")
        res = self._http.post(url, json={"using": strategy, "value": value})
        if res.status_code != 200:
            return []

        elements_data = res.json().get("value", [])
        results: list[ElementRef] = []
        for item in elements_data:
            elem_id = item.get("element-6066-11e4-a52e-4f735466cecf") or item.get("ELEMENT")
            if elem_id:
                results.append(ElementRef(element_id=str(elem_id), by=by, value=value))
        return results

    def click(self, session_id: str, element_id: str) -> None:
        url = self._url(session_id, f"/session/{session_id}/element/{element_id}/click")
        res = self._http.post(url, json={})
        if res.status_code != 200:
            raise AutomationError(f"Click failed on element {element_id}: {res.text}")

    def type_text(self, session_id: str, element_id: str, text: str) -> None:
        url = self._url(session_id, f"/session/{session_id}/element/{element_id}/value")
        # W3C spec accepts list of characters or string
        res = self._http.post(url, json={"text": text, "value": list(text)})
        if res.status_code != 200:
            raise AutomationError(f"Type text failed on element {element_id}: {res.text}")

    def clear_text(self, session_id: str, element_id: str) -> None:
        url = self._url(session_id, f"/session/{session_id}/element/{element_id}/clear")
        res = self._http.post(url, json={})
        if res.status_code != 200:
            raise AutomationError(f"Clear text failed on element {element_id}: {res.text}")

    def get_element_text(self, session_id: str, element_id: str) -> str:
        url = self._url(session_id, f"/session/{session_id}/element/{element_id}/text")
        res = self._http.get(url)
        if res.status_code == 200:
            return str(res.json().get("value", ""))
        return ""

    def get_element_attribute(self, session_id: str, element_id: str, name: str) -> str | None:
        url = self._url(session_id, f"/session/{session_id}/element/{element_id}/attribute/{name}")
        res = self._http.get(url)
        if res.status_code == 200:
            val = res.json().get("value")
            return str(val) if val is not None else None
        return None

    def is_element_displayed(self, session_id: str, element_id: str) -> bool:
        url = self._url(session_id, f"/session/{session_id}/element/{element_id}/displayed")
        res = self._http.get(url)
        if res.status_code == 200:
            return bool(res.json().get("value", False))
        return False

    def is_element_enabled(self, session_id: str, element_id: str) -> bool:
        url = self._url(session_id, f"/session/{session_id}/element/{element_id}/enabled")
        res = self._http.get(url)
        if res.status_code == 200:
            return bool(res.json().get("value", False))
        return False

    def tap_coordinates(self, session_id: str, x: int, y: int) -> None:
        url = self._url(session_id, f"/session/{session_id}/actions")
        actions_payload = {
            "actions": [
                {
                    "type": "pointer",
                    "id": "finger1",
                    "parameters": {"pointerType": "touch"},
                    "actions": [
                        {"type": "pointerMove", "duration": 0, "x": x, "y": y},
                        {"type": "pointerDown", "button": 0},
                        {"type": "pause", "duration": 50},
                        {"type": "pointerUp", "button": 0},
                    ],
                }
            ]
        }
        res = self._http.post(url, json=actions_payload)
        if res.status_code != 200:
            raise AutomationError(f"Tap at ({x}, {y}) failed: {res.text}")

    def swipe(
        self,
        session_id: str,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration_ms: int = 800,
    ) -> None:
        url = self._url(session_id, f"/session/{session_id}/actions")
        actions_payload = {
            "actions": [
                {
                    "type": "pointer",
                    "id": "finger1",
                    "parameters": {"pointerType": "touch"},
                    "actions": [
                        {"type": "pointerMove", "duration": 0, "x": start_x, "y": start_y},
                        {"type": "pointerDown", "button": 0},
                        {"type": "pause", "duration": 50},
                        {"type": "pointerMove", "duration": duration_ms, "x": end_x, "y": end_y},
                        {"type": "pointerUp", "button": 0},
                    ],
                }
            ]
        }
        res = self._http.post(url, json=actions_payload)
        if res.status_code != 200:
            raise AutomationError(f"Swipe failed: {res.text}")

    def press_key_code(self, session_id: str, keycode: int) -> None:
        url = self._url(session_id, f"/session/{session_id}/appium/device/press_keycode")
        self._http.post(url, json={"keycode": keycode})

    def press_back(self, session_id: str) -> None:
        url = self._url(session_id, f"/session/{session_id}/back")
        self._http.post(url, json={})

    def execute_script(self, session_id: str, script: str, args: list[Any] | None = None) -> Any:
        url = self._url(session_id, f"/session/{session_id}/execute/sync")
        res = self._http.post(url, json={"script": script, "args": args or []})
        if res.status_code == 200:
            return res.json().get("value")
        return None
