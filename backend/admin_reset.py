from database import SessionLocal
from models import User
from passlib.context import CryptContext
import hashlib
import sys

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def reset_user_password(matric_number):
    db = SessionLocal()
    
    # Normalize the matric number exactly like our new login logic
    hashed_matric = hashlib.sha256(matric_number.encode()).hexdigest()
    
    user = db.query(User).filter(User.matric_hash == hashed_matric).first()
    
    if not user:
        print(f"Error: No user found with matric number {matric_number}")
        db.close()
        return

    # Set the temporary password
    temp_password = "password123"
    user.password_hash = pwd_context.hash(temp_password)
    db.commit()
    
    print(f"Success! Password for {matric_number} has been reset to: {temp_password}")
    db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python backend/admin_reset.py <matric_number>")
    else:
        reset_user_password(sys.argv[1])