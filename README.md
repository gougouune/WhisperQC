# WhisperQC (développement)

App de transcription en français québécois → SRT pour CapCut. Un seul code pour Windows et macOS.
Le guide utilisateur est dans [README_INSTALL.md](README_INSTALL.md), les changements dans [CHANGELOG.md](CHANGELOG.md).

## Structure

```
run.py                     point d'entrée (GUI ; --selftest pour la CI)
whisperqc/
  platform_support.py      TOUT ce qui diffère Windows / macOS (dossiers, DLL CUDA, SSL…)
  config.py                constantes UI (modèles, longueurs) + config.json utilisateur
  gui.py                   interface v1 reprise telle quelle (Générer + Corrections)
  engine.py                transcription faster-whisper + écriture SRT façon XXL
  gpu.py                   détection CUDA / CPU + module GPU NVIDIA téléchargeable
  models.py                modèles HF (mêmes dépôts que XXL), téléchargés au 1er usage
  download.py              téléchargements HTTP (progression, SHA-256)
  srt.py                   post-traitement QC + matching Frame.io (v1, inchangé)
  ai.py                    correction IA Claude/OpenAI/Gemini (v1 + garde-fou)
  logs.py                  journal fichier + messages d'erreur en français
  selftest.py              auto-test sans interface
WhisperQC.spec             PyInstaller (Windows : dossier ; macOS : .app)
build/build_windows.bat    build local Windows -> dist/WhisperQC-<ver>-Windows.zip
.github/workflows/release.yml   build Windows + macOS (arm64, Intel) sur tag v*
```

## Dev

```
py -3.11 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python run.py
```

## Publier une version

1. Mettre à jour `__version__` dans `whisperqc/__init__.py` et `CHANGELOG.md`.
2. `git tag v1.1.0 && git push origin main v1.1.0`
3. GitHub Actions build les 3 versions et crée une Release **en brouillon** : vérifier puis publier.

Build Windows local sans GitHub : `build\build_windows.bat`.

## Où l'app écrit

| | Windows | macOS |
|---|---|---|
| Config (clé API) | `%APPDATA%\WhisperQC\config.json` | `~/Library/Application Support/WhisperQC/config.json` |
| Modèles | `%LOCALAPPDATA%\WhisperQC\models` | `~/Library/Application Support/WhisperQC/models` |
| Module GPU | `%LOCALAPPDATA%\WhisperQC\cuda` | — |
| Journal | `%LOCALAPPDATA%\WhisperQC\logs` | `~/Library/Logs/WhisperQC` |
| SRT (défaut) | `Documents\WhisperQC\SRT` | `~/Documents/WhisperQC/SRT` |
