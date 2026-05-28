# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['cat_zap.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('models', 'models'),
        ('cat_zap_extension', 'cat_zap_extension'),
        ('cat_icon.ico', '.'),
        ('cat_zap.py', 'cat_zap.py'),
        ('C:\\Python314\\Lib\\site-packages\\faster_whisper\\assets', 'faster_whisper/assets'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CatZap_v1.4',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['cat_icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CatZap_v1.4',
)
