from functools import partial

from talkbot.commands import add_reaction
from .logger import log


class MessageReactor:

    next_step = None

    commands_map = {
        'add_reaction': add_reaction
    }

    def __init__(self, message):
        self.message = message
        self.message_text = message.get('text')
        self.response = None

    def extract_entities(self, message):
        log.debug("Process entities")
        entities = message.get('entities', [])
        command_ents = [e for e in entities if e['type'] == 'bot_command']

        if len(command_ents):
            self.next_step = partial(self.process_commands, command_ents)
            return False

        self.next_step = self.search_reactions
        return False

    def process_commands(self, command_entries, message):
        log.debug("Process commands")
        for marker in command_entries:
            start = marker['offset']
            stop = marker['offset'] + marker['length']
            cmd = self.message_text[start:stop].strip('/')
            log.debug("Got command '%s'" % cmd)
            command_executor = self.commands_map.get(cmd)
            log.debug("Executor '%s'" % command_executor)
            if command_executor is not None:
                return command_executor(message)
            else:
                return None
        return False

    def search_reactions(self, message):
        log.debug("Search reactions")
        pass

    def __aiter__(self):
        self.next_step = self.extract_entities
        return self

    async def __anext__(self):
        rv = self.next_step(self.message)
        log.debug("RV '%s'" % rv)
        if rv is None:
            raise StopAsyncIteration
        else:
            return rv



# entities -> commands -> search reactions
#                |              |
# respond       <-             <-
