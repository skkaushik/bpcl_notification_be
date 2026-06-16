from app.db.mongodb import users_collection

async def validate_user(email: str, password: str):

    user = await users_collection.find_one(
        {
            "email": email,
            "password": password,
            "isActive": True
        }
    )

    return user