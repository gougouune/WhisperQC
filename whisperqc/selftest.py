# -*- coding: utf-8 -*-
"""Auto-test sans interface : `WhisperQC --selftest`.

Utilisé par la CI sur l'app compilée pour attraper un module ou une lib
manquante (ctranslate2, PyAV, VAD onnx, tkdnd) avant de publier.
"""

import math
import os
import struct
import sys
import tempfile
import wave


def _make_wav(path, seconds=1.0, rate=16000):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / rate)))
                          for i in range(int(seconds * rate)))
        w.writeframes(frames)


def main() -> int:
    results = []

    def check(name, fn):
        try:
            detail = fn()
            results.append((True, name, detail or ""))
        except Exception as e:  # noqa: BLE001
            results.append((False, name, f"{e.__class__.__name__}: {e}"))

    def _ct2():
        import ctranslate2
        return ctranslate2.__version__

    def _decode():
        from faster_whisper.audio import decode_audio
        tmp = os.path.join(tempfile.mkdtemp(), "t.wav")
        _make_wav(tmp)
        a = decode_audio(tmp)
        assert 15000 < len(a) < 17000, len(a)
        return f"{len(a)} échantillons"

    def _vad():
        from faster_whisper.vad import get_speech_timestamps
        import numpy as np
        get_speech_timestamps(np.zeros(16000, dtype=np.float32))
        return "silero ok"

    def _tkdnd():
        import tkinterdnd2
        d = os.path.join(os.path.dirname(tkinterdnd2.__file__), "tkdnd")
        assert os.path.isdir(d), d
        return ", ".join(sorted(os.listdir(d)))

    def _gui_imports():
        import importlib
        import tkinter
        importlib.import_module("customtkinter")
        importlib.import_module("whisperqc.gui")
        return f"Tk {tkinter.TkVersion}"

    def _ssl():
        from whisperqc.platform_support import ssl_context
        ssl_context()
        import certifi
        assert os.path.isfile(certifi.where())
        return "certifi ok"

    def _srt_writer():
        import types
        from whisperqc.engine import iterate_subtitles
        W = types.SimpleNamespace
        seg = W(words=[W(start=i * 0.3, end=i * 0.3 + 0.25, word=" " + w) for i, w in
                       enumerate("Fait que toi, Dave, dans le fond, ce que tu m'expliques, "
                                 "c'est que t'as commencé à mettre de l'argent de côté.".split())])
        subs = iterate_subtitles([seg], 55, 1)
        assert subs and all(len(t) <= 55 for _, _, t in subs), subs
        return f"{len(subs)} sous-titres"

    check("ctranslate2", _ct2)
    check("décodage audio (PyAV)", _decode)
    check("VAD", _vad)
    check("tkdnd", _tkdnd)
    check("interface", _gui_imports)
    check("SSL", _ssl)
    check("écriture SRT", _srt_writer)

    # Test complet optionnel (dev) : WHISPERQC_SELFTEST_VIDEO=chemin.mp4
    video = os.environ.get("WHISPERQC_SELFTEST_VIDEO")
    if video:
        def _transcribe():
            from whisperqc import config, engine, logs, models
            logs.setup()
            config.ensure_dirs()
            model = next((m for m in ("large-v3-turbo", "small") if models.model_path(m)), "small")
            out = tempfile.mkdtemp()
            srt = engine.run_pipeline(video, model, 55, 1, out, None, None, False, lambda m: None)
            n = open(srt, encoding="utf-8").read().count("-->")
            assert n > 0, "SRT vide"
            return f"{model} sur {engine.current_device().label} : {n} sous-titres"
        check("transcription", _transcribe)

    ok = all(r[0] for r in results)
    lines = [f"{'OK ' if r[0] else 'ÉCHEC'}  {r[1]} : {r[2]}" for r in results]
    report = "\n".join(lines) + f"\n{'SELFTEST OK' if ok else 'SELFTEST ÉCHEC'}\n"
    out = os.environ.get("WHISPERQC_SELFTEST_OUT")
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(report)
    try:
        sys.stdout.write(report)
    except Exception:
        pass
    return 0 if ok else 1
