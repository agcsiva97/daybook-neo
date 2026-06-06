# Daybook Lite - Logging System Documentation

## Overview

The Daybook application uses Python's built-in logging framework to track system activities, user actions, and errors. This helps with debugging, security auditing, and monitoring application health.

## Log Files Location

All log files are stored in: `daybook_lite/logs/`

### Log Files

1. **daybook.log** - General application logs
   - All INFO level messages from the application
   - User actions, page views, and normal operations
   - Maximum size: 10 MB per file
   - Keeps 10 backup files (100 MB total)

2. **daybook_errors.log** - Error logs
   - ERROR and CRITICAL level messages only
   - Stack traces and exception details
   - Failed operations and system errors
   - Maximum size: 10 MB per file
   - Keeps 10 backup files (100 MB total)

3. **security.log** - Security and authentication logs
   - User login/logout events
   - User creation and permission changes
   - Password changes
   - Profile modifications
   - Maximum size: 5 MB per file
   - Keeps 5 backup files (25 MB total)

4. **transactions.log** - Transaction-specific logs
   - All transaction CRUD operations
   - Ledger operations
   - Report generations
   - Export operations (CSV/Excel)
   - Maximum size: 10 MB per file
   - Keeps 10 backup files (100 MB total)

## Log Levels

The application uses these log levels (in order of severity):

1. **DEBUG** - Detailed information for diagnosing problems (disabled in production)
2. **INFO** - Confirmation that things are working as expected
3. **WARNING** - Something unexpected happened, or potential issues
4. **ERROR** - A serious problem that prevented a function from working
5. **CRITICAL** - A very serious error that may cause application failure

## What Gets Logged

### Transaction Operations
- **Creation** (INFO): User, transaction type, amount, ledger
- **Editing** (INFO): User, transaction ID, changes made
- **Deletion** (WARNING): User, transaction details
- **Balance validation failures** (ERROR): User, attempted operation

### Ledger Operations
- **Creation** (INFO): User, ledger name, initial balance
- **Editing** (INFO): User, ledger ID, changes
- **Deletion** (WARNING): User, ledger name
- **Related transactions check** (WARNING): Blocked deletions

### Report & Export Operations
- **Report generation** (INFO): Date, filters, user
- **CSV export** (INFO): Export parameters, user
- **Excel export** (INFO): Export parameters, user

### User Management
- **User creation** (INFO): Creator, new user, group assignment
- **Profile editing** (INFO): User, fields changed
- **Password change** (INFO): User
- **Logout** (INFO): User
- **Promote to admin** (WARNING): Admin, promoted user

### System Events
- **Django requests** (ERROR): Failed HTTP requests
- **Security events** (INFO): Authentication attempts
- **Exceptions** (ERROR): Full stack traces

## Log Format

### Verbose Format (File Logs)
```
LEVEL TIMESTAMP MODULE PROCESS_ID THREAD_ID MESSAGE
```

Example:
```
INFO 2026-02-08 14:30:45,123 views 12345 67890 Transaction created by admin: DEBIT 5000.00 on Cash Ledger
```

### Simple Format (Console)
```
LEVEL TIMESTAMP MESSAGE
```

Example:
```
INFO 2026-02-08 14:30:45 Transaction created by admin: DEBIT 5000.00 on Cash Ledger
```

## Viewing Logs

### Windows PowerShell

**View last 50 lines of general log:**
```powershell
Get-Content .\logs\daybook.log -Tail 50
```

**View last 50 lines of error log:**
```powershell
Get-Content .\logs\daybook_errors.log -Tail 50
```

**Monitor log in real-time:**
```powershell
Get-Content .\logs\daybook.log -Wait -Tail 50
```

**Search for specific user actions:**
```powershell
Select-String -Path .\logs\daybook.log -Pattern "username"
```

**Search for errors:**
```powershell
Select-String -Path .\logs\daybook_errors.log -Pattern "ERROR"
```

**View security log:**
```powershell
Get-Content .\logs\security.log -Tail 50
```

**View transactions log:**
```powershell
Get-Content .\logs\transactions.log -Tail 50
```

### Using Notepad or Text Editor

Simply open the log files with any text editor:
- Right-click log file → Open With → Notepad

## Log Rotation

Logs automatically rotate when they reach their maximum size:

