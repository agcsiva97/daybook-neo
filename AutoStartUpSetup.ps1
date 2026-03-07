$WshShell = New-Object -comObject WScript.Shell; 
$Shortcut = $WshShell.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\Daybook Server.lnk"); 
$Shortcut.TargetPath = "C:\Learnings\Python\daybook_lite\start_daybook_hidden.vbs"; 
$Shortcut.WorkingDirectory = "C:\Learnings\Python\daybook_lite"; 
$Shortcut.Save(); 
Write-Host "Updated startup shortcut to run hidden."