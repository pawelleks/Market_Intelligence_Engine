
import sqlite3
import os

DB_FILE = "data/users.db"

def update_schema():
    if not os.path.exists(DB_FILE):
        print("Database file not found.")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "visit_count" not in columns:
            print("Adding visit_count column to users table...")
            cursor.execute("ALTER TABLE users ADD COLUMN visit_count INTEGER DEFAULT 0")
            conn.commit()
            print("Column added successfully.")
        else:
            print("Column visit_count already exists.")
            
    except Exception as e:
        print(f"Error updating schema: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    update_schema()
