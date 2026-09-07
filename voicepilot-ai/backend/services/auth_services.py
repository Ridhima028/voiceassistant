from sqlalchemy.orm import Session

from models.user import User
from schemas.user import UserSignup
from utils.security import hash_password
from schemas.user import UserLogin
from utils.security import verify_password, create_access_token


def create_user(user: UserSignup, db: Session):

    # Check if email already exists
    existing_user = (
        db.query(User)
        .filter(User.email == user.email)
        .first()
    )

    if existing_user:
        raise Exception("Email already registered")

    # Hash password
    hashed_password = hash_password(user.password)

    # Create User object
    new_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password
    )

    # Save to database
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user

def login_user(user: UserLogin, db: Session):

    # Step 1 : Email se user dhoondo
    existing_user = (
        db.query(User)
        .filter(User.email == user.email)
        .first()
    )

    # Step 2 : User exist hi nahi karta
    if not existing_user:
        raise Exception("Invalid Email or Password")

    # Step 3 : Password verify karo
    if not verify_password(
        user.password,
        existing_user.hashed_password
    ):
        raise Exception("Invalid Email or Password")

    # Step 4 : JWT Token banao
    access_token = create_access_token(
        data={
            "sub": existing_user.email
        }
    )

    # Step 5 : Token return karo
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }