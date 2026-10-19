# Installer WhisperQC

WhisperQC transforme ta vidéo en sous-titres québécois (.srt) prêts à importer dans CapCut.

## Quel fichier télécharger ?

| Ton ordi | Fichier |
|---|---|
| Windows 10 ou 11 | `WhisperQC-…-Windows.zip` |
| Mac avec puce Apple (M1, M2, M3, M4…) | `WhisperQC-…-macOS-AppleSilicon.dmg` |
| Mac avec processeur Intel | `WhisperQC-…-macOS-Intel.dmg` |

Pour savoir quel Mac tu as : menu  → **À propos de ce Mac**. Si tu vois « Puce Apple M… », prends Apple Silicon. Si tu vois « Processeur … Intel », prends Intel.

---

## Windows

### 1. Télécharger

Ton navigateur peut afficher un avertissement, parce que l'app est gratuite et n'est pas « signée » (un certificat payant) :

- **Edge** : « … n'est pas fréquemment téléchargé » → clique sur **…** → **Conserver** → **Afficher plus** → **Conserver quand même**.
- **Chrome** : clique sur **Conserver** dans la liste des téléchargements.

### 2. Extraire le zip (important)

Fais un clic droit sur le fichier `.zip` → **Extraire tout…** → **Extraire**.

⚠️ Ne lance pas l'app directement depuis l'intérieur du zip, sinon rien ne sera sauvegardé. Une fois extrait, tu peux déplacer le dossier `WhisperQC` où tu veux, par exemple dans Documents.

### 3. Premier lancement : l'avertissement SmartScreen

Ouvre le dossier `WhisperQC` et double-clique sur **WhisperQC.exe**.

Si un écran bleu indique « Windows a protégé votre ordinateur » :

1. Clique sur **Informations complémentaires**.
2. Clique sur **Exécuter quand même**.

Windows ne le redemandera plus pour cette version.

> Si ton antivirus met le fichier en quarantaine, c'est un faux positif fréquent avec les apps Python non signées. Ajoute le dossier WhisperQC aux exceptions de l'antivirus.

### 4. Carte NVIDIA (facultatif)

Si ton ordi a une carte graphique NVIDIA, WhisperQC propose de télécharger le **module GPU** (≈ 1,1 Go, une seule fois). Ça rend la transcription beaucoup plus rapide. Tu peux dire non : l'app fonctionne quand même sur le processeur.

---

## Mac

### 1. Installer

Ouvre le fichier `.dmg`, puis glisse **WhisperQC** dans le dossier **Applications**.

### 2. Premier lancement : l'avertissement Gatekeeper

L'app n'est pas signée par Apple (ça coûte 99 $ US par année). macOS va donc la bloquer la première fois. La façon de l'ouvrir dépend de ta version de macOS.

**macOS 15 Sequoia et plus récent :**

1. Double-clique sur WhisperQC. Un message dit que l'app ne peut pas être vérifiée. Clique sur **Terminé**.
2. Ouvre **Réglages Système** → **Confidentialité et sécurité**.
3. Descends jusqu'à « WhisperQC a été bloqué… » et clique sur **Ouvrir quand même**.
4. Confirme avec ton mot de passe, puis clique sur **Ouvrir quand même**.

**macOS 13 Ventura ou 14 Sonoma :**

1. Dans Applications, fais un **clic droit** (ou Control-clic) sur WhisperQC → **Ouvrir**.
2. Clique sur **Ouvrir** dans la fenêtre qui apparaît.

Ces étapes se font une seule fois. Ensuite, WhisperQC s'ouvre normalement.

**Si rien ne marche**, ouvre l'app **Terminal**, colle cette ligne, puis appuie sur Entrée :

```
xattr -dr com.apple.quarantine /Applications/WhisperQC.app
```

### 3. Accès aux dossiers

macOS te demandera si WhisperQC peut accéder à **Documents** (c'est là que les SRT sont enregistrés), au Bureau ou aux Téléchargements, selon l'endroit où sont tes vidéos. Clique sur **Autoriser**.

---

## Premier lancement (Windows et Mac)

À la première transcription, WhisperQC télécharge le modèle de reconnaissance vocale : **1,6 Go** pour large-v3-turbo, le modèle recommandé. La barre de progression indique où ça en est. Ça se fait une seule fois. Ensuite, WhisperQC fonctionne sans Internet, sauf la correction IA, qui a besoin d'Internet.

Tes SRT sont enregistrés par défaut dans **Documents/WhisperQC/SRT**. Tu peux choisir un autre dossier dans l'app.

---

## Configuration minimale

| | Minimum | Recommandé |
|---|---|---|
| **Windows** | Windows 10 64 bits, 8 Go de RAM | Windows 11, 16 Go de RAM, carte NVIDIA (GTX 1060 ou plus récente, pilote à jour) |
| **Mac** | macOS 13 Ventura, 8 Go de RAM | Puce Apple M1 ou plus récente, 16 Go de RAM |
| **Espace disque** | 3 Go (app + modèle large-v3-turbo) | 6 Go si tu utilises aussi le modèle large-v3 |
| **Internet** | Pour le premier téléchargement du modèle et pour la correction IA | |

## Temps de transcription attendus

Temps pour une **vidéo de 1 minute** avec le modèle **large-v3-turbo** (recommandé). Ce sont des ordres de grandeur : ça dépend de l'ordi.

| Machine | Temps |
|---|---|
| Windows + carte NVIDIA (RTX) | ~ 5 à 15 secondes |
| Ordi de bureau, processeur 12 cœurs, sans NVIDIA | ~ 50 secondes (mesuré sur un Ryzen 9 5900X) |
| Portable récent (8 cœurs), sans NVIDIA | ~ 1 à 2 minutes |
| Portable plus ancien (4 cœurs) | ~ 3 à 5 minutes |
| Mac Apple Silicon (M1 à M4) | ~ 1 à 2 minutes |
| Mac Intel | ~ 3 à 5 minutes |

Sans carte NVIDIA, compte grosso modo **1 à 5 minutes de calcul par minute de vidéo**. C'est normal : laisse l'app travailler.

Le modèle **large-v3** est environ 3 à 4 fois plus lent. **medium** et **small** sont plus rapides, mais moins précis sur l'accent québécois.

---

## Problèmes ?

- **Le message en rouge dans l'app** explique quoi faire dans la plupart des cas.
- **Le journal** (à joindre si tu m'écris) :
  - Windows : `%LOCALAPPDATA%\WhisperQC\logs\whisperqc.log`. Colle ce chemin dans la barre d'adresse de l'Explorateur de fichiers.
  - Mac : `~/Library/Logs/WhisperQC/whisperqc.log`. Dans le Finder : menu Aller → Aller au dossier…
- **Désinstaller** :
  - Windows : supprime le dossier WhisperQC, plus `%LOCALAPPDATA%\WhisperQC` (modèles) et `%APPDATA%\WhisperQC` (config).
  - Mac : mets l'app à la corbeille, puis supprime `~/Library/Application Support/WhisperQC`.