1. When `daybook.log` reaches 10 MB:
   - Renamed to `daybook.log.1`
   - New empty `daybook.log` is created

2. When it fills again:
   - `daybook.log.1` → `daybook.log.2`
   - `daybook.log` → `daybook.log.1`
   - New empty `daybook.log` is created

3. After 10 rotations:
   - Oldest file (`daybook.log.10`) is deleted
   - Newer files are kept

This ensures logs don't consume too much disk space while maintaining history.

## Maintenance

### Archiving Old Logs

Create monthly archives of logs:

```powershell
# Create archive folder
New-Item -Path "C:\Backups\Daybook\Logs\Archive" -ItemType Directory -Force

# Archive logs
$date = Get-Date -Format "yyyy-MM"
Copy-Item "C:\Apps\daybook_lite\daybook_lite\logs\*.log.*" "C:\Backups\Daybook\Logs\Archive\$date\"
```

### Clearing Old Logs

Only clear logs if you've archived them:

```powershell
# Clear rotated logs (keeps current logs)
Remove-Item "C:\Apps\daybook_lite\daybook_lite\logs\*.log.*"
```

### Monitoring Disk Space

Check log folder size:

```powershell
Get-ChildItem ".\logs" -Recurse | Measure-Object -Property Length -Sum | Select-Object @{Name="Size(MB)";Expression={[math]::Round($_.Sum / 1MB, 2)}}
```

## Troubleshooting

### Logs Not Being Created

1. Check if `logs` directory exists:
   ```powershell
   Test-Path .\logs
   ```

2. Check directory permissions:
   - Ensure the application has write access to `logs` folder

3. Restart the Django server

### Logs Too Large

1. Check current log sizes:
   ```powershell
   Get-ChildItem .\logs\*.log | Select-Object Name, @{Name="Size(MB)";Expression={[math]::Round($_.Length / 1MB, 2)}}
   ```

2. Archive old rotated logs:
   ```powershell
   Move-Item .\logs\*.log.* C:\Backups\Daybook\Logs\
   ```

### Finding Specific Events

**Find all failed logins:**
```powershell
Select-String -Path .\logs\security.log -Pattern "failed|Failed|error"
```

**Find specific transaction:**
```powershell
Select-String -Path .\logs\transactions.log -Pattern "Transaction created.*5000"
```

**Find user actions:**
```powershell
Select-String -Path .\logs\daybook.log -Pattern "username: admin"
```

**Find errors from last 24 hours:**
```powershell
$yesterday = (Get-Date).AddDays(-1)
Get-Content .\logs\daybook_errors.log | Where-Object { 
    $_ -match '\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}' -and 
    [DateTime]::Parse(($matches[0])) -gt $yesterday 
}
```

## Best Practices

1. **Regular Monitoring**
   - Check error logs daily
   - Review security logs weekly
   - Monitor disk space monthly

2. **Archiving**
   - Archive logs monthly
   - Keep archives for at least 6 months
   - Store archives with database backups

3. **Security**
   - Protect log files from unauthorized access
   - Don't share logs containing sensitive information
   - Review security logs for suspicious activities

4. **Performance**
   - Logs are written asynchronously
   - Minimal performance impact
   - Automatic rotation prevents disk overflow

## Integration with Monitoring Tools

Logs can be integrated with:
- Windows Event Viewer (custom event sources)
- Splunk or ELK Stack (for enterprise monitoring)
- Email alerts for critical errors
- Custom monitoring dashboards

## Configuration

Logging is configured in `daybook_lite/settings.py` under the `LOGGING` dictionary.

To adjust log levels, modify the logger configuration:

```python
'entries': {
    'handlers': ['console', 'file', 'transaction_file'],
    'level': 'INFO',  # Change to DEBUG for more detail
    'propagate': False,
},
```

To change rotation settings:

```python
'file': {
    'maxBytes': 1024 * 1024 * 10,  # Change 10 to desired MB
    'backupCount': 10,              # Change number of backups
}
```

## Support

For issues related to logging:
1. Check this documentation
2. Review settings.py LOGGING configuration
3. Verify logs directory permissions
4. Check Django documentation: https://docs.djangoproject.com/en/6.0/topics/logging/

---

**Last Updated:** February 8, 2026  
**Application Version:** 1.0
