Set objShell = CreateObject("WScript.Shell")
objShell.CurrentDirectory = "C:\Users\bpietrzyk\Documents\Claude\excelHelper\backend"
objShell.Run """C:\Users\bpietrzyk\AppData\Local\Programs\Python\Python313\pythonw.exe"" -m app.main", 0, False
