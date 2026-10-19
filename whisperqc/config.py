# -*- coding: utf-8 -*-
"""Constantes de l'app et config utilisateur (config.json dans le dossier
utilisateur, plus à côté de l'exe)."""

import json
import shutil

from . import platform_support as plat

LOGO_PATH = plat.resource_dir() / "assets" / "simon_gagnon_logo.png"
CONFIG_PATH = plat.config_dir() / "config.json"
SRT_DIR = plat.default_srt_dir()
WEBSITE = "https://simon-gagnon.com"

MODELS = [
    ("large-v3-turbo", "Rapide · Excellent pour le québécois  ✓ Recommandé"),
    ("large-v3",       "Lent · Précision maximale"),
    ("medium",         "Très rapide · Moins précis sur les accents du Québec"),
    ("small",          "Ultra rapide · Pour tester seulement"),
]
MODEL_NAMES = [m[0] for m in MODELS]

CAPTION_LENGTHS = [
    ("Court",  "Style TikTok",        35, 1),
    ("Moyen",  "Bon équilibre ✓",     55, 1),
    ("Long",   "Style sous-titres",   80, 2),
]


def ensure_dirs() -> list:
    """Crée les dossiers utilisateur. Retourne la liste des erreurs (vide si OK)."""
    errors = []
    for d in (plat.config_dir(), plat.data_dir(), plat.log_dir(), SRT_DIR):
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            errors.append(f"{d} : {e.strerror or e}")
    _migrate_legacy_config()
    return errors


def _migrate_legacy_config() -> None:
    """La v1 gardait config.json à côté de l'exe : on le reprend une fois."""
    old = plat.legacy_paths()["config"]
    if CONFIG_PATH.exists() or not old.is_file():
        return
    try:
        shutil.copy2(old, CONFIG_PATH)
    except OSError:
        pass


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_config(data: dict) -> None:
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass
