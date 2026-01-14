import sys
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

# Add src to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT / "src"))

from mie_lib.db.database import DB_PATH

def backup_database():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = DB_PATH.parent / f"users_backup_{timestamp}.db"
    
    print(f"\n[1/4] Creating backup...")
    try:
        shutil.copy2(DB_PATH, backup_path)
        print(f"✅ Backup created: {backup_path}")
        print(f"✅ Size: {backup_path.stat().st_size} bytes")
        return True
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return False

def verify_pre_migration(cursor):
    print(f"\n[2/4] Pre-migration verification...")
    
    # Check user count
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    print(f"📊 Current user count: {count}")
    
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if "terms_accepted" in columns:
        print("⚠️  Columns already exist! Skipping migration.")
        return False, count
        
    return True, count

def migrate(conn, cursor):
    print(f"\n[3/4] Running migration...")
    
    columns = [
        ("terms_accepted", "BOOLEAN DEFAULT 0"),
        ("terms_accepted_at", "TIMESTAMP"),
        ("terms_version", "VARCHAR(10) DEFAULT '1.0'"),
        ("terms_content", "TEXT"),
        ("email_notifications", "BOOLEAN DEFAULT 1"), # SQLite uses 0/1 for boolean
        ("deleted", "BOOLEAN DEFAULT 0"),
        ("deleted_at", "TIMESTAMP")
    ]
    
    try:
        for col_name, col_def in columns:
            print(f"   Adding {col_name}...")
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
        
        conn.commit()
        print("✅ Migration committed successfully")
        return True
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        return False

def verify_post_migration(cursor, old_count):
    print(f"\n[4/4] Post-migration verification...")
    
    # Verify count unchanged
    cursor.execute("SELECT COUNT(*) FROM users")
    new_count = cursor.fetchone()[0]
    print(f"📊 New user count: {new_count}")
    
    if new_count != old_count:
        print(f"❌ CRITICAL: User count changed! ({old_count} -> {new_count})")
        return False
        
    # Verify columns
    cursor.execute("SELECT id, email, terms_accepted, terms_version, deleted FROM users LIMIT 1")
    row = cursor.fetchone()
    if row:
        print(f"✅ Sample row verification: OK")
        print(f"   ID: {row[0]}")
        print(f"   Terms Accepted: {row[2]}")
        print(f"   Terms Version: {row[3]}")
    else:
        print("ℹ️  No users to verify data structure (Table empty)")
        
    return True

def main():
    if not DB_PATH.exists():
        print(f"❌ Database not found at {DB_PATH}")
        return
        
    print(f"🚀 Starting migration for: {DB_PATH}")
    
    if not backup_database():
        print("❌ Aborting due to backup failure")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        should_run, old_count = verify_pre_migration(cursor)
        
        if should_run:
            if migrate(conn, cursor):
                if verify_post_migration(cursor, old_count):
                    print("\n✨ MIGRATION SUCCESSFUL! ✨")
                else:
                    print("\n⚠️  Migration finished but verification failed!")
            else:
                print("\n❌ MIGRATION FAILED!")
        else:
            print("\n⏹️  Migration skipped (already up to date)")
            
    finally:
        conn.close()

if __name__ == "__main__":
    main()
