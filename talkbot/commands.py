def add_reaction(reactor, message):
    pass


def start(reactor, message):
    reactor.response = {
        'chat_id': message['from']['id'],
        'text': "Чо-чо попячса"
    }
    return None
