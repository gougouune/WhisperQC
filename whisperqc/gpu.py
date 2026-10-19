# -*- coding: utf-8 -*-
"""Choix de l'appareil : GPU NVIDIA (CUDA) si utilisable, sinon CPU int8.

Windows + carte NVIDIA : il faut cuBLAS 12 + cuDNN 9 (~1,1 Go). Ils ne sont
plus livrés dans le zip ; l'app propose de les télécharger une fois (les
wheels officielles NVIDIA sur PyPI, versions et SHA-256 épinglés ici).
macOS : CTranslate2 n'a pas de backend Metal -> CPU (Apple Accelerate).
"""

import zipfile
from dataclasses import dataclass

from . import platform_support as plat
from .download import download

# Testé avec ctranslate2 4.8.3 (qui livre déjà cudnn64_9.dll 9.10.2).
CUDA_WHEELS = [
    {
        "url": "https://files.pythonhosted.org/packages/84/f7/985e9bdbe3e0ac9298fcc8cfa51a392862a46a0ffaccbbd56939b62a9c83/nvidia_cublas_cu12-12.6.4.1-py3-none-win_amd64.whl",
        "size": 434535301,
        "sha256": "9e4fa264f4d8a4eb0cdbd34beadc029f453b3bafae02401e999cf3d5a5af75f8",
        "keep": ("cublas64_12.dll", "cublasLt64_12.dll"),
    },
    {
        "url": "https://files.pythonhosted.org/packages/3d/90/0bd6e586701b3a890fd38aa71c387dab4883d619d6e5ad912ccbd05bfd67/nvidia_cudnn_cu12-9.10.2.21-py3-none-win_amd64.whl",
        "size": 692992268,
        "sha256": "c6288de7d63e6cf62988f0923f96dc339cea362decb1bf5b3141883392a7d65e",
        "keep": ("cudnn",),  # tous les cudnn*64_9.dll
    },
]
CUDA_PACK_SIZE = "1,1 Go"
_REQUIRED_DLLS = ("cublas64_12.dll", "cublasLt64_12.dll", "cudnn_ops64_9.dll",
                  "cudnn_cnn64_9.dll")


@dataclass
class Device:
    device: str          # "cuda" | "cpu"
    compute_type: str    # "auto" (GPU, comme XXL) | "int8" (CPU)
    label: str           # pour le log de l'app
    gpu_needs_pack: bool = False  # NVIDIA présente mais DLL CUDA absentes


def nvidia_gpu_present() -> bool:
    if plat.IS_MAC:
        return False
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def cuda_libs_ok() -> bool:
    if not plat.IS_WINDOWS:
        return True  # Linux : libs via pip/système, hors scope des builds
    plat.setup_cuda_search_path()
    import ctypes
    for name in _REQUIRED_DLLS:
        try:
            ctypes.WinDLL(name)
        except OSError:
            return False
    return True


def _gpu_name() -> str:
    try:
        import subprocess
        kw = {"creationflags": subprocess.CREATE_NO_WINDOW} if plat.IS_WINDOWS else {}
        r = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                           capture_output=True, text=True, timeout=5, **kw)
        return r.stdout.strip().splitlines()[0] if r.returncode == 0 and r.stdout.strip() else ""
    except Exception:
        return ""


def detect() -> Device:
    cpu = Device("cpu", "int8", "CPU (int8)")
    if not nvidia_gpu_present():
        if plat.IS_MAC:
            cpu.label = "CPU du Mac (int8)"
        return cpu
    if not cuda_libs_ok():
        cpu.gpu_needs_pack = True
        return cpu
    name = _gpu_name()
    label = name if name.upper().startswith("NVIDIA") else f"NVIDIA {name}".strip()
    return Device("cuda", "auto", f"GPU {label} (CUDA)")


def install_cuda_pack(progress=None, log_fn=None) -> None:
    """Télécharge les wheels NVIDIA et extrait seulement les DLL utiles dans
    le dossier cuda/. progress(done_bytes, total_bytes)."""
    dest = plat.cuda_dir()
    dest.mkdir(parents=True, exist_ok=True)
    total = sum(w["size"] for w in CUDA_WHEELS)
    done = 0

    def _tick(n):
        nonlocal done
        done += n
        if progress:
            progress(done, total)

    for w in CUDA_WHEELS:
        whl = dest / w["url"].rsplit("/", 1)[1]
        if log_fn:
            log_fn(f"   {whl.name.split('-')[0]} ({w['size'] / 1e6:.0f} Mo)")
        download(w["url"], whl, size=w["size"], sha256=w["sha256"], progress=_tick)
        try:
            with zipfile.ZipFile(whl) as z:
                for info in z.infolist():
                    base = info.filename.rsplit("/", 1)[-1]
                    if base.lower().endswith(".dll") and base.startswith(w["keep"]):
                        with z.open(info) as src, open(dest / base, "wb") as out:
                            while chunk := src.read(1024 * 1024):
                                out.write(chunk)
        finally:
            whl.unlink(missing_ok=True)
    plat.setup_cuda_search_path()
