import re
import urllib.parse
from itertools import chain

from .entities import Reaction
from .logger import log
from .utils import get_user_repr, url_regex


async def add_reaction(reactor, cmd, message):
    # '/add_reaction phrase1,phrase2;URL'
    text = message['text']
    raw_text = re.sub(r"/%s" % cmd, '', text).strip()
    splitted_text = raw_text.split(';', maxsplit=1)

    if len(splitted_text) > 1:
        patterns, reaction_content = splitted_text
        reaction_content = reaction_content.strip()
    else:
        # image may be passed as file
        patterns = splitted_text
        reaction_content = None

    patterns = patterns.split(',')
    patterns = [p.strip().lower() for p in patterns if p]

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

    reactions = [entity async for entity in Reaction.find_by_pattern(patterns)]

    if reactions:
        found_patterns = map(lambda r: r['patterns'], reactions)
        reactor.response = {
            'text': "There are some reactions already exist: '%s'" % ", ".join(chain.from_iterable(found_patterns))
        }
        return

    await Reaction.create(reaction)

    reactor.response = {
        'text': "Saved reaction for `{}` by {}".format(", ".join(patterns), get_user_repr(message['from']))
    }


def start(reactor, cmd, message):
    reactor.response = {
        'chat_id': message['from']['id'],
        'text': "Чо-чо попячса"
    }


def help(reactor, cmd, message):
    reactor.response = {
        'chat_id': message['from']['id'],
        'parse_mode': "markdown",
        'text': urllib.parse.quote(
            "*Commands are:*\n"
            "`/add_reaction` - add some reaction from bot (text or image) for phrases\n"
            "Format: /add_reaction phrase1,[phrase2],...[phraseN];URL\n\n"
            "`/start` - dummy command\n\n"
            "`/help` - This help text")
    }
