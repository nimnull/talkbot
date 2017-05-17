import re
from http import HTTPStatus
from itertools import chain

import aiohttp
import inject
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from talkbot.entities import Reaction
from talkbot.utils import get_user_repr, url_regex, fetch_file
from .logger import log


async def add_reaction(reactor, cmd, message):
    # '/add_reaction действительно,в самом деле; http://cs4.pikabu.ru/images/big_size_comm/2015-04_1/14282673621008.png'
    text = message['text']
    raw_text = re.sub(r"/%s\s+" % cmd, '', text)
    splitted_text = raw_text.split(';', maxsplit=1)

    if len(splitted_text) > 1:
        patterns, reaction_content = splitted_text
        reaction_content = reaction_content.strip()
    else:
        # image may be passed as file
        patterns = splitted_text
        reaction_content = None

    patterns = patterns.split(',')
    patterns = [p.strip() for p in patterns if p]

    reaction = {
        'id': None,
        'patterns': patterns,
        'created_by': message['from'],
        'created_at': message['date'],
        'image_id': '',
        'image_url': '',
        'text': ''
    }

    if reaction_content and url_regex.match(reaction_content):
        log.debug('URL: %s', reaction_content)
        reaction['image_url'] = reaction_content
    elif reaction_content:
        reaction['text'] = reaction_content

    db = inject.instance(AsyncIOMotorDatabase)
    reactions = [entity async for entity in db[Reaction.collection].find({'patterns': {'$in': patterns}})]
    if reactions:
        found_patterns = map(lambda r: r['patterns'], reactions)
        reactor.response = {
            'text': "There are some reactions already exist: '%s'" % ", ".join(chain.from_iterable(found_patterns))
        }
        return

    await db[Reaction.collection].insert_one(Reaction.from_dict(**reaction).to_dict())

    reactor.response = {
        'text': "Saved reaction for `{}` by {}".format(", ".join(patterns), get_user_repr(message['from']))
    }


def start(reactor, cmd, message):
    reactor.response = {
        'chat_id': message['from']['id'],
        'text': "Чо-чо попячса"
    }
