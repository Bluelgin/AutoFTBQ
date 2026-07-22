# -*- mode: python ; coding: utf-8 -*-

import os
import sys
import sysconfig
from PyInstaller.building.datastruct import Tree
from PyInstaller.utils.hooks.tcl_tk import TclTkInfo

dll_root = os.path.join(sys.base_prefix, 'DLLs')
tkinter_root = os.path.join(sysconfig.get_path('stdlib'), 'tkinter')
tk_binaries = [
    os.path.join(dll_root, 'tcl86t.dll'),
    os.path.join(dll_root, 'tk86t.dll'),
    os.path.join(dll_root, '_tkinter.pyd'),
]
missing_tk_files = [path for path in tk_binaries if not os.path.isfile(path)]
if missing_tk_files or not os.path.isdir(tkinter_root):
    raise RuntimeError(
        '当前 Python 环境缺少完整的 Tcl/Tk 运行库，无法安全打包：'
        + ', '.join(missing_tk_files or [tkinter_root])
    )
tk_info = TclTkInfo()
tcl_datas = [(src, os.path.dirname(dest)) for dest, src, _ in tk_info.data_files]
tkinter_datas = [(src, os.path.dirname(dest)) for dest, src, _ in Tree(tkinter_root, prefix='tkinter')]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[(path, '.') for path in tk_binaries],
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
