@echo off
REM Daybook Log Viewer and Management Script

:MENU
cls
echo ========================================
echo    Daybook Log Management Tool
echo ========================================
echo.
echo 1. View last 50 lines of general log
echo 2. View last 50 lines of error log
echo 3. View last 50 lines of security log
echo 4. View last 50 lines of transactions log
echo 5. Monitor general log in real-time
echo 6. Search logs for specific text
echo 7. Check log folder size
echo 8. Archive rotated logs
echo 9. Exit
echo.
set /p choice=Enter your choice (1-9): 

if "%choice%"=="1" goto VIEW_GENERAL
if "%choice%"=="2" goto VIEW_ERROR
if "%choice%"=="3" goto VIEW_SECURITY
if "%choice%"=="4" goto VIEW_TRANSACTIONS
if "%choice%"=="5" goto MONITOR
if "%choice%"=="6" goto SEARCH
if "%choice%"=="7" goto CHECK_SIZE
if "%choice%"=="8" goto ARCHIVE
if "%choice%"=="9" goto EXIT

echo Invalid choice. Please try again.
pause
goto MENU

:VIEW_GENERAL
cls
echo === Last 50 lines of daybook.log ===
echo.
powershell -Command "if (Test-Path '.\daybook_lite\logs\daybook.log') { Get-Content '.\daybook_lite\logs\daybook.log' -Tail 50 } else { Write-Host 'Log file not found!' }"
echo.
pause
goto MENU

:VIEW_ERROR
cls
echo === Last 50 lines of daybook_errors.log ===
echo.
powershell -Command "if (Test-Path '.\daybook_lite\logs\daybook_errors.log') { Get-Content '.\daybook_lite\logs\daybook_errors.log' -Tail 50 } else { Write-Host 'Log file not found or no errors logged!' }"
echo.
pause
goto MENU

:VIEW_SECURITY
cls
echo === Last 50 lines of security.log ===
echo.
powershell -Command "if (Test-Path '.\daybook_lite\logs\security.log') { Get-Content '.\daybook_lite\logs\security.log' -Tail 50 } else { Write-Host 'Log file not found!' }"
echo.
pause
goto MENU

:VIEW_TRANSACTIONS
cls
echo === Last 50 lines of transactions.log ===
echo.
powershell -Command "if (Test-Path '.\daybook_lite\logs\transactions.log') { Get-Content '.\daybook_lite\logs\transactions.log' -Tail 50 } else { Write-Host 'Log file not found!' }"
echo.
pause
goto MENU

:MONITOR
cls
echo === Monitoring general log (Ctrl+C to stop) ===
echo.
powershell -Command "if (Test-Path '.\daybook_lite\logs\daybook.log') { Get-Content '.\daybook_lite\logs\daybook.log' -Wait -Tail 50 } else { Write-Host 'Log file not found!' }"
pause
goto MENU

:SEARCH
cls
echo === Search Logs ===
echo.
set /p search_term=Enter text to search for: 
echo.
echo Searching in daybook.log...
powershell -Command "if (Test-Path '.\daybook_lite\logs\daybook.log') { Select-String -Path '.\daybook_lite\logs\daybook.log' -Pattern '%search_term%' | Select-Object -Last 20 } else { Write-Host 'Log file not found!' }"
echo.
pause
goto MENU

:CHECK_SIZE
cls
echo === Log Folder Size ===
echo.
powershell -Command "if (Test-Path '.\daybook_lite\logs') { Get-ChildItem '.\daybook_lite\logs' -Recurse | Measure-Object -Property Length -Sum | Select-Object @{Name='Total Size (MB)';Expression={[math]::Round($_.Sum / 1MB, 2)}}, Count | Format-List } else { Write-Host 'Logs folder not found!' }"
echo.
echo Individual log files:
powershell -Command "if (Test-Path '.\daybook_lite\logs') { Get-ChildItem '.\daybook_lite\logs\*.log' | Select-Object Name, @{Name='Size(KB)';Expression={[math]::Round($_.Length / 1KB, 2)}} | Format-Table -AutoSize } else { Write-Host 'Logs folder not found!' }"
echo.
pause
goto MENU

:ARCHIVE
cls
echo === Archive Rotated Logs ===
echo.
set ARCHIVE_DIR=C:\Backups\Daybook\Logs\Archive
set DATE=%date:~-4,4%-%date:~-10,2%
powershell -Command "New-Item -Path '%ARCHIVE_DIR%\%DATE%' -ItemType Directory -Force | Out-Null"
powershell -Command "if (Test-Path '.\daybook_lite\logs\*.log.*') { Copy-Item '.\daybook_lite\logs\*.log.*' '%ARCHIVE_DIR%\%DATE%\' -Force; Write-Host 'Rotated logs archived to %ARCHIVE_DIR%\%DATE%'; Write-Host; $count = (Get-ChildItem '%ARCHIVE_DIR%\%DATE%').Count; Write-Host 'Files archived: ' $count } else { Write-Host 'No rotated logs found to archive.' }"
echo.
pause
goto MENU

:EXIT
exit

