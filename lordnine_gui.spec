# -*- mode: python ; coding: utf-8 -*-

import os

block_cipher = None


def project_datas():
    datas = []
    # Include default config and assets so GUI defaults work out of the box
    datas.append((os.path.join('l9', 'config.yaml'), os.path.join('l9')))
    datas.append((os.path.join('l9', 'assets'), os.path.join('l9', 'assets')))
    # Include data directory for grind paths
    datas.append((os.path.join('l9', 'data'), os.path.join('l9', 'data')))
    # Include scripts needed by the GUI
    datas.append((os.path.join('scripts', 'record_grind_path.py'), os.path.join('scripts')))
    datas.append((os.path.join('scripts', 'check_assets.py'), os.path.join('scripts')))
    return datas


a = Analysis(
    ['scripts/gui.py'],
    pathex=['.'],
    binaries=[],
    datas=project_datas(),
    hiddenimports=[
        # Ensure dynamic imports are bundled
        'pyautogui',
        'pydirectinput',
        'keyboard',
        'mss',
        'cv2',
        'numpy',
        'PIL',
        'PIL.ImageGrab',
        'yaml',
        'tkinter',
        'tkinter.ttk',
        # L9 package modules
        'l9',
        'l9.flows',
        'l9.flows.grind_refill_loop',
        'l9.flows.buy_potions',
        'l9.flows.dismantle',
        'l9.flows.grind',
        'l9.flows.return_town',
        'l9.flows.revive',
        'l9.vision',
        'l9.vision.capture',
        'l9.vision.match',
        'l9.actions',
        'l9.actions.input',
        'l9.actions.window',
        'l9.config_loader',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LordnineGUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='LordnineGUI',
)
