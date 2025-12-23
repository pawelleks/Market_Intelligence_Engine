import sqlite3
import os

DB_PATH = "/app/data/users.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "visit_count" in columns:
            print("Column 'visit_count' already exists. Skipping.")
        else:
            print("Adding 'visit_count' column...")
            cursor.execute("ALTER TABLE users ADD COLUMN visit_count INTEGER DEFAULT 0")
            conn.commit()
            print("Migration successful.")
            
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
