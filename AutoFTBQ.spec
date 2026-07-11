# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.building.datastruct import Tree
from PyInstaller.utils.hooks.tcl_tk import TclTkInfo

dll_root = r'C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64\DLLs'
tkinter_root = r'C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64\Lib\tkinter'
tk_info = TclTkInfo()
tcl_datas = [(src, os.path.dirname(dest)) for dest, src, _ in tk_info.data_files]
tkinter_datas = [(src, os.path.dirname(dest)) for dest, src, _ in Tree(tkinter_root, prefix='tkinter')]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[
        (os.path.join(dll_root, 'tcl86t.dll'), '.'),
        (os.path.join(dll_root, 'tk86t.dll'), '.'),
        (os.path.join(dll_root, '_tkinter.pyd'), '.'),
    ],
    datas=[('playstyle_data', 'playstyle_data')] + tcl_datas + tkinter_datas,
    hiddenimports=['_tkinter'],
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
    a.binaries,
    a.datas,
    [],
    name='AutoFTBQ',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
