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
playstyle_root = os.path.abspath('playstyle_data')
playstyle_datas = [
    (os.path.join(playstyle_root, name), 'playstyle_data')
    for name in sorted(os.listdir(playstyle_root))
    if name.endswith('.md') and os.path.isfile(os.path.join(playstyle_root, name))
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[(path, '.') for path in tk_binaries],
    datas=[
        ('human_style_corpus.json.gz', '.'),
    ] + playstyle_datas + tcl_datas + tkinter_datas,
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
    # UPX 压缩是微软 Defender 误报的常见触发点，禁用可显著降低误报概率。
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # 写入版本资源，让程序在 Windows 属性中显示作者/版本信息，降低启发式误报。
    version='version_info.txt',
)
