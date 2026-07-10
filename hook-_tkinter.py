# Custom hook for _tkinter
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files
import os

# Find the DLLs directory
dll_dir = r'C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64\DLLs'

binaries = [
    (os.path.join(dll_dir, 'tcl86t.dll'), '.'),
    (os.path.join(dll_dir, 'tk86t.dll'), '.'),
    (os.path.join(dll_dir, '_tkinter.pyd'), '.'),
]

tcl_dir = r'C:\Users\Administrator\AppData\Local\Python\pythoncore-3.14-64\tcl'
datas = [
    (os.path.join(tcl_dir, 'tcl8.6', f), os.path.join('tcl', 'tcl8.6'))
    for f in os.listdir(os.path.join(tcl_dir, 'tcl8.6'))
    if os.path.isfile(os.path.join(tcl_dir, 'tcl8.6', f))
] + [
    (os.path.join(tcl_dir, 'tk8.6', f), os.path.join('tcl', 'tk8.6'))
    for f in os.listdir(os.path.join(tcl_dir, 'tk8.6'))
    if os.path.isfile(os.path.join(tcl_dir, 'tk8.6', f))
] + [
    (os.path.join(tcl_dir, 'tcl8', f), os.path.join('tcl', 'tcl8'))
    for f in os.listdir(os.path.join(tcl_dir, 'tcl8'))
    if os.path.isfile(os.path.join(tcl_dir, 'tcl8', f))
]
