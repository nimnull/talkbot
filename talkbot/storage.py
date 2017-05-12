import inject
import motor

from talkbot.entities import Config


@inject.param('config', Config)
def init_database(config=None):
    client = motor.motor_asyncio.AsyncIOMotorClient(config.mongo.uri)
    return client[config.mongo.db]
