# Daybook Lite - Production Deployment Guide

This guide will help you set up Daybook Lite on a client machine for production use.

## Prerequisites

- Windows 10/11
- Administrator access
- Internet connection (for initial setup only)

## Step 1: Install Python

1. Download Python 3.11 or later from [python.org](https://www.python.org/downloads/)
2. Run the installer
3. **IMPORTANT:** Check "Add Python to PATH" during installation
4. Click "Install Now"
5. Verify installation:
   ```powershell
   python --version
   ```

## Step 2: Copy Project Files

1. Copy the entire `daybook_lite` folder to the client machine
2. Recommended location: `C:\Apps\daybook_lite\`
3. Ensure all files and folders are copied:
   ```
   daybook_lite/
   ├── daybook_lite/          # Main project folder
   ├── start_daybook.bat
   ├── start_daybook_hidden.vbs
   └── requirements.txt (if exists)
   ```

## Step 3: Create Virtual Environment

1. Open PowerShell as Administrator
2. Navigate to project folder:
   ```powershell
   cd C:\Apps\daybook_lite
   ```
3. Create virtual environment:
   ```powershell
   python -m venv .venv
   ```

## Step 4: Install Dependencies

1. Activate virtual environment:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```
   
   **Note:** If you get an execution policy error, run:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

2. Install Django and dependencies:
   ```powershell
   pip install django==6.0.2
   pip install openpyxl
   ```

## Step 5: Database Setup

1. Navigate to the inner daybook_lite folder:
   ```powershell
   cd daybook_lite
   ```

2. Run migrations:
   ```powershell
   python manage.py migrate
   ```

3. Create superuser (Admin account):
   ```powershell
   python manage.py createsuperuser
   ```
   - Enter username, email (optional), and password
   - Remember these credentials!

## Step 6: Create User Groups

1. Start the development server temporarily:
   ```powershell
   python manage.py runserver
   ```

2. Open browser and go to: `http://localhost:8000/admin`

3. Login with superuser credentials

4. Create two groups:
   - Click "Groups" → "Add Group"
   - Create group named: **Admin**
   - Click "Save and add another"
   - Create group named: **Staff**
   - Click "Save"

5. Add superuser to Admin group:
   - Click "Users" → Click your username
   - In "Groups" section, select "Admin" and click the arrow to add
   - Click "Save"

6. Stop the server (Ctrl+C in PowerShell)

## Step 7: Configure for Production

1. Edit `daybook_lite/daybook_lite/settings.py`:
   
   Find and change:
   ```python
   DEBUG = True
   ```
   To:
   ```python
   DEBUG = False
   ```

2. Update ALLOWED_HOSTS:
   ```python
   ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'YOUR_MACHINE_NAME']
   ```
   
   To find your machine name:
   ```powershell
   hostname
   ```

3. Collect static files:
   ```powershell
   python manage.py collectstatic --noinput
   ```

## Step 8: Update Startup Scripts

1. Edit `start_daybook.bat`:
   ```batch
   @echo off
   cd /d C:\Apps\daybook_lite\daybook_lite
   start "Daybook Server" C:\Apps\daybook_lite\.venv\Scripts\python.exe manage.py runserver localhost:8000
   ```

2. Edit `start_daybook_hidden.vbs`:
   ```vbscript
   Set WshShell = CreateObject("WScript.Shell")
   WshShell.Run "C:\Apps\daybook_lite\start_daybook.bat", 0, False
   Set WshShell = Nothing
   ```

## Step 9: Configure Auto-Start on Windows Login

### Option A: Using Startup Folder (Recommended)

1. Open PowerShell as Administrator
2. Run this command:
   ```powershell
   $WshShell = New-Object -comObject WScript.Shell
   $Shortcut = $WshShell.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\Daybook Server.lnk")
   $Shortcut.TargetPath = "C:\Apps\daybook_lite\start_daybook_hidden.vbs"
   $Shortcut.WorkingDirectory = "C:\Apps\daybook_lite"
   $Shortcut.Save()
   Write-Host "Startup shortcut created successfully!"
   ```

### Option B: Using Task Scheduler (For Background Service)

1. Open Task Scheduler (`Win + R`, type `taskschd.msc`)
2. Click "Create Basic Task"
3. Name: `Daybook Server`
4. Trigger: "When I log on"
5. Action: "Start a program"
6. Program/script: `C:\Apps\daybook_lite\start_daybook_hidden.vbs`
7. Finish and check "Open Properties"
8. Under "General" tab:
   - Check "Run whether user is logged on or not"
   - Check "Run with highest privileges"
9. Under "Conditions" tab:
   - Uncheck "Start only if on AC power"
10. Click OK

## Step 10: Test the Setup

1. Restart the computer
2. Wait 30 seconds for the server to start
3. Open browser and navigate to: `http://localhost:8000`
4. Login with your superuser credentials
5. Test all features:
   - Create a ledger
   - Add transactions
   - Generate reports
   - Export to Excel/CSV

## Step 11: Create Additional Users

1. Login as Admin
2. Click "Users" in the navigation bar
3. Click "Create New User"
4. Fill in details and assign to appropriate group:
   - **Admin**: Full access (create users, delete ledgers, etc.)
   - **Staff**: Limited access (view and manage transactions only)

## Production Usage Notes

### Accessing the Application

- On the same machine: `http://localhost:8000`
- From other computers on the network: `http://[MACHINE-IP]:8000`

To find machine IP:
```powershell
ipconfig
```
Look for "IPv4 Address"

### Important: Windows Firewall

To allow network access:

1. Open Windows Defender Firewall
2. Click "Advanced settings"
3. Click "Inbound Rules" → "New Rule"
4. Rule Type: Port
5. TCP Port: 8000
6. Allow the connection
7. Name: "Daybook Server"

### Backup Database

The database file is located at:
```
C:\Apps\daybook_lite\daybook_lite\db.sqlite3
```

**Backup schedule recommendations:**
- Daily: Copy `db.sqlite3` to backup folder
- Weekly: Copy entire project folder

Simple backup script (`backup_database.bat`):
```batch
@echo off
set BACKUP_DIR=C:\Backups\Daybook
set DATE=%date:~-4,4%%date:~-10,2%%date:~-7,2%
mkdir "%BACKUP_DIR%\%DATE%" 2>nul
copy "C:\Apps\daybook_lite\daybook_lite\db.sqlite3" "%BACKUP_DIR%\%DATE%\db.sqlite3"
echo Database backed up to %BACKUP_DIR%\%DATE%
```

### Stopping the Server

**Method 1: Task Manager**
1. Press `Ctrl + Shift + Esc`
2. Find `python.exe` process
3. Right-click → End Task

**Method 2: PowerShell**
```powershell
Get-Process python | Stop-Process
```

### Troubleshooting

**Server doesn't start:**
- Check if Python is installed: `python --version`
- Check if virtual environment exists: Look for `.venv` folder
- Check Windows Event Viewer for errors

**Can't access from browser:**
- Verify server is running: Check Task Manager for `python.exe`
- Check firewall settings
- Try: `http://127.0.0.1:8000` instead of `localhost`

**Database errors:**
- Ensure migrations are run: `python manage.py migrate`
- Check database file permissions
- Restore from backup if corrupted

**ImportError or ModuleNotFoundError:**
- Activate virtual environment
- Reinstall dependencies: `pip install django==6.0.2 openpyxl`

## Security Recommendations

1. **Change SECRET_KEY** in `settings.py`:
   - Generate new key: 
     ```powershell
     python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
     ```
   - Replace in settings.py

2. **Regular backups**: Schedule daily database backups

3. **User passwords**: Enforce strong passwords (8+ characters, mixed case, numbers)

4. **Network access**: Only allow trusted IPs if exposing to network

5. **Updates**: Keep Python and Django updated for security patches

## Production-Ready Checklist

- [ ] Python installed and in PATH
- [ ] Virtual environment created
- [ ] All dependencies installed
- [ ] Migrations applied
- [ ] Superuser created
- [ ] Admin and Staff groups created
- [ ] DEBUG = False in settings.py
- [ ] ALLOWED_HOSTS configured
- [ ] Static files collected
- [ ] Auto-start configured
- [ ] Firewall configured (if network access needed)
- [ ] Backup system in place
- [ ] Test all features working
- [ ] Additional users created
- [ ] SECRET_KEY changed

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review Django logs in `daybook_lite/logs/` folder
3. Use `view_logs.bat` to view logs easily
4. Check LOGGING_GUIDE.md for detailed logging information
5. Check Windows Event Viewer
6. Contact your system administrator

## Logging and Monitoring

The application maintains detailed logs for troubleshooting and auditing:

**Log Files Location:** `C:\Apps\daybook_lite\daybook_lite\logs\`

**Log Types:**
- `daybook.log` - General application activity
- `daybook_errors.log` - Error messages and exceptions
- `security.log` - User authentication and permissions
- `transactions.log` - All transaction and ledger operations

**Viewing Logs:**
1. Run `view_logs.bat` for interactive log viewer
2. Or manually open log files with Notepad
3. See LOGGING_GUIDE.md for detailed instructions

**Log Rotation:**
- Logs automatically rotate at 10 MB
- Keeps 10 backup copies
- No manual intervention needed

---

**Version:** 1.0  
**Last Updated:** February 8, 2026  
**Django Version:** 6.0.2  
**Python Version:** 3.11+
