# -*- mode: python ; coding: utf-8 -*-

import faster_whisper
import os

_whisper_dir = os.path.dirname(faster_whisper.__file__)
_assets_src = os.path.join(_whisper_dir, 'assets')
_script_dir = os.getcwd()
_ext_src = os.path.join(_script_dir, 'cat_zap_extension')

_datas = []
if os.path.isdir(_assets_src):
    _datas.append((_assets_src, 'faster_whisper/assets'))
if os.path.isdir(_ext_src):
    _datas.append((_ext_src, 'cat_zap_extension'))

a = Analysis(
    ['cat_zap.py'],
    pathex=[],
    binaries=[],
    datas=_datas,
    hiddenimports=['pystray', 'PIL', 'spellchecker'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'notebook', 'IPython', 'PIL.ImageShow'],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CatZap',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['cat_icon.ico'],
)
