from mongodb  import email_config_collection

def get_email_config(plant_name):
    return email_config_collection.find_one(
        {"plantName": plant_name},
        {"_id": 0}
    )