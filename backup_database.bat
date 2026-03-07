@echo off
REM Daybook Database Backup Script
REM Run this script to backup your database

set BACKUP_DIR=C:\Backups\Daybook
set DATE=%date:~-4,4%%date:~-10,2%%date:~-7,2%__%time:~0,2%%time:~3,2%%time:~6,2%
set DATE=%DATE: =0%

REM Create backup directory if it doesn't exist
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"
mkdir "%BACKUP_DIR%\%DATE%" 2>nul

REM Copy database file
copy "C:\Learnings\Python\daybook_lite\daybook_lite\db.sqlite3" "%BACKUP_DIR%\%DATE%\db.sqlite3"

REM Copy entire project folder (optional - comment out if not needed)
REM xcopy "C:\Learnings\Python\daybook_lite" "%BACKUP_DIR%\%DATE%\project_backup\" /E /I /Y

echo.
echo ========================================
echo Database backed up successfully!
echo Location: %BACKUP_DIR%\%DATE%
echo ========================================
echo.

pause
