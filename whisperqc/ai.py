# -*- coding: utf-8 -*-
"""Correction IA des SRT (Claude / OpenAI / Gemini) — repris tel quel de la v1."""

import json
import re
import urllib.request

from .platform_support import ssl_context


AI_PROMPT_POLISH = """Tu es un correcteur de sous-titres pour vidéos TikTok en français québécois.

Tu reçois un fichier SRT généré automatiquement par Whisper. Ton travail :

CORRIGER :
- Les mots mal transcrits ou qui sonnent pas québécois
- Les noms propres financiers (CÉLI, REER, CÉLIAP, SCHL, etc.)
- La ponctuation manquante ou incorrecte
- Les majuscules en début de phrase

NE PAS TOUCHER :
- Les numéros de blocs
- Les timestamps (jamais, même si le timing semble weird)
- Le nombre de blocs (pas de fusion, pas de séparation)
- Le style parlé québécois (faque, ben, là, t'as, etc.) — c'est voulu

RETOURNER :
Le fichier SRT complet corrigé, rien d'autre. Pas d'explication, pas de commentaires, pas de balises markdown."""

AI_PROMPT_CORRECTIONS = """Tu es un correcteur de sous-titres pour vidéos TikTok en français québécois.

Tu reçois un fichier SRT et une liste de commentaires de révision provenant de Frame.io.

Les commentaires contiennent un timecode et une description de la correction à faire.

TON TRAVAIL :
- Appliquer UNIQUEMENT les corrections qui touchent le TEXTE des sous-titres
- Ignorer complètement les commentaires de montage vidéo (coupes, vitesse, logo, silences, etc.)

EXEMPLES de corrections à appliquer :
- "ajouter le ne" → corriger la négation dans le sous-titre au timecode indiqué
- "remplacer ses par sur les" → modifier le texte
- "s'assurer que le mot soit sur la même ligne" → ajuster le texte du bloc

EXEMPLES de commentaires à IGNORER :
- "couper ce clip"
- "augmenter la vitesse de lecture"
- "ajout du logo à la fin"
- "couper les silences"
- "enlever ce clip"

NE PAS TOUCHER :
- Les numéros de blocs
- Les timestamps (jamais)
- Le nombre de blocs (pas de fusion, pas de séparation)

RETOURNER :
Le fichier SRT complet avec les corrections appliquées, rien d'autre. Pas d'explication, pas de commentaires, pas de balises markdown."""


# ── AI provider detection ───────────────────────────────────────────────────────

def detect_provider(key: str):
    key = key.strip()
    if key.startswith("sk-ant-"):
        return "claude"
    elif key.startswith("sk-") or key.startswith("sk-proj-"):
        return "openai"
    elif key.startswith("AIza"):
        return "gemini"
    return None

PROVIDER_LABELS = {
    "claude": "✓ Claude détecté",
    "openai": "✓ OpenAI détecté",
    "gemini": "✓ Gemini détecté",
}


# ── AI calls ───────────────────────────────────────────────────────────────────

def _http_post(url, headers, body):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30, context=ssl_context()) as resp:
        return json.loads(resp.read().decode("utf-8"))

def _call_claude(api_key, user_msg):
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": user_msg}],
    }
    resp = _http_post(url, headers, body)
    return resp["content"][0]["text"]

def _call_openai(api_key, user_msg):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {"model": "gpt-4o", "messages": [{"role": "user", "content": user_msg}], "max_tokens": 4096}
    resp = _http_post(url, headers, body)
    return resp["choices"][0]["message"]["content"]

def _call_gemini(api_key, user_msg):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    body = {"contents": [{"parts": [{"text": user_msg}]}], "generationConfig": {"maxOutputTokens": 4096}}
    resp = _http_post(url, headers, body)
    return resp["candidates"][0]["content"]["parts"][0]["text"]

def _call_ai(api_key, provider, user_msg):
    if provider == "claude":
        return _call_claude(api_key, user_msg)
    elif provider == "openai":
        return _call_openai(api_key, user_msg)
    elif provider == "gemini":
        return _call_gemini(api_key, user_msg)
    return None

def _clean_ai_output(text):
    text = re.sub(r"^```[a-z]*\n?", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"\n?```$", "", text.strip(), flags=re.MULTILINE)
    return text.strip()

_TIMING_LINE = re.compile(r"^\d{2}:\d{2}:\d{2},\d{3}\s*-->", re.MULTILINE)

def _count_blocks(srt_text):
    return len(_TIMING_LINE.findall(srt_text))

def ai_polish_srt(srt_path, api_key, provider, log_fn=None):
    with open(srt_path, encoding="utf-8") as f:
        srt_content = f.read()
    user_msg = f"{AI_PROMPT_POLISH}\n\nVoici le SRT à corriger :\n\n{srt_content}"
    try:
        result = _call_ai(api_key, provider, user_msg)
        if result:
            result = _clean_ai_output(result)
            # Garde-fou : une réponse coupée (SRT long > max_tokens) ou qui a
            # fusionné des blocs écraserait le SRT de base. On le garde alors.
            if _count_blocks(result) != _count_blocks(srt_content):
                if log_fn:
                    log_fn("⚠  Réponse IA incomplète (nombre de blocs différent)")
                return False
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(result)
            return True
    except Exception as e:
        if log_fn:
            log_fn(f"⚠  Erreur IA : {e}")
    return False

def ai_apply_corrections(srt_content, comments, api_key, provider):
    user_msg = f"{AI_PROMPT_CORRECTIONS}\n\nSRT :\n\n{srt_content}\n\n---\n\nCommentaires Frame.io :\n\n{comments}"
    result = _call_ai(api_key, provider, user_msg)
    if result:
        return _clean_ai_output(result)
    return None


