# Daybook Lite - Quick Start Guide

## For End Users (Client Machine)

### Starting the Application

The Daybook server starts automatically when you log in to Windows. If not:

1. **Manual Start:**
   - Double-click: `start_daybook_hidden.vbs`
   - Or run: `start_daybook.bat` (shows console window)

2. **Access the Application:**
   - Open your web browser
   - Go to: `http://localhost:8000`
   - Login with your credentials

### Using Daybook Lite

#### For Admin Users

**Managing Ledgers:**
1. Home page shows all ledger cards with opening/closing balances
2. Click "+ Add Ledger" button to create new ledgers
3. Click on any ledger card to view details
4. Use three-dot menu on cards for Edit/Delete options

**Managing Transactions:**
1. Fill the transaction form on the Home page
2. Select Date, Ledger, Amount, Type (Debit/Credit)
3. Add remarks (optional)
4. Click "Save Transaction"

**Viewing Reports:**
1. Click "Report" in navigation
2. Select date and/or ledger to filter
3. View ledger balance summary and transaction list
4. Export options: Print, CSV, or Excel

**Managing Users:**
1. Click "Users" in navigation
2. View all users in the system
3. Click "Create New User" to add users
4. Assign users to Admin or Staff groups
5. Click on username to view details
6. Promote Staff users to Admin if needed

#### For Staff Users

Staff users can:
- View and manage transactions
- View reports and export data
- View their profile settings
- Cannot: Create users, delete ledgers, or access admin functions

### Daily Operations

**Adding Transactions:**
1. Login to the application
2. On Home page, use the transaction form
3. Fill all required fields (Date, Ledger, Amount, Type)
4. Click "Save Transaction"
5. Transaction appears in the list instantly

**Viewing Ledger Balances:**
- Home page shows all ledgers with current balances
- Click any ledger to see transaction history
- Opening and closing balances update automatically

**Generating Reports:**
1. Go to Report page
2. Select the date you want to view
3. Optionally filter by specific ledger
4. Click "Filter" button
5. Review ledger summaries and transactions
6. Export as needed (Print/CSV/Excel)

### Troubleshooting

**Cannot access the application:**
- Check if server is running: Open Task Manager, look for `python.exe`
- Restart the server: Double-click `start_daybook_hidden.vbs`
- Try different URL: `http://127.0.0.1:8000`

**Forgot password:**
- Contact your administrator to reset password
- Admins can reset passwords through Django admin panel

**Application is slow:**
- Close unused browser tabs
- Restart the server
- Restart your computer

**Need help:**
- Contact your system administrator
- Refer to the full DEPLOYMENT_GUIDE.md

### Backup Your Data

**Important:** Regular backups are crucial!

1. Run `backup_database.bat` daily or weekly
2. Backups are saved to: `C:\Backups\Daybook\`
3. Keep at least 7 days of backups

### Keyboard Shortcuts

- **Ctrl + S** on transaction form: Save transaction (when in form field)
- **Print shortcut**: Ctrl + P (on report page after clicking Print)

### Best Practices

1. **Daily Routine:**
   - Login each morning
   - Review ledger balances
   - Add transactions as they occur
   - Generate end-of-day report

2. **Weekly Routine:**
   - Backup database
   - Review all transactions
   - Generate weekly reports

3. **Monthly Routine:**
   - Export monthly reports to Excel
   - Archive old data
   - Review user access

### Support Contact

For technical support or questions:
- Contact: Your System Administrator
- Email: [Your Support Email]
- Phone: [Your Support Phone]

---

**Quick Access URLs:**
- Main Application: `http://localhost:8000`
- Admin Interface: `http://localhost:8000/admin`

**Version:** 1.0  
**Last Updated:** February 8, 2026
