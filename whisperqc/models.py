# -*- coding: utf-8 -*-
"""Modèles Whisper (format CTranslate2) : présence, téléchargement au
premier usage. Mêmes dépôts que Faster-Whisper-XXL utilisait."""

from pathlib import Path

from . import platform_support as plat
from .download import download, fetch_json

REPOS = {
    "large-v3-turbo": "Purfview/faster-whisper-large-v3-turbo",
    "large-v3":       "Systran/faster-whisper-large-v3",
    "medium":         "Systran/faster-whisper-medium",
    "small":          "Systran/faster-whisper-small",
}

# Tailles approximatives pour les messages (le vrai total vient de l'API)
APPROX_SIZE = {"large-v3-turbo": "1,6 Go", "large-v3": "3,1 Go",
               "medium": "1,5 Go", "small": "490 Mo"}

_REQUIRED = ("model.bin", "config.json", "tokenizer.json")


def _is_complete(d: Path) -> bool:
    return d.is_dir() and all((d / f).is_file() for f in _REQUIRED) and \
        any((d / v).is_file() for v in ("vocabulary.json", "vocabulary.txt"))


def model_path(name: str) -> Path | None:
    """Chemin du modèle s'il est déjà présent, sinon None. Reprend les
    modèles de la v1 (_models à côté de l'exe) pour éviter de retélécharger."""
    for d in (plat.models_dir() / f"faster-whisper-{name}",
              plat.legacy_paths()["models"] / f"faster-whisper-{name}"):
        if _is_complete(d):
            return d
    return None


def ensure_model(name: str, progress=None, log_fn=None) -> Path:
    """Retourne le dossier du modèle, en le téléchargeant au besoin.
    progress(done_bytes, total_bytes)."""
    existing = model_path(name)
    if existing:
        return existing

    repo = REPOS[name]
    dest = plat.models_dir() / f"faster-whisper-{name}"
    tree = fetch_json(f"https://huggingface.co/api/models/{repo}/tree/main")
    files = [f for f in tree if f.get("type") == "file"
             and not f["path"].startswith(".") and f["path"] != "README.md"]
    total = sum(f.get("size", 0) for f in files)
    done = 0

    def _tick(n):
        nonlocal done
        done += n
        if progress:
            progress(done, total)

    for f in files:
        target = dest / f["path"]
        lfs = f.get("lfs") or {}
        if target.is_file() and target.stat().st_size == f.get("size"):
            _tick(f["size"])
            continue
        if log_fn and f.get("size", 0) > 50_000_000:
            log_fn(f"   {f['path']} ({f['size'] / 1e9:.1f} Go)")
        download(f"https://huggingface.co/{repo}/resolve/main/{f['path']}",
                 target, size=f.get("size"), sha256=lfs.get("oid"), progress=_tick)

    if not _is_complete(dest):
        raise ConnectionError("modèle incomplet après téléchargement")
    return dest
