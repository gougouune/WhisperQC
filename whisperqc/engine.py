# -*- coding: utf-8 -*-
"""Transcription avec la lib faster-whisper (remplace faster-whisper-xxl.exe).

Les paramètres reprennent les défauts de Faster-Whisper-XXL 1.1.1 (beam 5,
patience 2, VAD silero seuil 0.45 / pad 900 ms / silence 3 s, timestamps par
mot) et l'écriture SRT reproduit --max_line_width / --max_line_count.
Le post-traitement QC et la correction IA de la v1 s'appliquent ensuite.
"""

import os
import threading
import time
from pathlib import Path

from . import gpu, models
from .logs import UserError, log
from .ai import ai_polish_srt
from .srt import postprocess_srt

INITIAL_PROMPT = "Transcription en français québécois."

_TRANSCRIBE_OPTS = dict(
    language="fr",
    task="transcribe",
    initial_prompt=INITIAL_PROMPT,
    beam_size=5,
    best_of=5,
    patience=2.0,
    temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
    compression_ratio_threshold=2.4,
    log_prob_threshold=-1.0,
    no_speech_threshold=0.6,
    condition_on_previous_text=True,
    prompt_reset_on_temperature=0.5,
    max_initial_timestamp=1.0,
    suppress_tokens=[-1],
    word_timestamps=True,
    vad_filter=True,
    vad_parameters=dict(threshold=0.45, min_speech_duration_ms=250,
                        min_silence_duration_ms=3000, speech_pad_ms=900),
)

_lock = threading.Lock()
_cache = {"key": None, "model": None}
_device = None


def current_device() -> gpu.Device:
    global _device
    if _device is None:
        _device = gpu.detect()
        log.info("Appareil : %s", _device.label)
    return _device


def reset_device() -> None:
    """Après l'installation du module GPU."""
    global _device
    _device = None
    _cache.update(key=None, model=None)


def _load(path: Path, dev: gpu.Device):
    from faster_whisper import WhisperModel
    key = (str(path), dev.device, dev.compute_type)
    if _cache["key"] != key:
        _cache.update(key=None, model=None)
        threads = 0 if dev.device == "cuda" else max(1, (os.cpu_count() or 4))
        _cache["model"] = WhisperModel(str(path), device=dev.device,
                                       compute_type=dev.compute_type,
                                       cpu_threads=threads)
        _cache["key"] = key
    return _cache["model"]


def _is_cuda_error(e: Exception) -> bool:
    s = str(e).lower()
    return any(k in s for k in ("cuda", "cublas", "cudnn", "nvidia", "gpu"))


def _fmt_short(t: float) -> str:
    m, s = divmod(max(0.0, t), 60)
    return f"{int(m):02}:{s:06.3f}"


def _quote_tokens(model) -> list:
    """IDs des tokens contenant « ou ». Avec le prompt initial, le modèle
    part parfois en mode « citation » et saute des répliques entières ;
    XXL ne le fait pas. Interdire ces tokens règle le problème."""
    if not hasattr(model, "_wqc_quote_ids"):
        ids = []
        try:
            for piece, i in model.hf_tokenizer.get_vocab().items():
                text = model.hf_tokenizer.decode([i])
                if "«" in text or "»" in text:
                    ids.append(i)
        except Exception:
            log.exception("Tokens guillemets")
        model._wqc_quote_ids = sorted(ids)
    return model._wqc_quote_ids


def _run(path: Path, dev: gpu.Device, video: str, log_fn):
    model = _load(path, dev)
    opts = dict(_TRANSCRIBE_OPTS, suppress_tokens=[-1] + _quote_tokens(model))
    segments, info = model.transcribe(video, **opts)
    out = []
    for seg in segments:
        out.append(seg)
        if log_fn:
            log_fn(f"[{_fmt_short(seg.start)} --> {_fmt_short(seg.end)}] {seg.text.strip()}")
    return out, info


def transcribe(video: str, model: str, max_chars: int, max_lines: int,
               output_dir: str | None = None, log_fn=None,
               download_progress=None) -> str:
    """Transcrit une vidéo -> chemin du SRT (même nom que la vidéo).
    log_fn(line) : lignes pour le log de l'app.
    download_progress(done, total) : pendant le téléchargement du modèle."""
    global _device
    if not os.path.isfile(video):
        raise UserError(f"Vidéo introuvable : {video}")

    out_dir = output_dir or os.path.dirname(video)
    try:
        os.makedirs(out_dir, exist_ok=True)
    except OSError as e:
        raise UserError(f"Impossible de créer le dossier de sortie : {out_dir} ({e.strerror})")
    base = os.path.splitext(os.path.basename(video))[0]
    srt_path = os.path.join(out_dir, base + ".srt")

    with _lock:
        path = models.model_path(model)
        if path is None:
            if log_fn:
                log_fn(f"⬇  Téléchargement du modèle {model} "
                       f"({models.APPROX_SIZE.get(model, '')}) — une seule fois…")
            path = models.ensure_model(model, progress=download_progress, log_fn=log_fn)
            if log_fn:
                log_fn("✓  Modèle téléchargé")

        dev = current_device()
        if log_fn:
            log_fn(f"   Appareil : {dev.label}")
        t0 = time.time()
        try:
            segments, info = _run(path, dev, video, log_fn)
        except Exception as e:
            if dev.device != "cuda" or not _is_cuda_error(e):
                raise
            log.exception("Échec GPU, bascule CPU")
            if log_fn:
                log_fn("⚠  Le GPU NVIDIA n'a pas fonctionné (pilote trop vieux ?). "
                       "Bascule sur le CPU — plus lent.")
            _device = gpu.Device("cpu", "int8", "CPU (int8)")
            segments, info = _run(path, _device, video, log_fn)

        log.info("Transcription %s : %.1fs audio en %.1fs (%s, %s)", base,
                 info.duration, time.time() - t0, model, _device.label if _device else "")

    if not segments:
        raise UserError("Aucune parole détectée dans cette vidéo.")
    write_srt(segments, srt_path, max_chars, max_lines)
    return srt_path


