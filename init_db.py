import sys
from pathlib import Path

# Add src to python path to allow imports
sys.path.append(str(Path(__file__).parent / "src"))

from mie_lib.db.database import engine, Base
from mie_lib.db.models import User

def init_db():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")
    print(f"Database location: {engine.url}")

if __name__ == "__main__":
    init_db()
