"""Code signing hooks and utilities for SP-Farms Windows packaging.

Supports:
- Windows signtool.exe discovery and execution
- PFX / Authenticode signing configuration
- Azure Trusted Signing / Hardware token CLI integration
- Timestamping server configuration (DigiCert / Sectigo)
- Dry-run mode for build automation without inventing certificates
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SigningConfig:
    """Configuration for Windows Authenticode signing."""

    cert_path: Path | None = None
    cert_password: str | None = None
    timestamp_url: str = "http://timestamp.digicert.com"
    digest_algorithm: str = "sha256"
    signtool_path: Path | None = None
    dry_run: bool = False

    @classmethod
    def from_environment(cls, environ: dict[str, str] | None = None) -> SigningConfig:
        env = os.environ if environ is None else environ
        cert_path_str = env.get("SP_FARMS_CERT_PATH")
        cert_path = Path(cert_path_str) if cert_path_str else None
        cert_password = env.get("SP_FARMS_CERT_PASSWORD")
        timestamp_url = env.get("SP_FARMS_TIMESTAMP_URL", "http://timestamp.digicert.com")
        digest_algorithm = env.get("SP_FARMS_DIGEST_ALGORITHM", "sha256")
        signtool_str = env.get("SP_FARMS_SIGNTOOL_PATH")
        signtool_path = Path(signtool_str) if signtool_str else None
        dry_run = env.get("SP_FARMS_SIGN_DRY_RUN", "0") in ("1", "true", "True")

        return cls(
            cert_path=cert_path,
            cert_password=cert_password,
            timestamp_url=timestamp_url,
            digest_algorithm=digest_algorithm,
            signtool_path=signtool_path,
            dry_run=dry_run,
        )


def find_signtool(explicit_path: Path | None = None) -> Path | None:
    """Locate signtool.exe from Windows SDKs or PATH."""
    if explicit_path and explicit_path.exists():
        return explicit_path

    which_signtool = shutil.which("signtool.exe") or shutil.which("signtool")
    if which_signtool:
        return Path(which_signtool)

    # Standard Windows SDK paths
    program_files = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
    sdk_root = Path(program_files) / "Windows Kits" / "10" / "bin"
    if sdk_root.exists():
        candidates = sorted(sdk_root.glob("*/x64/signtool.exe"), reverse=True)
        if candidates:
            return candidates[0]

    return None


def sign_executable(
    target_path: Path,
    config: SigningConfig | None = None,
) -> tuple[bool, str]:
    """Sign an executable or DLL using Authenticode signtool.

    Returns (success: bool, message: str).
    """
    if config is None:
        config = SigningConfig.from_environment()

    if not target_path.exists():
        return False, f"Target file does not exist: {target_path}"

    if config.dry_run:
        return True, f"[DRY-RUN] Would sign {target_path} using {config.digest_algorithm}"

    if not config.cert_path or not config.cert_path.exists():
        return False, "Code signing skipped: SP_FARMS_CERT_PATH not configured or file not found"

    signtool = find_signtool(config.signtool_path)
    if not signtool:
        return (
            False,
            "signtool.exe not found. Install Windows 10/11 SDK or set SP_FARMS_SIGNTOOL_PATH",
        )

    cmd: list[str] = [
        str(signtool),
        "sign",
        "/fd",
        config.digest_algorithm,
        "/f",
        str(config.cert_path),
        "/tr",
        config.timestamp_url,
        "/td",
        config.digest_algorithm,
    ]

    if config.cert_password:
        cmd.extend(["/p", config.cert_password])

    cmd.append(str(target_path))

    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            return True, f"Successfully signed {target_path.name}"
        return False, f"signtool failed with code {res.returncode}: {res.stderr.strip()}"
    except Exception as exc:
        return False, f"Execution failed: {exc}"
