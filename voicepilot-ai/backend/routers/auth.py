from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from schemas.user import UserSignup, UserResponse
from services.auth_services import create_user
from schemas.user import UserLogin
from services.auth_services import login_user

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


@router.post(
    "/signup",
    response_model=UserResponse
)
def signup(
    user: UserSignup,
    db: Session = Depends(get_db)
):
    try:
        return create_user(user, db)

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@router.post("/login")
def login(
    user: UserLogin,
    db: Session = Depends(get_db)
):
    try:
        return login_user(user, db)

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )