# -*- coding: utf-8 -*-
"""Fichier log dans le dossier utilisateur + traduction des erreurs en
messages français lisibles (au lieu des tracebacks)."""

import logging
import logging.handlers
import platform
import sys
import threading
import urllib.error

from . import __version__
from . import platform_support as plat

log = logging.getLogger("whisperqc")
LOG_FILE = plat.log_dir() / "whisperqc.log"


def setup() -> None:
    log.setLevel(logging.INFO)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        h = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(h)
    except OSError:
        log.addHandler(logging.NullHandler())

    log.info("WhisperQC %s · %s %s · Python %s", __version__, platform.system(),
             platform.release(), platform.python_version())

    def _hook(exc_type, exc, tb):
        log.error("Erreur non gérée", exc_info=(exc_type, exc, tb))

    sys.excepthook = _hook
    threading.excepthook = lambda a: _hook(a.exc_type, a.exc_value, a.exc_traceback)


class UserError(Exception):
    """Erreur dont le message est déjà prêt pour l'utilisateur."""


def friendly(e: BaseException) -> str:
    """Message français court pour l'utilisateur. Le détail technique va
    dans le log."""
    if isinstance(e, UserError):
        return str(e)
    msg = str(e)
    low = msg.lower()

    if isinstance(e, urllib.error.HTTPError):
        return f"Le serveur a refusé la requête (HTTP {e.code})."
    if isinstance(e, (urllib.error.URLError, ConnectionError, TimeoutError)) \
            or "timed out" in low or "getaddrinfo" in low:
        return ("Pas de connexion Internet (ou le serveur ne répond pas). "
                "Vérifie ta connexion et réessaie.")
    if "certificate" in low or "ssl" in low:
        return ("Connexion sécurisée impossible (certificat). Un antivirus ou "
                "un proxy bloque peut-être la connexion.")
    if isinstance(e, OSError) and getattr(e, "errno", None) == 28 or "no space" in low:
        return "Plus d'espace disque. Libère de l'espace et réessaie."
    if isinstance(e, PermissionError):
        return (f"Accès refusé : {getattr(e, 'filename', '') or msg}. Choisis un "
                "autre dossier de sortie.")
    if isinstance(e, FileNotFoundError):
        return f"Fichier introuvable : {getattr(e, 'filename', '') or msg}"
    if "out of memory" in low or "cudaerrormemoryallocation" in low \
            or isinstance(e, MemoryError):
        return ("Pas assez de mémoire pour ce modèle. Essaie un modèle plus "
                "petit (medium ou large-v3-turbo) ou ferme d'autres programmes.")
    if "invalid data found" in low or "could not find codec" in low \
            or "no audio" in low or "avfilter" in low or e.__class__.__module__.startswith("av"):
        return ("Impossible de lire l'audio de cette vidéo. Le fichier est "
                "peut-être corrompu ou sans piste audio.")
    return f"Erreur inattendue : {msg or e.__class__.__name__}"


def report(e: BaseException, context: str = "") -> str:
    """Log l'erreur complète et retourne le message pour l'utilisateur."""
    log.error("%s", context or "Erreur", exc_info=(type(e), e, e.__traceback__))
    return friendly(e)
