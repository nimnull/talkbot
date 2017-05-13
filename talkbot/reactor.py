from . import commands
from .logger import log


class MessageReactor:

    next_step = None

    commands_map = {
        'add_reaction': commands.add_reaction,
        'start': commands.start
    }

    def __init__(self, message):
        self.message = message
        self.message_text = message.get('text')
        self.response = None

    def process_commands(self, message):
        log.debug("Process commands")
        entities = message.get('entities', [])
        command_ents = [e for e in entities if e['type'] == 'bot_command']

        for marker in command_ents:
            start = marker['offset']
            stop = marker['offset'] + marker['length']
            cmd = self.message_text[start:stop].strip('/')
            log.debug("Got command '%s'" % cmd)
            command_executor = self.commands_map.get(cmd)
            log.debug("Executor '%s'" % command_executor)
            if command_executor is not None:
                return command_executor(self, message)
            else:
                name = message['from'].get('username', message['from']['first_name'])
                self.response = {
                    'text': "There is no command '/{}', @{}".format(cmd, name)
                }
                return None

        self.next_step = self.search_reactions
        return True

    def search_reactions(self, message):
        log.debug("Search reactions")
        pass

    def __aiter__(self):
        self.next_step = self.process_commands
        return self

    async def __anext__(self):
        proceed = self.next_step(self.message)
        if proceed:
            return proceed
        else:
            raise StopAsyncIteration
