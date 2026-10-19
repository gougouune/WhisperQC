# -*- coding: utf-8 -*-
"""Interface WhisperQC — reprise de la v1 à l'identique (onglets Générer +
Corrections). Seul le lancement de la transcription change : la lib
faster-whisper remplace faster-whisper-xxl.exe."""

import os
import threading
import tkinter as tk
import urllib.error
import webbrowser
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image
from tkinterdnd2 import TkinterDnD, DND_FILES

from . import engine, gpu, logs
from . import platform_support as plat
from .ai import PROVIDER_LABELS, ai_apply_corrections, detect_provider
from .config import (CAPTION_LENGTHS, LOGO_PATH, MODEL_NAMES, MODELS, SRT_DIR,
                     WEBSITE, load_config, save_config)
from .srt import find_matching_srt

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

SRT_DIR = str(SRT_DIR)
LOGO_PATH = str(LOGO_PATH)


class WhisperQC(ctk.CTk, TkinterDnD.DnDWrapper):
    TkVersion = tk.TkVersion

    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)
        self.title("Whisper QC")
        self.resizable(True, True)
        self.option_add("*bell", False)

        self.video_path = tk.StringVar()
        self.output_path = tk.StringVar(value=SRT_DIR)
        self.model_index = tk.IntVar(value=0)
        self.caption_index = tk.IntVar(value=1)
        self.ai_enabled = tk.BooleanVar(value=False)
        self.api_key_var = tk.StringVar()

        cfg = load_config()
        saved_key = cfg.get("api_key", "")
        if saved_key:
            self.api_key_var.set(saved_key)
            self.ai_enabled.set(True)

        self._build_ui()

        self.update_idletasks()
        w = self.winfo_reqwidth() + 60
        h = self.winfo_reqheight() + 80
        self.geometry(f"{max(w, 680)}x{max(h, 900)}")
        self.minsize(max(w, 680), max(h, 900))

        if saved_key:
            self._on_key_change()

    def _open_website(self, event=None):
        webbrowser.open(WEBSITE)

    def _on_key_change(self, *args):
        key = self.api_key_var.get().strip()
        provider = detect_provider(key)
        if provider:
            self.provider_label.configure(text=PROVIDER_LABELS[provider], text_color=("#2d7d2d","#4caf50"))
            self.ai_enabled.set(True)
            cfg = load_config(); cfg["api_key"] = key; save_config(cfg)
        elif key == "":
            self.provider_label.configure(text="", text_color=("gray50","gray55"))
            self.ai_enabled.set(False)
        else:
            self.provider_label.configure(text="Clé non reconnue…", text_color=("gray50","gray55"))
            self.ai_enabled.set(False)

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── Header (commun aux deux onglets) ──
        header_row = ctk.CTkFrame(self, fg_color="transparent")
        header_row.grid(row=0, column=0, padx=36, pady=(32, 0), sticky="ew")
        header_row.grid_columnconfigure(0, weight=1)

        text_block = ctk.CTkFrame(header_row, fg_color="transparent")
        text_block.grid(row=0, column=0, sticky="w")

        top_line = ctk.CTkFrame(text_block, fg_color="transparent")
        top_line.pack(anchor="w")
        ctk.CTkLabel(top_line, text="WHISPER QC", font=ctk.CTkFont(family="Courier New", size=11), text_color=("gray50","gray55")).pack(side="left")
        ctk.CTkLabel(top_line, text="  ·  un ti projet par ", font=ctk.CTkFont(family="Courier New", size=11), text_color=("gray60","gray50")).pack(side="left")
        credit_link = ctk.CTkLabel(top_line, text="Simon Gagnon", font=ctk.CTkFont(family="Courier New", size=11), text_color=("#1a6fbf","#5aabf0"), cursor="hand2")
        credit_link.pack(side="left")
        credit_link.bind("<Button-1>", self._open_website)

        ctk.CTkLabel(text_block, text="Captions québécoises", font=ctk.CTkFont(size=26, weight="bold")).pack(anchor="w", pady=(4,2))
        ctk.CTkLabel(text_block, text="Glisse ta vidéo. Reçois ton SRT. C'est toute.", font=ctk.CTkFont(size=13), text_color=("gray50","gray55")).pack(anchor="w")

        if os.path.exists(LOGO_PATH):
            try:
                pil_img = Image.open(LOGO_PATH)
                logo_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(72,72))
                logo_lbl = ctk.CTkLabel(header_row, image=logo_img, text="", cursor="hand2")
                logo_lbl.grid(row=0, column=1, padx=(16,0), sticky="ne")
                logo_lbl.bind("<Button-1>", self._open_website)
            except Exception:
                pass

        # ── Tabs ──
        self.tabs = ctk.CTkTabview(self, corner_radius=10)
        self.tabs.grid(row=1, column=0, padx=36, pady=(20, 36), sticky="nsew")
        self.tabs.add("🎙  Générer")
        self.tabs.add("✏️  Corrections")

        self._build_tab_generate(self.tabs.tab("🎙  Générer"))
        self._build_tab_corrections(self.tabs.tab("✏️  Corrections"))

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 1 — Générer
    # ─────────────────────────────────────────────────────────────────────────

    def _build_tab_generate(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(6, weight=1)

        # Drop zone
        self.drop_frame = ctk.CTkFrame(tab, height=130, border_width=2, border_color=("gray70","gray40"), fg_color=("gray95","gray17"), corner_radius=12)
        self.drop_frame.grid(row=0, column=0, pady=(12,20), sticky="ew")
        self.drop_frame.grid_propagate(False)
        self.drop_frame.grid_columnconfigure(0, weight=1)
        self.drop_frame.grid_rowconfigure(0, weight=1)

        inner = ctk.CTkFrame(self.drop_frame, fg_color="transparent")
        inner.grid(row=0, column=0)
        self.drop_icon = ctk.CTkLabel(inner, text="▶", font=ctk.CTkFont(size=24), text_color=("gray55","gray50"))
        self.drop_icon.pack()
        self.drop_label = ctk.CTkLabel(inner, text="Glisse ta vidéo ici", font=ctk.CTkFont(size=14, weight="bold"))
        self.drop_label.pack(pady=(6,2))
        self.drop_sub = ctk.CTkLabel(inner, text="ou clique pour sélectionner  ·  mp4, mov, mkv, avi", font=ctk.CTkFont(size=11), text_color=("gray50","gray55"))
        self.drop_sub.pack()
        for w in [self.drop_frame, inner, self.drop_icon, self.drop_label, self.drop_sub]:
            w.bind("<Button-1>", lambda e: self._browse_video())
        self.drop_frame.drop_target_register(DND_FILES)
        self.drop_frame.dnd_bind("<<Drop>>", self._on_drop)

        # Output folder
        out_row = ctk.CTkFrame(tab, fg_color="transparent")
        out_row.grid(row=1, column=0, sticky="ew")
        out_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(out_row, text="Dossier de sortie", font=ctk.CTkFont(size=12), text_color=("gray50","gray55")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0,4))
        self.output_entry = ctk.CTkEntry(out_row, textvariable=self.output_path, placeholder_text="Même dossier que la vidéo par défaut", height=36)
        self.output_entry.grid(row=1, column=0, sticky="ew", padx=(0,8))
        ctk.CTkButton(out_row, text="Parcourir", width=90, height=36, fg_color=("gray85","gray25"), text_color=("gray20","gray90"), hover_color=("gray75","gray30"), command=self._browse_output).grid(row=1, column=1)

        # Model
        model_frame = ctk.CTkFrame(tab, fg_color="transparent")
        model_frame.grid(row=2, column=0, pady=(20,0), sticky="ew")
        model_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(model_frame, text="Modèle", font=ctk.CTkFont(size=12), text_color=("gray50","gray55")).grid(row=0, column=0, sticky="w", pady=(0,6))
        for i, (name, desc) in enumerate(MODELS):
            row_f = ctk.CTkFrame(model_frame, fg_color="transparent")
            row_f.grid(row=i+1, column=0, sticky="ew", pady=3)
            row_f.grid_columnconfigure(1, weight=1)
            rb = ctk.CTkRadioButton(row_f, text="", variable=self.model_index, value=i, width=24)
            rb.grid(row=0, column=0, rowspan=2, padx=(0,8))
            nl = ctk.CTkLabel(row_f, text=name, font=ctk.CTkFont(size=13, weight="bold"), anchor="w")
            nl.grid(row=0, column=1, sticky="w")
            nl.bind("<Button-1>", lambda e, idx=i: self.model_index.set(idx))
            dl = ctk.CTkLabel(row_f, text=desc, font=ctk.CTkFont(size=11), text_color=("gray50","gray55"), anchor="w")
            dl.grid(row=1, column=1, sticky="w")
            dl.bind("<Button-1>", lambda e, idx=i: self.model_index.set(idx))

        # Caption length
        cap_frame = ctk.CTkFrame(tab, fg_color="transparent")
        cap_frame.grid(row=3, column=0, pady=(20,0), sticky="ew")
        cap_frame.grid_columnconfigure((0,1,2), weight=1)
        ctk.CTkLabel(cap_frame, text="Longueur des captions", font=ctk.CTkFont(size=12), text_color=("gray50","gray55")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0,8))
        for i, (label, desc, _, __) in enumerate(CAPTION_LENGTHS):
            col_f = ctk.CTkFrame(cap_frame, fg_color="transparent")
            col_f.grid(row=1, column=i, sticky="w", padx=(0,20))
            rb = ctk.CTkRadioButton(col_f, text="", variable=self.caption_index, value=i, width=24)
            rb.grid(row=0, column=0, padx=(0,6))
            txt_f = ctk.CTkFrame(col_f, fg_color="transparent")
            txt_f.grid(row=0, column=1)
            nl = ctk.CTkLabel(txt_f, text=label, font=ctk.CTkFont(size=13, weight="bold"), anchor="w")
            nl.pack(anchor="w")
            nl.bind("<Button-1>", lambda e, idx=i: self.caption_index.set(idx))
            dl = ctk.CTkLabel(txt_f, text=desc, font=ctk.CTkFont(size=11), text_color=("gray50","gray55"), anchor="w")
            dl.pack(anchor="w")
            dl.bind("<Button-1>", lambda e, idx=i: self.caption_index.set(idx))

        # AI section
        ai_frame = ctk.CTkFrame(tab, fg_color=("gray92","gray18"), corner_radius=10)
        ai_frame.grid(row=4, column=0, pady=(20,0), sticky="ew")
        ai_frame.grid_columnconfigure(0, weight=1)
        ai_hdr = ctk.CTkFrame(ai_frame, fg_color="transparent")
        ai_hdr.grid(row=0, column=0, padx=16, pady=(14,6), sticky="ew")
        ai_hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(ai_hdr, text="Correction IA", font=ctk.CTkFont(size=13, weight="bold"), anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(ai_hdr, text="Colle ta clé API — Claude, OpenAI ou Gemini détecté automatiquement", font=ctk.CTkFont(size=11), text_color=("gray50","gray55"), anchor="w").grid(row=1, column=0, sticky="w")
        key_row = ctk.CTkFrame(ai_frame, fg_color="transparent")
        key_row.grid(row=1, column=0, padx=16, pady=(0,14), sticky="ew")
        key_row.grid_columnconfigure(0, weight=1)
        self.key_entry = ctk.CTkEntry(key_row, textvariable=self.api_key_var, placeholder_text="sk-ant-…  /  sk-…  /  AIza…", height=36, show="•")
        self.key_entry.grid(row=0, column=0, sticky="ew", padx=(0,8))
        self._key_visible = False
        self.eye_btn = ctk.CTkButton(key_row, text="👁", width=36, height=36, fg_color=("gray80","gray28"), text_color=("gray20","gray90"), hover_color=("gray70","gray35"), command=self._toggle_key_visibility)
        self.eye_btn.grid(row=0, column=1)
        self.provider_label = ctk.CTkLabel(key_row, text="", font=ctk.CTkFont(size=11), text_color=("gray50","gray55"))
        self.provider_label.grid(row=1, column=0, sticky="w", pady=(4,0))
        self.api_key_var.trace_add("write", self._on_key_change)
        if self.api_key_var.get():
            self._on_key_change()

        # Progress + Run
        self.progress = ctk.CTkProgressBar(tab, height=8, corner_radius=4)
        self.progress.grid(row=5, column=0, pady=(24,0), sticky="ew")
        self.progress.set(0)
        self.run_btn = ctk.CTkButton(tab, text="Générer le SRT  →", height=52, font=ctk.CTkFont(size=15, weight="bold"), corner_radius=12, command=self._run_whisper)
        self.run_btn.grid(row=6, column=0, pady=(16,8), sticky="ew")

        # Log + Status
        self.log_box = ctk.CTkTextbox(tab, height=140, font=ctk.CTkFont(family="Courier New", size=11), corner_radius=8, state="disabled")
        self.log_box.grid(row=7, column=0, pady=(0,8), sticky="ew")
        self.status_label = ctk.CTkLabel(tab, text="", font=ctk.CTkFont(size=12), text_color=("gray45","gray60"), wraplength=560)
        self.status_label.grid(row=8, column=0, pady=(0,8))

    # ─────────────────────────────────────────────────────────────────────────
    # TAB 2 — Corrections Frame.io
    # ─────────────────────────────────────────────────────────────────────────

    def _build_tab_corrections(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_rowconfigure(3, weight=1)
        tab.grid_rowconfigure(5, weight=2)

        # Instructions
        ctk.CTkLabel(tab, text="Colle ton SRT et tes commentaires Frame.io — Claude applique les corrections de texte automatiquement.", font=ctk.CTkFont(size=12), text_color=("gray50","gray55"), wraplength=580, justify="left").grid(row=0, column=0, sticky="w", pady=(12,12))

        # SRT input
        srt_lbl_row = ctk.CTkFrame(tab, fg_color="transparent")
        srt_lbl_row.grid(row=1, column=0, sticky="ew")
        srt_lbl_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(srt_lbl_row, text="SRT", font=ctk.CTkFont(size=12, weight="bold"), anchor="w").grid(row=0, column=0, sticky="w")
        self.srt_load_btn = ctk.CTkButton(srt_lbl_row, text="Charger un fichier…", width=140, height=28, fg_color=("gray85","gray25"), text_color=("gray20","gray90"), hover_color=("gray75","gray30"), command=self._load_srt_file)
        self.srt_load_btn.grid(row=0, column=1)

        self.srt_input = ctk.CTkTextbox(tab, font=ctk.CTkFont(family="Courier New", size=11), corner_radius=8)
        self.srt_input.grid(row=2, column=0, sticky="nsew", pady=(6,0))
        tab.grid_rowconfigure(2, weight=2)

        # Commentaires
        ctk.CTkLabel(tab, text="Commentaires Frame.io", font=ctk.CTkFont(size=12, weight="bold"), anchor="w").grid(row=3, column=0, sticky="w", pady=(14,0))
        self.comments_input = ctk.CTkTextbox(tab, height=160, font=ctk.CTkFont(size=12), corner_radius=8)
        self.comments_input.grid(row=4, column=0, sticky="nsew", pady=(6,0))
        self.comments_input.bind("<KeyRelease>", self._on_comments_change)
        self.comments_input.bind("<<Paste>>", lambda e: self.after(100, self._on_comments_change))

        # Match banner (caché par défaut)
        self.match_banner = ctk.CTkFrame(tab, fg_color=("gray92","gray18"), corner_radius=8)
        self.match_banner.grid(row=5, column=0, sticky="ew", pady=(8,0))
        self.match_banner.grid_columnconfigure(0, weight=1)
        self.match_banner.grid_remove()  # caché au départ

        match_inner = ctk.CTkFrame(self.match_banner, fg_color="transparent")
        match_inner.grid(row=0, column=0, padx=14, pady=10, sticky="ew")
        match_inner.grid_columnconfigure(0, weight=1)

        self.match_label = ctk.CTkLabel(match_inner, text="", font=ctk.CTkFont(size=12, weight="bold"), anchor="w")
        self.match_label.grid(row=0, column=0, sticky="w")
        self.match_sublabel = ctk.CTkLabel(match_inner, text="", font=ctk.CTkFont(size=11), text_color=("gray50","gray55"), anchor="w")
        self.match_sublabel.grid(row=1, column=0, sticky="w")

        btn_frame = ctk.CTkFrame(match_inner, fg_color="transparent")
        btn_frame.grid(row=0, column=1, rowspan=2, padx=(12,0))
        self.match_use_btn = ctk.CTkButton(btn_frame, text="Utiliser ce SRT", width=120, height=30, command=self._use_matched_srt)
        self.match_use_btn.pack(side="left", padx=(0,6))
        self.match_ignore_btn = ctk.CTkButton(btn_frame, text="Ignorer", width=70, height=30, fg_color=("gray80","gray28"), text_color=("gray20","gray90"), hover_color=("gray70","gray35"), command=self._ignore_match)
        self.match_ignore_btn.pack(side="left")

        self._matched_srt_path = None

        # Bouton appliquer
        self.apply_btn = ctk.CTkButton(tab, text="Appliquer les corrections  →", height=48, font=ctk.CTkFont(size=14, weight="bold"), corner_radius=12, command=self._apply_corrections)
        self.apply_btn.grid(row=6, column=0, pady=(16,8), sticky="ew")

        # SRT corrigé output
        out_lbl_row = ctk.CTkFrame(tab, fg_color="transparent")
        out_lbl_row.grid(row=7, column=0, sticky="ew")
        out_lbl_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(out_lbl_row, text="SRT corrigé", font=ctk.CTkFont(size=12, weight="bold"), anchor="w").grid(row=0, column=0, sticky="w")

        btn_row = ctk.CTkFrame(out_lbl_row, fg_color="transparent")
        btn_row.grid(row=0, column=1)
        self.copy_btn = ctk.CTkButton(btn_row, text="Copier", width=80, height=28, fg_color=("gray85","gray25"), text_color=("gray20","gray90"), hover_color=("gray75","gray30"), command=self._copy_output, state="disabled")
        self.copy_btn.pack(side="left", padx=(0,6))
        self.save_btn = ctk.CTkButton(btn_row, text="Sauvegarder…", width=120, height=28, fg_color=("gray85","gray25"), text_color=("gray20","gray90"), hover_color=("gray75","gray30"), command=self._save_output, state="disabled")
        self.save_btn.pack(side="left")

        self.srt_output = ctk.CTkTextbox(tab, font=ctk.CTkFont(family="Courier New", size=11), corner_radius=8, state="disabled")
        self.srt_output.grid(row=8, column=0, sticky="nsew", pady=(6,8))
        tab.grid_rowconfigure(8, weight=2)

        self.corrections_status = ctk.CTkLabel(tab, text="", font=ctk.CTkFont(size=12), text_color=("gray45","gray60"))
        self.corrections_status.grid(row=9, column=0, pady=(0,8))

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 2 logic
    # ─────────────────────────────────────────────────────────────────────────

    def _on_comments_change(self, event=None):
        comments = self.comments_input.get("1.0", "end").strip()
        if len(comments) < 30:
            self.match_banner.grid_remove()
            self._matched_srt_path = None
            return

        # Lancer la détection en background pour pas freezer l'UI
        def detect():
            path, score = find_matching_srt(comments, SRT_DIR)
            self.after(0, self._show_match_result, path, score)

        threading.Thread(target=detect, daemon=True).start()

    def _show_match_result(self, path, score):
        if not path or not score:
            self.match_banner.grid_remove()
            self._matched_srt_path = None
            return

        self._matched_srt_path = path
        fname = os.path.basename(path)

        CONF_COLORS = {
            "haute":   ("#1a6f2d", "#4caf50"),
            "moyenne": ("#7a6000", "#f0b429"),
            "faible":  ("gray50",  "gray55"),
        }
        color = CONF_COLORS.get(score["confidence"], ("gray50","gray55"))

        icons = {"haute": "✓", "moyenne": "⚠", "faible": "?"}
        icon = icons.get(score["confidence"], "?")

        self.match_label.configure(
            text=f"{icon}  SRT trouvé : {fname}  —  confiance {score['confidence']}",
            text_color=color
        )
        self.match_sublabel.configure(
            text=f"{score['tc_hits']}/{score['tc_total']} timecodes matchés  ·  {score['kw_hits']}/{score['kw_total']} mots-clés trouvés"
        )
        self.match_banner.grid()

    def _use_matched_srt(self):
        if not self._matched_srt_path:
            return
        try:
            with open(self._matched_srt_path, encoding="utf-8") as f:
                content = f.read()
            self.srt_input.delete("1.0", "end")
            self.srt_input.insert("1.0", content)
            self.match_banner.grid_remove()
            self.corrections_status.configure(
                text=f"✓  SRT chargé : {os.path.basename(self._matched_srt_path)}",
                text_color=("#2d7d2d","#4caf50")
            )
        except Exception as e:
            self.corrections_status.configure(text=f"✗  Erreur lecture SRT : {e}", text_color=("#c0392b","#e74c3c"))

    def _ignore_match(self):
        self.match_banner.grid_remove()
        self._matched_srt_path = None

    def _load_srt_file(self):
        path = filedialog.askopenfilename(title="Sélectionne un SRT", filetypes=[("SRT","*.srt"),("Tous","*.*")])
        if path:
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.srt_input.delete("1.0", "end")
            self.srt_input.insert("1.0", content)

    def _apply_corrections(self):
        srt_content = self.srt_input.get("1.0", "end").strip()
        comments = self.comments_input.get("1.0", "end").strip()

        if not srt_content:
            self.corrections_status.configure(text="⚠  Colle un SRT d'abord.", text_color=("gray50","gray55"))
            return
        if not comments:
            self.corrections_status.configure(text="⚠  Colle les commentaires Frame.io.", text_color=("gray50","gray55"))
            return

        api_key = self.api_key_var.get().strip()
        provider = detect_provider(api_key)
        if not provider:
            self.corrections_status.configure(text="⚠  Entre ta clé API dans l'onglet Générer d'abord.", text_color=("gray50","gray55"))
            return

        self.apply_btn.configure(state="disabled", text="En cours…")
        self.corrections_status.configure(text=f"🤖  Envoi à {provider}…", text_color=("gray50","gray55"))
        self.srt_output.configure(state="normal")
        self.srt_output.delete("1.0", "end")
        self.srt_output.configure(state="disabled")
        self.copy_btn.configure(state="disabled")
        self.save_btn.configure(state="disabled")

        def worker():
            try:
                result = ai_apply_corrections(srt_content, comments, api_key, provider)
                if result:
                    self.after(0, self._set_corrections_result, result)
                else:
                    self.after(0, lambda: self.corrections_status.configure(text="✗  L'IA n'a pas retourné de résultat.", text_color=("#c0392b","#e74c3c")))
                    self.after(0, lambda: self.apply_btn.configure(state="normal", text="Appliquer les corrections  →"))
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                logs.log.error("Corrections IA : HTTP %s %s", e.code, body[:500])
                self.after(0, lambda b=body, c=e.code: self.corrections_status.configure(text=f"✗  HTTP {c} : {b[:200]}", text_color=("#c0392b","#e74c3c")))
                self.after(0, lambda: self.apply_btn.configure(state="normal", text="Appliquer les corrections  →"))
            except urllib.error.URLError as e:
                logs.report(e, "Corrections IA")
                self.after(0, lambda r=e.reason: self.corrections_status.configure(text=f"✗  Réseau : {r}", text_color=("#c0392b","#e74c3c")))
                self.after(0, lambda: self.apply_btn.configure(state="normal", text="Appliquer les corrections  →"))
            except Exception as e:
                err = logs.report(e, "Corrections IA")
                self.after(0, lambda err=err: self.corrections_status.configure(text=f"✗  {err}", text_color=("#c0392b","#e74c3c")))
                self.after(0, lambda: self.apply_btn.configure(state="normal", text="Appliquer les corrections  →"))

        threading.Thread(target=worker, daemon=True).start()

    def _set_corrections_result(self, result):
        self.srt_output.configure(state="normal")
        self.srt_output.delete("1.0", "end")
        self.srt_output.insert("1.0", result)
        self.srt_output.configure(state="disabled")
        self.copy_btn.configure(state="normal")
        self.save_btn.configure(state="normal")
        self.apply_btn.configure(state="normal", text="Appliquer les corrections  →")
        self.corrections_status.configure(text="✓  Corrections appliquées — copie ou sauvegarde le SRT.", text_color=("#2d7d2d","#4caf50"))

    def _copy_output(self):
        result = self.srt_output.get("1.0", "end").strip()
        self.clipboard_clear()
        self.clipboard_append(result)
        self.corrections_status.configure(text="✓  Copié dans le presse-papier!", text_color=("#2d7d2d","#4caf50"))

    def _save_output(self):
        result = self.srt_output.get("1.0", "end").strip()
        path = filedialog.asksaveasfilename(defaultextension=".srt", filetypes=[("SRT","*.srt"),("Tous","*.*")], title="Sauvegarder le SRT corrigé")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(result)
            self.corrections_status.configure(text=f"✓  Sauvegardé : {os.path.basename(path)}", text_color=("#2d7d2d","#4caf50"))

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 1 logic
    # ─────────────────────────────────────────────────────────────────────────

    def _toggle_key_visibility(self):
        self._key_visible = not self._key_visible
        self.key_entry.configure(show="" if self._key_visible else "•")

    def _on_drop(self, event):
        path = event.data.strip().strip("{}")
        if path:
            self._set_video(path)

    def _browse_video(self):
        path = filedialog.askopenfilename(title="Sélectionne ta vidéo", filetypes=[("Vidéos","*.mp4 *.mov *.mkv *.avi *.webm"),("Tous","*.*")])
        if path:
            self._set_video(path)

    def _set_video(self, path):
        self.video_path.set(path)
        name = os.path.basename(path)
        self.drop_icon.configure(text="✓", text_color=("#2d7d2d","#7bc97b"))
        self.drop_label.configure(text=name[:50]+("…" if len(name)>50 else ""))
        self.drop_sub.configure(text="Clique pour changer")
        # Ne pas écraser si déjà défini (ex: SRT_DIR par défaut)
        if not self.output_path.get():
            self.output_path.set(SRT_DIR)

    def _browse_output(self):
        path = filedialog.askdirectory(title="Dossier de sortie")
        if path:
            self.output_path.set(path)

    def _log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text+"\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _set_done(self, srt_path):
        self.progress.stop()
        self.progress.configure(mode="determinate", progress_color=("#2d7d2d","#4caf50"))
        self.progress.set(1)
        self.run_btn.configure(state="normal", text="Générer le SRT  →")
        self._log(f"\n✓  SRT généré : {srt_path}")
        self.status_label.configure(text="✓ Terminé! Dans CapCut : Text → Auto Captions → Local Captions → Import")

    def _set_error(self, msg):
        self.progress.stop()
        self.progress.configure(mode="determinate", progress_color=("#c0392b","#e74c3c"))
        self.progress.set(0)
        self.run_btn.configure(state="normal", text="Générer le SRT  →")
        self._log(msg)

    def _run_whisper(self):
        video = self.video_path.get().strip()
        output = self.output_path.get().strip()
        model = MODEL_NAMES[self.model_index.get()]
        _, _, max_chars, max_lines = CAPTION_LENGTHS[self.caption_index.get()]

        if not video:
            self._log("⚠  Sélectionne une vidéo d'abord.")
            return
        if not os.path.isfile(video):
            self._log(f"✗  Vidéo introuvable : {video}")
            return

        api_key = self.api_key_var.get().strip()
        provider = detect_provider(api_key) if api_key else None
        use_ai = self.ai_enabled.get() and provider is not None

        self.run_btn.configure(state="disabled", text="En cours…")
        self.progress.configure(progress_color=ctk.ThemeManager.theme["CTkProgressBar"]["progress_color"])
        self.progress.set(0)
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self.status_label.configure(text="")
        self._log(f"▶  Démarrage · modèle {model}")
        self._log(f"   {os.path.basename(video)}")
        if use_ai:
            self._log(f"   + Correction IA activée ({provider})")

        log_fn = lambda m: self.after(0, self._log, m)

        def worker():
            try:
                srt_path = engine.run_pipeline(
                    video, model, max_chars, max_lines, output or None,
                    api_key, provider, use_ai, log_fn,
                    download_progress=lambda d, t: self.after(0, self._show_download, d, t))
                self.after(0, self._set_done, srt_path)
            except Exception as e:
                msg = logs.report(e, "Transcription")
                self.after(0, self._set_error,
                           f"✗  {msg}\n   Détails dans le journal : {logs.LOG_FILE}")

        threading.Thread(target=worker, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────────────
    # Démarrage : vérifications + appareil (GPU / CPU)
    # ─────────────────────────────────────────────────────────────────────────

    def _show_download(self, done, total):
        """Barre de progression déterminée pendant un téléchargement."""
        if self.progress.cget("mode") != "determinate":
            self.progress.stop()
            self.progress.configure(mode="determinate")
        if total:
            self.progress.set(done / total)
            pct = int(done * 100 / total)
            if pct != getattr(self, "_last_pct", -1):
                self._last_pct = pct
                self.status_label.configure(
                    text=f"Téléchargement… {done / 1e9:.2f} / {total / 1e9:.2f} Go ({pct} %)")
        if total and done >= total:
            self.status_label.configure(text="")
            self.progress.configure(mode="indeterminate")
            self.progress.start()

    def startup_checks(self, dir_errors):
        if plat.running_from_zip():
            messagebox.showwarning(
                "WhisperQC",
                "WhisperQC est lancé depuis l'intérieur du fichier .zip.\n\n"
                "Ferme l'app, fais clic droit sur le .zip → « Extraire tout… », "
                "puis lance WhisperQC.exe depuis le dossier extrait.")
        for err in dir_errors:
            self._log(f"⚠  Dossier inaccessible : {err}")

        def detect():
            try:
                dev = engine.current_device()
            except Exception as e:
                logs.report(e, "Détection de l'appareil")
                dev = gpu.Device("cpu", "int8", "CPU (int8)")
            self.after(0, self._show_device, dev)

        threading.Thread(target=detect, daemon=True).start()

    def _show_device(self, dev):
        from . import models
        self._log(f"Appareil : {dev.label}")
        if dev.device == "cpu" and not dev.gpu_needs_pack:
            self._log("   Pas de GPU NVIDIA : la transcription roule sur le CPU (plus lent).")
        model = MODEL_NAMES[self.model_index.get()]
        if models.model_path(model) is None:
            self._log(f"Modèle {model} : sera téléchargé au premier lancement "
                      f"({models.APPROX_SIZE.get(model, '')}).")
        if dev.gpu_needs_pack:
            self._offer_cuda_pack()

    def _offer_cuda_pack(self):
        cfg = load_config()
        if cfg.get("gpu_pack_declined"):
            self._log("   Carte NVIDIA détectée, module GPU non installé : CPU utilisé.")
            return
        ok = messagebox.askyesno(
            "WhisperQC — carte NVIDIA détectée",
            "Ta carte NVIDIA peut rendre la transcription beaucoup plus rapide.\n\n"
            f"Il faut télécharger le module GPU NVIDIA (≈ {gpu.CUDA_PACK_SIZE}, une seule fois).\n\n"
            "Le télécharger maintenant ?\n(Sinon, WhisperQC fonctionne quand même sur le CPU.)")
        if not ok:
            cfg["gpu_pack_declined"] = True
            save_config(cfg)
            self._log("   Module GPU refusé : CPU utilisé. (Pour qu'il te soit reproposé, "
                      f"supprime « gpu_pack_declined » dans {plat.config_dir()})")
            return

        self.run_btn.configure(state="disabled", text="Téléchargement du module GPU…")
        self.progress.configure(progress_color=ctk.ThemeManager.theme["CTkProgressBar"]["progress_color"])
        self._log(f"⬇  Téléchargement du module GPU NVIDIA (≈ {gpu.CUDA_PACK_SIZE})…")
        log_fn = lambda m: self.after(0, self._log, m)

        def worker():
            try:
                gpu.install_cuda_pack(
                    progress=lambda d, t: self.after(0, self._show_download, d, t),
                    log_fn=log_fn)
                engine.reset_device()
                dev = engine.current_device()
                self.after(0, self._cuda_pack_done, dev, None)
            except Exception as e:
                self.after(0, self._cuda_pack_done, None, logs.report(e, "Module GPU"))

        threading.Thread(target=worker, daemon=True).start()

    def _cuda_pack_done(self, dev, err):
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress.set(0)
        self.status_label.configure(text="")
        self.run_btn.configure(state="normal", text="Générer le SRT  →")
        if err:
            self._log(f"✗  Module GPU : {err}")
            self._log("   WhisperQC continue sur le CPU. Il te le reproposera au prochain lancement.")
        elif dev.device == "cuda":
            self._log(f"✓  Module GPU installé — Appareil : {dev.label}")
        else:
            self._log("⚠  Module GPU installé mais le GPU reste inutilisable "
                      "(pilote NVIDIA trop vieux ?). CPU utilisé.")


def run():
    from . import config
    logs.setup()
    dir_errors = config.ensure_dirs()
    try:
        app = WhisperQC()
    except Exception as e:
        msg = logs.report(e, "Démarrage")
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("WhisperQC", f"WhisperQC n'a pas pu démarrer.\n\n{msg}\n\n"
                                 f"Journal : {logs.LOG_FILE}")
        except Exception:
            pass
        raise SystemExit(1)

    def _tk_error(exc, val, tb):
        msg = logs.report(val, "Erreur d'interface")
        messagebox.showerror("WhisperQC", f"{msg}\n\nJournal : {logs.LOG_FILE}")

    app.report_callback_exception = _tk_error
    app.after(200, app.startup_checks, dir_errors)
    app.mainloop()
