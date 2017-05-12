import motor


MONGO_URI = "mongodb://localhost:27017"


def init_database(uri):
    client = motor.motor_asyncio.AsyncIOMotorClient(uri)
    return client['test_database']

db = init_database(MONGO_URI)
