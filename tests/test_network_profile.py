"""Unit tests for Phase 54: Network Profile and Pre-Restore Network Automation."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from sp_farms.application.network_service import (
    NetworkRequirementError,
    NetworkService,
    NetworkVerificationResult,
)
from sp_farms.domain.network_profile import (
    AccountNetworkBinding,
    FallbackPolicy,
    NetworkBindingStatus,
    NetworkProfile,
    NetworkProfileType,
    PageNetworkOverride,
)


def test_network_profile_creation_and_defaults():
    profile = NetworkProfile(
        name="Dedicated US Proxy",
        profile_type=NetworkProfileType.HTTP_PROXY,
        host="10.0.0.50",
        port=8080,
        country_code="US",
        region_label="North America",
    )

    assert profile.name == "Dedicated US Proxy"
    assert profile.profile_type == NetworkProfileType.HTTP_PROXY
    assert profile.host == "10.0.0.50"
    assert profile.port == 8080
    assert profile.verify_before_use is True
    assert profile.require_success is True


def test_network_service_resolve_system_default():
    service = NetworkService()
    profile = service.resolve_effective_profile(account_id="acc-999")
    assert profile.profile_type == NetworkProfileType.SYSTEM
    assert "System Network" in profile.name


def test_network_service_resolve_account_binding():
    service = NetworkService()
    profile = NetworkProfile(
        name="Account Proxy",
        profile_type=NetworkProfileType.SOCKS5,
        host="proxy.corp.internal",
        port=1080,
    )
    service.save_profile(profile)
    service.bind_account_to_profile(account_id="acc-1", profile_id=profile.id)

    resolved = service.resolve_effective_profile(account_id="acc-1")
    assert resolved.id == profile.id
    assert resolved.profile_type == NetworkProfileType.SOCKS5
    assert resolved.host == "proxy.corp.internal"


def test_network_service_resolve_page_override():
    service = NetworkService()
    acc_profile = NetworkProfile(
        name="Account Proxy",
        profile_type=NetworkProfileType.HTTP_PROXY,
        host="acc.proxy",
        port=8080,
    )
    page_profile = NetworkProfile(
        name="Page Dedicated Proxy",
        profile_type=NetworkProfileType.HTTPS_PROXY,
        host="page.proxy",
        port=8443,
    )
    service.save_profile(acc_profile)
    service.save_profile(page_profile)

    service.bind_account_to_profile("acc-1", acc_profile.id)
    service.set_page_network_override("page-100", page_profile.id)

    # Resolving with page_id uses page override
    resolved = service.resolve_effective_profile(account_id="acc-1", page_id="page-100")
    assert resolved.id == page_profile.id
    assert resolved.name == "Page Dedicated Proxy"

    # Resolving without page_id uses account profile
    resolved_acc = service.resolve_effective_profile(account_id="acc-1")
    assert resolved_acc.id == acc_profile.id


def test_network_service_verify_system_profile():
    service = NetworkService()
    system_profile = NetworkProfile(name="Sys", profile_type=NetworkProfileType.SYSTEM)
    result = service.verify_profile(system_profile)
    assert result.success is True
    assert "System network" in result.message


def test_network_service_verify_remote_profile_success():
    service = NetworkService()
    profile = NetworkProfile(
        name="Remote Proxy",
        profile_type=NetworkProfileType.HTTP_PROXY,
        host="1.2.3.4",
        port=8080,
    )

    with patch("socket.create_connection") as mock_conn:
        mock_conn.return_value.__enter__.return_value = MagicMock()
        result = service.verify_profile(profile)
        assert result.success is True
        assert result.error_code is None


def test_network_service_verify_remote_profile_failure():
    service = NetworkService()
    profile = NetworkProfile(
        name="Broken Proxy",
        profile_type=NetworkProfileType.HTTP_PROXY,
        host="10.255.255.1",
        port=9999,
    )

    with patch("socket.create_connection", side_effect=OSError("Connection refused")):
        result = service.verify_profile(profile)
        assert result.success is False
        assert result.error_code == "connection_failed"
        assert "Connection refused" in (result.error_message or "")


def test_prepare_network_for_restore_stop_policy_on_failure():
    mock_adb = MagicMock()
    service = NetworkService(adb_client=mock_adb)

    profile = NetworkProfile(
        name="Failed Proxy",
        profile_type=NetworkProfileType.HTTP_PROXY,
        host="unreachable.net",
        port=8080,
    )
    service.save_profile(profile)
    service.bind_account_to_profile(
        account_id="acc-stop",
        profile_id=profile.id,
        fallback_policy=FallbackPolicy.STOP,
    )

    with patch.object(service, "verify_profile", return_value=NetworkVerificationResult(
        profile_id=profile.id,
        success=False,
        error_code="connection_failed",
        error_message="Host unreachable",
    )):
        with pytest.raises(NetworkRequirementError) as exc_info:
            service.prepare_network_for_restore("acc-stop", device_serial="emulator-5554")

        assert "failed verification: Host unreachable" in str(exc_info.value)
        assert "aborted to prevent silent network-policy violation" in str(exc_info.value)


def test_prepare_network_for_restore_success_applies_adb_proxy():
    mock_adb = MagicMock()
    service = NetworkService(adb_client=mock_adb)

    profile = NetworkProfile(
        name="Active Proxy",
        profile_type=NetworkProfileType.HTTP_PROXY,
        host="192.168.1.150",
        port=3128,
    )
    service.save_profile(profile)
    service.bind_account_to_profile(account_id="acc-ok", profile_id=profile.id)

    with patch.object(service, "verify_profile", return_value=NetworkVerificationResult(
        profile_id=profile.id,
        success=True,
        latency_ms=15.0,
    )):
        eff_profile = service.prepare_network_for_restore("acc-ok", device_serial="emulator-5554")
        assert eff_profile.id == profile.id
        mock_adb.shell.assert_called_with("emulator-5554", "settings put global http_proxy 192.168.1.150:3128")


def test_prepare_network_resets_proxy_for_system():
    mock_adb = MagicMock()
    service = NetworkService(adb_client=mock_adb)

    eff_profile = service.prepare_network_for_restore("acc-unbound", device_serial="emulator-5554")
    assert eff_profile.profile_type == NetworkProfileType.SYSTEM
    mock_adb.shell.assert_called_with("emulator-5554", "settings put global http_proxy :0")
