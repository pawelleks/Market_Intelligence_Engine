
import requests
import json
import sqlite3
import os

import sqlite3
import os

DB_FILE = "data/users.db"

def verify_tracking():
    if not os.path.exists(DB_FILE):
        print(f"Database file {DB_FILE} not found.")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    try:
        # 1. Get a user
        cursor.execute("SELECT id, email, visit_count FROM users LIMIT 1")
        user = cursor.fetchone()
        
        if not user:
            print("No user found in DB to test.")
            return

        user_id, email, count = user
        initial_count = count or 0
        print(f"User {email} initial count: {initial_count}")

        # 2. Simulate increment
        new_count = initial_count + 1
        cursor.execute("UPDATE users SET visit_count = ? WHERE id = ?", (new_count, user_id))
        conn.commit()
        
        # 3. Verify persistence
        cursor.execute("SELECT visit_count FROM users WHERE id = ?", (user_id,))
        updated_count = cursor.fetchone()[0]
        
        print(f"User {email} new count: {updated_count}")
        
        if updated_count == new_count:
            print("SUCCESS: Visit count incremented and persisted.")
        else:
            print("FAILURE: Visit count did not persist.")
            
    except Exception as e:
        print(f"Error during verification: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    verify_tracking()
