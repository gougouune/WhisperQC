# -*- coding: utf-8 -*-
"""Post-traitement SRT + auto-détection du SRT pour les commentaires Frame.io.
Repris tel quel de la v1."""

import os
import re

ELISIONS = {"c'", "j'", "m'", "t'", "s'", "l'", "d'", "n'", "qu'", "lorsqu'", "puisqu'", "quoiqu'"}

# ── SRT post-processor ─────────────────────────────────────────────────────────

CORRECTIONS = {
    r"\bCéliap\b":           "CÉLIAP",
    r"\bCéli[,\s]+Réaïr\b": "CÉLI-REER",
    r"\bRéaïr\b":            "REER",
    r"\bCéli\b":             "CÉLI",
    r"\bschl\b":             "SCHL",
    r"\bSCHL\b":             "SCHL",
    r"\bfaque\b":            "fait que",
    r"\bpis\b":              "puis",
}

MIN_CHARS = 12
MIN_DURATION_MS = 500

def ts_to_ms(ts):
    h, m, rest = ts.split(":")
    s, ms = rest.split(",")
    return int(h)*3600000 + int(m)*60000 + int(s)*1000 + int(ms)

def ms_to_ts(ms):
    ms = max(0, ms)
    h = ms//3600000; ms %= 3600000
    m = ms//60000;   ms %= 60000
    s = ms//1000;    ms %= 1000
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def apply_corrections(text):
    for pattern, replacement in CORRECTIONS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text

def parse_srt(path):
    with open(path, encoding="utf-8") as f:
        content = f.read()
    blocks = []
    pattern = re.compile(
        r"(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n([\s\S]*?)(?=\n\d+\s*\n|\Z)",
        re.MULTILINE
    )
    for m in pattern.finditer(content):
        text = m.group(4).strip().replace("\n", " ")
        if text:
            blocks.append((int(m.group(1)), m.group(2), m.group(3), text))
    return blocks

def smart_split(text, max_chars, max_lines):
    words = text.split()
    if not words:
        return text
    dehyph = []
    i = 0
    while i < len(words):
        w = words[i]
        if w.endswith('-') and i+1 < len(words):
            dehyph.append(w[:-1]+words[i+1]); i += 2
        else:
            dehyph.append(w); i += 1
    words = dehyph
    lines = []
    current = []
    current_len = 0
    for word in words:
        word_len = len(word)
        add_len = word_len + (1 if current else 0)
        if len(lines)+1 >= max_lines:
            current.append(word); current_len += add_len; continue
        if not current or current_len+add_len <= max_chars:
            current.append(word); current_len += add_len; continue
        ends_elision = current[-1].endswith("'")
        starts_elision = any(word.lower().startswith(e) for e in ELISIONS)
        if ends_elision or starts_elision:
            current.append(word); current_len += add_len
            lines.append(" ".join(current)); current = []; current_len = 0; continue
        lines.append(" ".join(current)); current = [word]; current_len = word_len
    if current:
        lines.append(" ".join(current))
    return "\n".join(lines)

def merge_blocks(blocks):
    merged = []
    i = 0
    while i < len(blocks):
        idx, start, end, text = blocks[i]
        while i+1 < len(blocks):
            words = text.split()
            last_word = words[-1] if words else ""
            _, _, next_end, next_text = blocks[i+1]
            next_words = next_text.split()
            next_first = next_words[0] if next_words else ""
            duration_ms = ts_to_ms(end) - ts_to_ms(start)
            should_merge = (
                last_word.endswith("'")
                or next_first.startswith("'")
                or (next_first.startswith("-") and len(next_first) > 1)
                or len(text.strip()) < MIN_CHARS
                or duration_ms < MIN_DURATION_MS
            )
            if should_merge:
                if next_first.startswith("'") and not last_word.endswith("'"):
                    text = text.rstrip() + next_first + (" "+" ".join(next_words[1:]) if len(next_words)>1 else "")
                elif next_first.startswith("-") and len(next_first)>1:
                    text = text.rstrip() + next_first + (" "+" ".join(next_words[1:]) if len(next_words)>1 else "")
                else:
                    text = text + " " + next_text
                end = next_end; i += 1
            else:
                break
        merged.append((idx, start, end, text)); i += 1
    return merged

def postprocess_srt(srt_path, max_chars, max_lines):
    blocks = parse_srt(srt_path)
    if not blocks:
        return
    merged = merge_blocks(blocks)
    corrected = [(idx, start, end, apply_corrections(text)) for idx, start, end, text in merged]
    lines_out = []
    for i, (idx, start, end, text) in enumerate(corrected, 1):
        lines_out.append(f"{i}\n{start} --> {end}\n{smart_split(text, max_chars, max_lines)}\n")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_out))


# ── SRT auto-detection ─────────────────────────────────────────────────────────

