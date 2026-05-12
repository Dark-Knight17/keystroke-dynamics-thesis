import os
import hmac
import hashlib
import sys
from dotenv import load_dotenv
from database import SessionLocal
from models import User
from passlib.context import CryptContext

# Load environment variables from the same directory as this script
script_dir = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path)

SECRET_PEPPER = os.getenv("SECRET_PEPPER")
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def get_stable_hash(identifier: str) -> str:
    """Creates a deterministic hash for database lookups (matching main.py)."""
    if not SECRET_PEPPER:
        raise ValueError("SECRET_PEPPER environment variable not set. Please check backend/.env")
    return hmac.new(
        SECRET_PEPPER.encode('utf-8'),
        identifier.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

def get_password_hash(password: str):
    """Pre-hashes with SHA-256 before storing (matching main.py)."""
    # Matching main.py's implementation exactly
    pre_hash = hashlib.sha256(password.encode()).hexdigest()
    return pwd_context.hash(pre_hash[:72])

def reset_user_password(matric_number):
    db = SessionLocal()
    
    try:
        # Use the same stable hash logic as main.py
        hashed_matric = get_stable_hash(matric_number)
        
        user = db.query(User).filter(User.matric_hash == hashed_matric).first()
        
        if not user:
            print(f"Error: No user found with matric number {matric_number}")
            return

        # Set the temporary password
        temp_password = "password123"
        user.password_hash = get_password_hash(temp_password)
        db.commit()
        
        print(f"Success! Password for {matric_number} has been reset to: {temp_password}")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python backend/admin_reset.py <matric_number>")
    else:
        reset_user_password(sys.argv[1])
