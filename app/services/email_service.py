from app.db.mongodb import db

async def get_email_config(plant_name: str):
    return await db.email_config.find_one(
        {"plantName": plant_name},
        {"_id": 0}
    )