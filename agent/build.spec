# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for RemoteGate Windows Agent.
Builds a single-file .exe with all agent modules and hidden pynput backend imports.

Usage:
    pyinstaller build.spec
"""

import sys
from pathlib import Path

block_cipher = None

agent_dir = Path(SPECPATH)

# Collect all agent Python source files
agent_sources = [str(p) for p in agent_dir.glob("*.py") if p.name != "build.spec"]

a = Analysis(
    [str(agent_dir / "main.py")],
    pathex=[str(agent_dir)],
    binaries=[],
    datas=[],
    hiddenimports=[
        # pynput platform-specific backends
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
        "pynput._util.win32",
        "pynput.keyboard",
        "pynput.mouse",
        # mss platform backend
        "mss.windows",
        # Standard library modules sometimes missed
        "ctypes",
        "ctypes.wintypes",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unused pynput backends to reduce size
        "pynput.keyboard._xorg",
        "pynput.keyboard._darwin",
        "pynput.mouse._xorg",
        "pynput.mouse._darwin",
        "pynput._util.xorg",
        "pynput._util.darwin",
        # Exclude test frameworks
        "pytest",
        "unittest",
        # Exclude unused mss backends
        "mss.linux",
        "mss.darwin",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="RemoteGateAgent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window (tray app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # TODO: Add icon in v0.2
)
