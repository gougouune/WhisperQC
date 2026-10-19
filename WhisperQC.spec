# -*- mode: python ; coding: utf-8 -*-
# Build : pyinstaller WhisperQC.spec --noconfirm
# Windows -> dist/WhisperQC/WhisperQC.exe (dossier, pas --onefile : démarre
# plus vite et déclenche beaucoup moins de faux positifs antivirus)
# macOS   -> dist/WhisperQC.app

import re
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

VERSION = re.search(r'__version__ = "([^"]+)"',
                    open("whisperqc/__init__.py", encoding="utf-8").read()).group(1)
IS_MAC = sys.platform == "darwin"

datas = [("assets", "assets")]
datas += collect_data_files("faster_whisper")   # silero_vad_v6.onnx
datas += collect_data_files("customtkinter")
datas += collect_data_files("tkinterdnd2")      # binaires tkdnd (drag & drop)
binaries = collect_dynamic_libs("ctranslate2")

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=["certifi"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["torch", "matplotlib", "IPython", "pytest", "scipy", "pandas"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WhisperQC",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icon.icns" if IS_MAC else "assets/icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="WhisperQC",
)

if IS_MAC:
    app = BUNDLE(
        coll,
        name="WhisperQC.app",
        icon="assets/icon.icns",
        bundle_identifier="com.simongagnon.whisperqc",
        version=VERSION,
        info_plist={
            "CFBundleName": "WhisperQC",
            "CFBundleDisplayName": "WhisperQC",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "LSMinimumSystemVersion": "13.0",
            "NSHighResolutionCapable": True,
            "NSDocumentsFolderUsageDescription":
                "WhisperQC enregistre tes SRT dans Documents/WhisperQC.",
            "NSDesktopFolderUsageDescription":
                "WhisperQC lit les vidéos que tu choisis sur le Bureau.",
            "NSDownloadsFolderUsageDescription":
                "WhisperQC lit les vidéos que tu choisis dans Téléchargements.",
            "NSRemovableVolumesUsageDescription":
                "WhisperQC lit les vidéos que tu choisis sur un disque externe.",
        },
    )
