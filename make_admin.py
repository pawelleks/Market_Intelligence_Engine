import sys
import argparse
from pathlib import Path

# Add src to python path to allow imports
sys.path.append(str(Path(__file__).parent / "src"))

from mie_lib.db.database import SessionLocal
from mie_lib.db.models import User

def make_admin(email: str):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"Error: User with email '{email}' not found.")
            return

        user.is_admin = True
        user.is_approved = True
        db.commit()
        print(f"Success: User '{email}' is now an Admin and Approved.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Promote a user to Admin.")
    parser.add_argument("email", type=str, help="The email of the user to promote")
    args = parser.parse_args()
    
    make_admin(args.email)
