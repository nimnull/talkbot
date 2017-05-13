import re

from talkbot.utils import get_user_repr, url_regex
from .logger import log


def add_reaction(reactor, cmd, message):
    # '/add_reaction действительно,в самом деле; http://cs4.pikabu.ru/images/big_size_comm/2015-04_1/14282673621008.png'
    text = message['text']
    raw_text = re.sub(r"/%s\s+" % cmd, '', text)
    splitted_text = raw_text.split(';', maxsplit=1)

    if len(splitted_text) > 1:
        patterns, reaction_url = splitted_text
        reaction_url = reaction_url.strip()
    else:
        # image may be passed as file
        patterns = splitted_text
        reaction_url = None

    patterns = patterns.split(',')
    patterns = [p.strip() for p in patterns if p]

    if reaction_url and url_regex.match(reaction_url):
        log.debug('URL: %s', reaction_url)

    # message['date']

    user_repr = get_user_repr(message['from'])

    reactor.response = {
        'text': "Saved reaction for {} by {}".format(",".join(patterns), user_repr)
    }


def start(reactor, cmd, message):
    reactor.response = {
        'chat_id': message['from']['id'],
        'text': "Чо-чо попячса"
    }
