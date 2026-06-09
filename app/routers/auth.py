from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)

COMPANY_EMAIL = "admin@gmail.com"
COMPANY_PASSWORD = "admin123"


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
async def login(payload: LoginRequest):

    if (
        payload.email == COMPANY_EMAIL
        and payload.password == COMPANY_PASSWORD
    ):
        return {
            "success": True,
            "message": "Login successful"
        }

    raise HTTPException(
        status_code=401,
        detail="Invalid email or password"
    )