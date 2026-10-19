# -*- coding: utf-8 -*-
"""Tout ce qui diffère entre Windows et macOS est ici, nulle part ailleurs.

Dossiers utilisateur (config, logs, modèles, SRT), ressources embarquées
par PyInstaller, DLL CUDA, ouverture d'un dossier dans l'explorateur.
"""

import os
import subprocess
import sys
from pathlib import Path

APP_NAME = "WhisperQC"

IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
FROZEN = getattr(sys, "frozen", False)


def resource_dir() -> Path:
    """Dossier des fichiers embarqués (assets/). PyInstaller les extrait
    dans sys._MEIPASS ; en dev c'est la racine du projet."""
    if FROZEN:
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def app_dir() -> Path:
    """Dossier de l'exécutable (Windows) — là où la v1 écrivait tout.
    Sert seulement à récupérer l'ancienne config / les anciens modèles."""
    if FROZEN:
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _windows_known_folder(guid: str) -> Path | None:
    """SHGetKnownFolderPath — suit les redirections OneDrive de Documents."""
    try:
        import ctypes
        from ctypes import wintypes
        import uuid

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                        ("Data3", wintypes.WORD), ("Data4", wintypes.BYTE * 8)]

        u = uuid.UUID(guid)
        g = GUID(u.time_low, u.time_mid, u.time_hi_version,
                 (wintypes.BYTE * 8).from_buffer_copy(u.bytes[8:]))
        out = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None,
                                                      ctypes.byref(out)) != 0:
            return None
        path = Path(out.value)
        ctypes.windll.ole32.CoTaskMemFree(out)
        return path
    except Exception:
        return None


def config_dir() -> Path:
    """config.json (clé API). Windows : %APPDATA%\\WhisperQC.
    macOS : ~/Library/Application Support/WhisperQC."""
    if IS_WINDOWS:
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif IS_MAC:
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / APP_NAME


def data_dir() -> Path:
    """Gros fichiers (modèles, module GPU). Windows : %LOCALAPPDATA%\\WhisperQC
    (pas synchronisé avec le profil itinérant). macOS : Application Support."""
    if IS_WINDOWS:
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif IS_MAC:
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / APP_NAME


def log_dir() -> Path:
    if IS_MAC:
        return Path.home() / "Library" / "Logs" / APP_NAME
    return data_dir() / "logs"


def models_dir() -> Path:
    return data_dir() / "models"


def cuda_dir() -> Path:
    """DLL cuBLAS/cuDNN téléchargées à la demande (Windows seulement)."""
    return data_dir() / "cuda"


def documents_dir() -> Path:
    if IS_WINDOWS:
        p = _windows_known_folder("FDD39AD0-238F-46AF-ADB4-6C85480369C7")
        if p:
            return p
    return Path.home() / "Documents"


def default_srt_dir() -> Path:
    """Dossier de sortie par défaut des SRT (Documents/WhisperQC/SRT)."""
    return documents_dir() / APP_NAME / "SRT"


def legacy_paths() -> dict:
    """Où la v1 mettait ses fichiers (à côté de l'exe)."""
    base = app_dir()
    return {
        "config": base / "config.json",
        "models": base / "_models",
        "srt": base / "SRT",
    }


def running_from_zip() -> bool:
    """Windows ouvre un .exe lancé depuis l'intérieur d'un zip dans un
    dossier temporaire (…\\Temp\\Temp1_xxx.zip\\…). Rien n'y persiste."""
    if not (IS_WINDOWS and FROZEN):
        return False
    p = str(app_dir()).lower()
    return "\\temp\\" in p and (".zip" in p or "\\temp1_" in p or "\\rar$" in p or "\\7z" in p)


def setup_cuda_search_path() -> None:
    """Rend les DLL CUDA téléchargées visibles pour ctranslate2. À appeler
    avant de charger un modèle ; sans effet hors Windows."""
    if not IS_WINDOWS:
        return
    d = cuda_dir()
    if not d.is_dir():
        return
    try:
        os.add_dll_directory(str(d))
    except (OSError, AttributeError):
        pass
    if str(d) not in os.environ.get("PATH", ""):
        os.environ["PATH"] = str(d) + os.pathsep + os.environ.get("PATH", "")


def open_in_file_manager(path: Path) -> None:
    try:
        if IS_WINDOWS:
            os.startfile(str(path))  # noqa: S606
        elif IS_MAC:
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


def ssl_context():
    """Contexte SSL avec les certificats de certifi. Indispensable dans une
    .app macOS (le Python embarqué n'a pas accès au trousseau système)."""
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()
