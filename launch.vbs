Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")
navDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = navDir
WshShell.Run "cmd /c """ & navDir & "\launch.bat""", 0, False
