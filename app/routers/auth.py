from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.auth_services import validate_user

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)
class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/login")
async def login(payload: LoginRequest):

    user = await validate_user(
        payload.email,
        payload.password
    )

    if user:
        return {
            "success": True,
            "message": "Login successful"
        }

    raise HTTPException(
        status_code=401,
        detail="Invalid email or password"
    )