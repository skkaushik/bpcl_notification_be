from fastapi import APIRouter
from services.email_service import get_email_config

router = APIRouter()

@router.get("/email-config/{plant_name}")
def fetch_email_config(plant_name: str):
    data = get_email_config(plant_name)

    if not data:
        return {"success": False, "message": "Plant not found"}

    return {
        "success": True,
        "data": data
    }