# ── Écriture SRT (reproduit le découpage de Faster-Whisper-XXL) ───────────────
#
# Observé sur la sortie de XXL r245.4 avec --max_line_width/--max_line_count :
#  - chaque segment whisper commence un nouveau sous-titre ;
#  - dans un segment, on coupe d'abord après la ponctuation (, ; : . ? !) et on
#    regroupe les bouts tant que la ligne reste sous max_line_width ;
#  - un bout trop long est coupé en parts à peu près égales.

_BREAK_PUNCT = (",", ";", ":", ".", "?", "!", "…")
_MIN_LINE = 12


def _ts(t: float) -> str:
    ms = int(round(max(0.0, t) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def _text(words) -> str:
    # Les "mots" de whisper portent leur espace devant (" m", "'expliques")
    return "".join(w[2] for w in words).strip()


def _clauses(words):
    out, cur = [], []
    for w in words:
        cur.append(w)
        if w[2].rstrip().endswith(_BREAK_PUNCT):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def _split_even(words, width):
    """Coupe une suite de mots trop longue en n parts d'environ len/n chars
    (coupure au mot le plus proche de la cible)."""
    n = -(-len(_text(words)) // width)  # ceil
    pieces = []
    rest = list(words)
    for k in range(n, 1, -1):
        target = len(_text(rest)) / k
        cur = [rest.pop(0)]
        while len(rest) > 1:
            longer = len(_text(cur + rest[:1]))
            if abs(longer - target) > abs(len(_text(cur)) - target) or longer >= width:
                break
            cur.append(rest.pop(0))
        pieces.append(cur)
    if rest:
        pieces.append(rest)
    return pieces


def _segment_lines(words, width):
    lines, cur = [], []
    for clause in _clauses(words):
        if cur and (len(_text(cur + clause)) < width - 1 or len(_text(cur)) < _MIN_LINE):
            # Un bout très court (« là, », « Maintenant, ») reste avec la suite
            cur = cur + clause
            if len(_text(cur)) >= width:
                *done, cur = _split_even(cur, width)
                lines.extend(done)
            continue
        if cur:
            lines.append(cur)
        cur = clause
        if len(_text(cur)) >= width:
            *done, cur = _split_even(cur, width)
            lines.extend(done)
    if cur:
        lines.append(cur)
    return lines


def iterate_subtitles(segments, max_line_width: int, max_line_count: int):
    """Retourne [(start, end, text)] ; les lignes de text sont séparées par
    des retours à la ligne."""
    subs = []
    for seg in segments:
        words = []
        for w in (seg.words or []):
            if not w.word.strip():
                continue
            if words and not w.word[:1].isspace():
                # « 'aise » collé à « l » : on ne coupe jamais au milieu
                s, _, t = words[-1]
                words[-1] = (s, w.end, t + w.word)
            else:
                words.append((w.start, w.end, w.word))
        if not words:
            continue
        lines = _segment_lines(words, max_line_width)
        for i in range(0, len(lines), max(1, max_line_count)):
            group = lines[i:i + max_line_count]
            subs.append((group[0][0][0], group[-1][-1][1],
                         "\n".join(_text(l) for l in group)))
    return subs


def write_srt(segments, srt_path: str, max_chars: int, max_lines: int) -> None:
    subs = iterate_subtitles(segments, max_chars, max_lines)
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, (start, end, text) in enumerate(subs, 1):
            f.write(f"{i}\n{_ts(start)} --> {_ts(end)}\n{text.replace('-->', '->')}\n\n")


def run_pipeline(video, model, max_chars, max_lines, output_dir, api_key,
                 provider, use_ai, log_fn, download_progress=None) -> str:
    """Transcription + post-traitement + correction IA (même séquence que la v1)."""
    srt_path = transcribe(video, model, max_chars, max_lines, output_dir,
                          log_fn=log_fn, download_progress=download_progress)
    log_fn("⚙  Post-traitement des captions…")
    try:
        postprocess_srt(srt_path, max_chars, max_lines)
    except Exception as e:
        log.exception("Post-traitement")
        log_fn(f"⚠  Post-traitement échoué: {e}")
    if use_ai:
        log_fn(f"🤖  Correction IA en cours ({provider})…")
        try:
            success = ai_polish_srt(srt_path, api_key, provider, log_fn=log_fn)
            log_fn("✓  Correction IA appliquée" if success
                   else "⚠  Correction IA échouée — SRT de base conservé")
        except Exception as e:
            log.exception("Correction IA")
            log_fn(f"⚠  Erreur IA : {e}")
    return srt_path
