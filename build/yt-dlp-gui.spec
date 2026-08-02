# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for yt-dlp-gui (one-folder: exe + dependencies in dist/yt-dlp-gui/)
#
# Large excludes: avoid bundling ML / unrelated packages if PyInstaller is run from a
# cluttered global Python. Prefer building via build.ps1 (isolated venv).

import os

block_cipher = None

REPO_ROOT = os.path.dirname(SPECPATH)  # build/ -> repo root
SRC_DIR = os.path.join(REPO_ROOT, "src")
RESOURCES_DIR = os.path.join(SRC_DIR, "yt_dlp_gui", "resources")

# Not used by this app; often pulled in from a dev site-packages and cause DLL warnings.
_EXCLUDE_MODULES = [
    'PyQt5',
    'PyQt6',
    'torch',
    'torchvision',
    'torchaudio',
    'torchgen',
    'tensorflow',
    'tensorboard',
    'tensorboardX',
    'transformers',
    'datasets',
    'accelerate',
    'diffusers',
    'tokenizers',
    'sentencepiece',
    'onnxruntime',
    'paddle',
    'paddlepaddle',
    'spacy',
    'thinc',
    'gradio',
    'matplotlib',
    'matplotlib.backends',
    'scipy',
    'sklearn',
    'pandas',
    'numba',
    'llvmlite',
    'pygame',
    'cv2',
    'pytest',
    'IPython',
    'jupyter',
    'notebook',
    'sympy',
    'nltk',
    'jieba',
    'imageio',
    'skimage',
    'networkx',
    'faiss',
]

a = Analysis(
    [os.path.join(REPO_ROOT, "main.py")],
    pathex=[SRC_DIR],
    binaries=[],
    datas=[
        (RESOURCES_DIR, "resources"),
    ],
    hiddenimports=[
        'qtawesome',
        'qtawesome.iconic_font',
        'platformdirs',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_EXCLUDE_MODULES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='yt-dlp-gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(RESOURCES_DIR, "yt-dlp-gui.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='yt-dlp-gui',
)
