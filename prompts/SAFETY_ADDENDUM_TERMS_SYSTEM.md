# SAFETY ADDENDUM - Terms System Implementation

**CRITICAL**: Read this BEFORE starting implementation

---

## Pre-Implementation Safety Checklist

### 1. Database Backup (MANDATORY - DO NOT SKIP)

**Before making ANY changes**, create a full database backup:

```bash
# PostgreSQL
pg_dump -U your_user -d blindmonkey_db -F c -b -v -f backup_$(date +%Y%m%d_%H%M%S).dump

# OR MySQL
mysqldump -u your_user -p blindmonkey_db > backup_$(date +%Y%m%d_%H%M%S).sql

# OR SQLite
sqlite3 blindmonkey.db ".backup 'backup_$(date +%Y%m%d_%H%M%S).db'"
```

**Verification**:
- [ ] Backup file created
- [ ] File size > 0 (not empty)
- [ ] Downloaded to local machine (NOT just on server)
- [ ] Can open/verify backup

**Do NOT proceed without a verified backup!**

---

### 2. Pre-Migration Verification

**Record current state**:

```sql
-- Count total users (should be 155)
SELECT COUNT(*) as total_users FROM users;

-- Count by status
SELECT status, COUNT(*) FROM users GROUP BY status;

-- Sample 5 users to verify data structure
SELECT id, email, name, role, status, created_at 
FROM users 
ORDER BY id 
LIMIT 5;
```

**Save this output!** You'll compare after migration.

---

### 3. Migration Safety

**The migration is SAFE because**:

```sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS 
  terms_accepted BOOLEAN DEFAULT FALSE,
  ...
```

- ✅ Only **ADDS** columns (doesn't modify existing)
- ✅ Uses `IF NOT EXISTS` (safe to re-run)
- ✅ Sets defaults (no NULL issues)
- ✅ Doesn't touch existing data

**Existing columns remain unchanged**:
- `id`, `email`, `name`, `role`, `status`, `created_at` → **UNTOUCHED**

**New columns added**:
- `terms_accepted` → `FALSE` (all users)
- `terms_version` → `NULL`
- `email_notifications` → `TRUE`
- `deleted` → `FALSE`

---

### 4. Post-Migration Verification

**Immediately after migration, verify**:

```sql
-- User count should be identical
SELECT COUNT(*) as total_users FROM users;
-- Should still be 155

-- Verify no data loss
SELECT id, email, name, role, status, created_at 
FROM users 
ORDER BY id 
LIMIT 5;
-- Compare with pre-migration output - should be IDENTICAL

-- Check new columns
SELECT id, email, terms_accepted, terms_version, email_notifications
FROM users 
LIMIT 5;
-- Expected: terms_accepted = FALSE, terms_version = NULL, email_notifications = TRUE
```

**If anything doesn't match → ROLLBACK immediately!**

---

## Rollback Procedure

### If Migration Fails or Data Lost:

**Step 1: Stop Backend**
```bash
systemctl stop your-backend-service
# OR
docker-compose down
# OR kill the process
```

**Step 2: Restore Database**
```bash
# PostgreSQL
pg_restore -U your_user -d blindmonkey_db -c backup_file.dump

# MySQL
mysql -u your_user -p blindmonkey_db < backup_file.sql

# SQLite
cp backup_file.db blindmonkey.db
```

**Step 3: Verify Restore**
```sql
SELECT COUNT(*) FROM users;
-- Should be 155 again

SELECT id, email, name FROM users LIMIT 5;
-- Should match original
```

**Step 4: Revert Code**
```bash
git revert <commit-hash>
# OR
git reset --hard <previous-commit>
```

**Step 5: Restart Backend**
```bash
systemctl start your-backend-service
```

---

## What Happens to 155 Existing Users

**Immediately after deployment**:
- All 155 users: `terms_accepted = FALSE`
- No data lost, no access revoked YET

**When they next login**:
- Terms modal appears (blocks dashboard)
- They must accept terms
- Once accepted: `terms_accepted = TRUE` → normal access

**This is by design and expected!**

---

## Testing Order (CRITICAL)

**DO NOT test on production users first!**

### Test Order:
1. ✅ **Test on YOUR admin account first**
   - Use admin reset button
   - Verify terms flow works
   - Verify profile page works
   - Verify you can still access everything after accepting

2. ✅ **Then test on ONE test user** (if possible)
   - Not a real user if you can avoid it
   - Verify they see terms
   - Verify acceptance works

3. ✅ **Monitor logs for errors**
   - Check backend logs
   - Check browser console

4. ✅ **Only then** let real users login

---

## Monitoring After Deployment

### Watch for Issues:

**Backend logs**:
```bash
tail -f /var/log/your-backend.log
# Look for errors related to:
# - Database connections
# - Email sending
# - Terms acceptance
```

**Database monitoring**:
```sql
-- How many users accepted terms so far?
SELECT COUNT(*) FROM users WHERE terms_accepted = TRUE;

-- Any errors in logs?
SELECT * FROM error_logs ORDER BY created_at DESC LIMIT 10;
```

**User feedback**:
- Check if users report login issues
- Monitor support emails
- Check if emails are being sent

---

## Emergency Contacts

**If something goes wrong**:

1. **Immediate**: Rollback (see procedure above)
2. **Report**: Document what went wrong
3. **Fix**: Debug on dev environment, not production
4. **Re-deploy**: Only after thoroughly tested

---

## Agent Instructions

**As the implementing agent, you MUST**:

1. ✅ **VERIFY backup exists before starting**
2. ✅ **Run pre-migration verification queries**
3. ✅ **Show output of user count before and after**
4. ✅ **Test migration on dev first if available**
5. ✅ **Report any discrepancies immediately**
6. ✅ **Do NOT proceed if user count changes**

**If anything unexpected happens**:
- STOP immediately
- Report the issue
- DO NOT continue until resolved
- Have rollback plan ready

---

## Success Criteria

Migration is successful ONLY when:

- ✅ User count unchanged (still 155)
- ✅ All existing user data intact (spot-check verified)
- ✅ New columns added with correct defaults
- ✅ Backend starts without errors
- ✅ Admin can login and see terms modal
- ✅ Terms acceptance saves correctly
- ✅ Profile page loads without errors

**If ANY of these fail → ROLLBACK**

---

## Final Safety Notes

**Remember**:
- Database backups are MANDATORY, not optional
- Test on your own account first
- Monitor closely for first 24 hours
- Have rollback plan ready
- Better to be cautious than fix data loss

**With proper backup, this migration is SAFE.**

The schema changes only add columns, they don't modify existing data. Your 155 users' data will remain completely intact.

---

**Proceed only after:**
1. ✅ Database backup created and verified
2. ✅ Pre-migration state recorded
3. ✅ Rollback plan understood
4. ✅ Testing strategy clear

**Good luck! Be careful and methodical.**
