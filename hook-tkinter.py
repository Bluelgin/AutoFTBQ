# Custom hook for tkinter
datas = [
    ('C:\\Users\\Administrator\\AppData\\Local\\Python\\pythoncore-3.14-64\\DLLs\\tcl86t.dll', '.'),
    ('C:\\Users\\Administrator\\AppData\\Local\\Python\\pythoncore-3.14-64\\DLLs\\tk86t.dll', '.'),
    ('C:\\Users\\Administrator\\AppData\\Local\\Python\\pythoncore-3.14-64\\DLLs\\_tkinter.pyd', '.'),
]

# Also include the entire tcl directory
from PyInstaller.utils.hooks import collect_data_files
datas += collect_data_files('C:\\Users\\Administrator\\AppData\\Local\\Python\\pythoncore-3.14-64\\tcl')
