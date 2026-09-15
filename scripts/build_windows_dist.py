"""Build distributable Windows package and installer for SP-Farms.

Steps:
1. Generate high-res icons and Windows version info metadata.
2. Run PyInstaller using packaging/sp_farms.spec.
3. Sign binary executables and DLLs if signing credentials/flags are provided.
4. Generate installer script / artifacts.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from sp_farms.infrastructure.signing import SigningConfig, sign_executable

ROOT_DIR = Path(__file__).resolve().parent.parent


def build_package(skip_installer: bool = False) -> int:
    print("=== Step 1: Generating Application Icons ===")
    icon_script = ROOT_DIR / "scripts" / "generate_icons.py"
    res = subprocess.run([sys.executable, str(icon_script)], check=False)
    if res.returncode != 0:
        print("Failed to generate icons")
        return res.returncode

    print("=== Step 2: Running PyInstaller ===")
    spec_file = ROOT_DIR / "packaging_windows" / "sp_farms.spec"
    dist_dir = ROOT_DIR / "dist"
    work_dir = ROOT_DIR / "build" / "pyinstaller"

    pyinstaller_cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(work_dir),
        str(spec_file),
    ]
    print(f"Executing: {' '.join(pyinstaller_cmd)}")
    res = subprocess.run(pyinstaller_cmd, check=False)
    if res.returncode != 0:
        print(f"PyInstaller failed with code {res.returncode}")
        return res.returncode

    print("=== Step 3: Verifying Dist Output ===")
    output_exe = dist_dir / "SP-Farms" / "SP-Farms.exe"
    if not output_exe.exists():
        print(f"Expected executable not found at: {output_exe}")
        return 1
    print(f"Successfully generated Windows binary: {output_exe}")

    print("=== Step 4: Code Signing Hook ===")
    signing_config = SigningConfig.from_environment()
    success, msg = sign_executable(output_exe, signing_config)
    print(f"Code signing status: {msg}")

    print("=== Packaging complete ===")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build SP-Farms Windows Distribution")
    parser.add_argument("--skip-installer", action="store_true", help="Skip compiling installer")
    args = parser.parse_args()
    return build_package(skip_installer=args.skip_installer)


if __name__ == "__main__":
    raise SystemExit(main())
