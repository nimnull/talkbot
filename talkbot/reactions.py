from .logger import log


def process_chat_left(bot, member, chat):
    if member['username'] == bot.username:
        log.info("Removed from chat %s", chat['title'])


def process_chat_joined(bot, member, chat):
    if member['username'] == bot.username:
        log.info("Added to chat %s", chat['title'])


def process_entities(bot, entry, message):
    pass
