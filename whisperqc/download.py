# -*- coding: utf-8 -*-
"""Téléchargement HTTP avec progression, fichier .part et vérif SHA-256."""

import hashlib
import os
import urllib.request
from pathlib import Path

from .platform_support import ssl_context

CHUNK = 1024 * 1024
UA = {"User-Agent": "WhisperQC"}


def fetch_json(url: str):
    import json
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30, context=ssl_context()) as r:
        return json.loads(r.read().decode("utf-8"))


def download(url: str, dest: Path, size: int | None = None,
             sha256: str | None = None, progress=None) -> None:
    """Télécharge url -> dest. progress(n_bytes) est appelé à chaque bloc
    avec le nombre d'octets reçus depuis le dernier appel."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    h = hashlib.sha256() if sha256 else None
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60, context=ssl_context()) as r, \
            open(part, "wb") as f:
        while True:
            buf = r.read(CHUNK)
            if not buf:
                break
            f.write(buf)
            if h:
                h.update(buf)
            if progress:
                progress(len(buf))
    got = part.stat().st_size
    if size is not None and got != size:
        part.unlink(missing_ok=True)
        raise ConnectionError(f"téléchargement incomplet ({got}/{size} octets)")
    if h and h.hexdigest() != sha256:
        part.unlink(missing_ok=True)
        raise ConnectionError("fichier corrompu pendant le téléchargement")
    os.replace(part, dest)