def _frameio_ts_to_ms(ts: str) -> int:
    """
    Convertit un timecode Frame.io ou SRT en millisecondes.
    Supporte : HH:MM:SS:FF (Frame.io 24fps), HH:MM:SS,mmm (SRT), HH:MM:SS.mmm
    """
    ts = ts.strip()
    # HH:MM:SS:FF — Frame.io (assume 24fps)
    m = re.match(r"(\d+):(\d+):(\d+):(\d+)$", ts)
    if m:
        h, mn, s, ff = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        return h*3600000 + mn*60000 + s*1000 + int(ff * 1000/24)
    # HH:MM:SS,mmm — SRT
    m = re.match(r"(\d+):(\d+):(\d+)[,.](\d+)$", ts)
    if m:
        h, mn, s, ms = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        return h*3600000 + mn*60000 + s*1000 + ms
    # HH:MM:SS
    m = re.match(r"(\d+):(\d+):(\d+)$", ts)
    if m:
        h, mn, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return h*3600000 + mn*60000 + s*1000
    return -1


def _extract_comment_signals(comments: str):
    """
    Extrait les signaux des commentaires Frame.io :
    - timecodes en ms
    - mots-clés de contenu (mots mentionnés comme corrections)
    Retourne (list[int], list[str])
    """
    # Timecodes : HH:MM:SS:FF ou [HH:MM:SS:FF - HH:MM:SS:FF]
    tc_pattern = re.compile(r"\d{2}:\d{2}:\d{2}[:,.]\d{2,3}")
    raw_tcs = tc_pattern.findall(comments)
    timecodes_ms = [_frameio_ts_to_ms(tc) for tc in raw_tcs if _frameio_ts_to_ms(tc) >= 0]

    # Mots entre guillemets ou après des mots-clés comme "remplacer X par Y", "ajouter X", "enlever X"
    keywords = []
    # Mots entre guillemets
    keywords += re.findall(r'"([^"]+)"', comments)
    keywords += re.findall(r"'([^']+)'", comments)
    # Pattern "remplacer X par Y" → X et Y
    for m in re.finditer(r"remplacer\s+(\w+)\s+par\s+(\w+)", comments, re.IGNORECASE):
        keywords += [m.group(1), m.group(2)]
    # Mots après "ajouter le/la/les", "enlever le/la/les"
    for m in re.finditer(r"(?:ajouter|enlever)\s+(?:le\s+|la\s+|les\s+)?(\w+)", comments, re.IGNORECASE):
        keywords.append(m.group(1))
    # Mots isolés en italique ou entre parenthèses
    keywords += re.findall(r"\(([^)]+)\)", comments)

    # Nettoyer — mots de 3+ chars, minuscules, pas de stopwords
    stopwords = {"que", "est", "pas", "sur", "les", "des", "une", "dans", "pour", "par", "mot", "même", "ligne", "plan", "soit"}
    clean_kw = [w.lower().strip() for kw in keywords for w in kw.split() if len(w) >= 3 and w.lower() not in stopwords]

    return timecodes_ms, clean_kw


def _score_srt_match(srt_path: str, timecodes_ms: list, keywords: list) -> dict:
    """
    Score un fichier SRT contre les signaux extraits des commentaires.
    Retourne un dict avec score, timecode_hits, keyword_hits, confidence.
    """
    try:
        blocks = parse_srt(srt_path)
    except Exception:
        return None

    if not blocks:
        return None

    # Index des timestamps SRT en ms
    srt_times = []
    for _, start, end, _ in blocks:
        srt_times.append(ts_to_ms(start))

    # Score timecodes : tolérance ±2000ms
    TOLERANCE = 2000
    tc_hits = 0
    for tc_ms in timecodes_ms:
        if any(abs(tc_ms - srt_ms) <= TOLERANCE for srt_ms in srt_times):
            tc_hits += 1

    # Score contenu : chercher les keywords dans le texte des blocs proches des timecodes
    srt_text_full = " ".join(text.lower() for _, _, _, text in blocks)
    kw_hits = sum(1 for kw in keywords if kw in srt_text_full)

    # Score total pondéré
    tc_ratio = tc_hits / max(len(timecodes_ms), 1)
    kw_ratio = kw_hits / max(len(keywords), 1)
    score = tc_ratio * 0.6 + kw_ratio * 0.4

    # Confiance — les timecodes ont plus de poids que les keywords
    if tc_ratio >= 0.7:
        confidence = "haute"
    elif tc_ratio >= 0.5:
        confidence = "moyenne"
    elif tc_ratio >= 0.3:
        confidence = "faible"
    else:
        confidence = None

    return {
        "score": score,
        "tc_hits": tc_hits,
        "tc_total": len(timecodes_ms),
        "kw_hits": kw_hits,
        "kw_total": len(keywords),
        "confidence": confidence,
    }


def find_matching_srt(comments: str, srt_folder: str) -> tuple:
    """
    Cherche le meilleur SRT dans srt_folder qui correspond aux commentaires.
    Retourne (srt_path, score_dict) ou (None, None) si aucun match acceptable.
    """
    if not os.path.isdir(srt_folder):
        return None, None

    srt_files = [f for f in os.listdir(srt_folder) if f.lower().endswith(".srt")]
    if not srt_files:
        return None, None

    timecodes_ms, keywords = _extract_comment_signals(comments)
    if not timecodes_ms:
        return None, None

    best_path = None
    best_score = None

    for fname in srt_files:
        fpath = os.path.join(srt_folder, fname)
        result = _score_srt_match(fpath, timecodes_ms, keywords)
        if result and result["confidence"] and (best_score is None or result["score"] > best_score["score"]):
            best_path = fpath
            best_score = result

    return best_path, best_score


