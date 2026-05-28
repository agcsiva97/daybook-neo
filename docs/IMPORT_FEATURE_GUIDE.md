# Import Feature Implementation Guide

## Overview
A comprehensive import feature has been added to the Sync History page that allows importing JSON files containing types, accounts, and transactions. The feature supports both full exports and incremental exports.

## Features

### 1. Import Button Location
- **Page**: Sync History (`/admin/sync-history/`)
- **Position**: Next to the Export button in the header
- **Appearance**: Blue "Import" button with download icon

### 2. Supported JSON Formats

#### Format A: Full Export (Flat Structure)
```json
{
  "shop_id": "SHP8B1EC",
  "shop_name": "Thaila Bankers",
  "export_mode": "all",
  "types": [{...}],
  "accounts": [{...}],
  "transactions": [{...}]
}
```

#### Format B: Incremental Export (Nested Structure)
```json
{
  "shop_id": "SHP8B1EC",
  "shop_name": "Thaila Bankers", 
  "export_mode": "after_last_export",
  "types": {
    "created": [{...}],
    "updated": [{...}],
    "deleted": [{...}]
  },
  "accounts": {
    "created": [{...}],
    "updated": [{...}],
    "deleted": [{...}]
  },
  "transactions": {
    "created": [{...}],
    "updated": [{...}],
    "deleted": [{...}]
  }
}
```

### 3. Import Logic

When you upload a JSON file:

1. **Format Detection**: System automatically detects flat vs nested format
2. **Shop Validation**: Verifies shop exists in database
3. **System User**: Gets or creates 'system' user for tracking
4. **Record Processing**:
   - Records WITH IDs that exist → **UPDATE** existing record
   - Records WITHOUT IDs or non-existent → **CREATE** new record
5. **User Attribution**: All created/updated records marked as by 'system' user
6. **Tracking**: Each import creates ImportHistory and ImportDetails records
7. **Result**: Returns summary of created/updated records

### 4. How to Use

#### Step 1: Export Data
1. Go to Shops list
2. Select a shop
3. Click "Export" button  
4. Choose export type (All, Date Range, or After Last Export)
5. Download the JSON file

#### Step 2: Import to Different System/Shop
1. Go to Sync History page
2. Click the "Import" button (blue button with download icon)
3. Select the JSON file you exported
4. Review the import information dialog
5. Click "Import"
6. Wait for processing
7. See success message with summary

#### Step 3: Verify Import
- Check synced history table for new import entry
- Click "Details" to see what was imported
- Verify data appears in the shop

## Technical Details

### Endpoint
- **URL**: `/manager/import-transactions/`
- **Method**: POST
- **Content-Type**: multipart/form-data
- **Parameter**: `json_file` (JSON file)

### Response
```json
{
  "success": true,
  "message": "Import completed successfully",
  "summary": {
    "types": {"created": 5, "updated": 2},
    "accounts": {"created": 1, "updated": 0},
    "transactions": {"created": 10, "updated": 3}
  }
}
```

### Files Imported
1. **Types** (Account classification categories)
   - ID preserved if provided
   - Group reference preserved

2. **Accounts** (Ledger entries)
   - ID preserved if provided
   - Account type reference preserved
   - Priority and admin flags preserved

3. **Transactions** (Financial transactions)
   - ID preserved if provided
   - Account reference preserved
   - Transaction date and amount preserved
   - Tally flag preserved

## Important Notes

### Data Preservation
- If a record ID exists in JSON and in database → record is UPDATED
- If a record ID is missing or doesn't exist → new record CREATED
- Original created_at timestamps are NOT preserved (uses import time)
- Created/Updated by is ALWAYS 'system' user (not current user)

### System User
- Automatically created if doesn't exist
- Username: `system`
- First Name: `System`
- Last Name: `Automated`
- Status: Inactive (cannot login)
- Purpose: Track automated imports

### Import History
- Every import creates an ImportHistory record
- Each individual record is tracked in ImportDetails
- Failed records are logged with error message
- Successful records marked with action (Created/Updated)

### Error Handling
- Invalid JSON → rejected with message
- Missing shop_id → rejected with message
- Missing file → rejected with message
- Individual record errors → logged but import continues
- All changes are atomic (all-or-nothing for the transaction)

## Troubleshooting

### "Shop ID not found in import file"
- The JSON file doesn't have a `shop_id` field
- Make sure you're using a JSON file exported from this system

### "Invalid JSON file"
- The file is corrupted or not valid JSON
- Download a fresh copy from the export feature

### Import completed but records missing
- Check the import details page
- Some records may have failed if account/type references don't exist
- Verify all required records exist in the destination shop

### System user already exists
- This is normal, system handles it automatically
- Verify user "system" exists in the admin panel

## Best Practices

1. **Always export before importing**
   - Don't manually edit JSON files
   - Use the export feature to ensure proper format

2. **Test with a copy**
   - Import to a test shop first
   - Verify all data transferred correctly before production

3. **Keep export files**
   - Maintain backups of exported JSON
   - Good for disaster recovery

4. **Monitor imports**
   - Check the Sync History page for all imports
   - Review ImportDetails if anything unexpected appears

5. **Use incremental exports**
   - "After Last Export" mode is more efficient
   - Better for frequent syncs

## See Also
- [Export Feature Documentation](README.md)
- [Sync History](./daybook_lite/manager/templates/manager/sync_history.html)
- [Import View Code](./daybook_lite/manager/views.py) - `import_transactions()` function
