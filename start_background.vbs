Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")
navDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = navDir
WshShell.Run "pythonw.exe server.py", 0, False
