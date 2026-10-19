# WhisperQC 1.1.0

Version de stabilité. Mêmes onglets, mêmes réglages, même workflow : on glisse la vidéo et on reçoit le SRT. Rien de nouveau à apprendre.

## Nouveau

- **Version macOS** pour les Mac Apple Silicon (M1 à M4) et Intel. Il faut macOS 13 Ventura ou plus récent.
- **Ça marche sans carte NVIDIA.** WhisperQC détecte la machine tout seul. Avec une carte NVIDIA, il utilise le GPU. Sinon, il transcrit sur le processeur. Le log affiche l'appareil utilisé au démarrage.
- **Download beaucoup plus léger : environ 150–250 Mo au lieu de 3,9 Go.** Le modèle de transcription (1,6 Go pour large-v3-turbo) se télécharge une seule fois, au premier lancement, avec une barre de progression.
- **Module GPU NVIDIA en option sur Windows (≈ 1,1 Go).** Il est proposé au premier lancement si une carte NVIDIA est détectée. Si tu le refuses, l'app fonctionne quand même sur le CPU.

## Corrigé

- Les erreurs s'affichent maintenant en français clair, au lieu de « Erreur (code 1) » ou d'un message technique. Le détail complet est écrit dans un fichier journal :
  - Windows : `%LOCALAPPDATA%\WhisperQC\logs\whisperqc.log`
  - Mac : `~/Library/Logs/WhisperQC/whisperqc.log`
- Si le GPU NVIDIA plante (pilote trop vieux, par exemple), WhisperQC bascule tout seul sur le CPU au lieu d'échouer.
- L'app fonctionne même installée dans un dossier en lecture seule (Program Files, OneDrive, Applications sur Mac).
- Un avertissement s'affiche si l'app est lancée directement depuis l'intérieur du .zip sans l'avoir extrait.
- Onglet Corrections : une erreur réseau ou d'API bloquait le bouton sur « En cours… ». Corrigé.
- Correction IA : si la réponse de l'IA arrive coupée (SRT long), le SRT d'origine est conservé au lieu d'être remplacé par une version incomplète.
- Correction IA sur Mac : les connexions HTTPS fonctionnent dans l'app compilée.

## Changé (en coulisses)

- Le moteur de transcription est la librairie faster-whisper, au lieu de l'exécutable Faster-Whisper-XXL qui n'existe pas sur Mac. Les modèles sont les mêmes, les réglages par défaut de XXL sont repris et le découpage des sous-titres est reproduit. Sur nos vidéos test, on obtient le même texte et un nombre de sous-titres quasi identique.
- Le dossier SRT par défaut passe à **Documents/WhisperQC/SRT**. La v1 l'écrivait à côté de l'app.
- La clé API, la config et les modèles sont rangés dans le dossier utilisateur. Si tu extrais la nouvelle version par-dessus l'ancien dossier de la v1, ta clé API et les modèles déjà téléchargés sont repris automatiquement. Sinon, recolle ta clé une fois.
- L'app a maintenant son icône. Elle est livrée en dossier plutôt qu'en un seul .exe, ce qui donne un démarrage plus rapide et moins de faux positifs antivirus.

## Limites connues

- L'app n'est pas signée : Windows SmartScreen et macOS Gatekeeper affichent un avertissement au premier lancement (voir README_INSTALL.md).
- Sur Mac, la transcription se fait sur le processeur : il n'y a pas d'accélération GPU.
