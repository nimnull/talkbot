import asyncio

import inject
from motor.motor_asyncio import AsyncIOMotorDatabase

from . import commands
from .entities import Reaction
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
        self.db = inject.instance(AsyncIOMotorDatabase)
        self.response = {}

    async def process_commands(self, message):
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
                if asyncio.iscoroutinefunction(command_executor):
                    log.debug("Executor is coroutine")
                    return await command_executor(self, cmd, message)
                else:
                    return command_executor(self, cmd, message)
            else:
                name = message['from'].get('username', message['from']['first_name'])
                self.response = {
                    'text': "There is no command '/{}', @{}".format(cmd, name)
                }
                return None

        self.next_step = self.search_reactions
        return True

    async def search_reactions(self, message):
        # short circuit
        if not self.message_text:
            return

        found = None
        # TODO: optimize it
        async for reaction in self.db[Reaction.collection].find():
            r = Reaction.from_dict(**reaction)
            for pattern in r.patterns:
                if pattern in self.message_text.lower():
                    found = r

        # short circuit
        if not found:
            return

        if found.image_id or found.image_url:
            self.response['photo'] = found.image_id or found.image_url
        elif found.text:
            self.response['text'] = found.text
        else:
            log.debug("Broken reaction: %s", found.to_dict())

    def __aiter__(self):
        self.next_step = self.process_commands
        return self

    async def __anext__(self):
        proceed = await self.next_step(self.message)
        if proceed:
            return proceed
        else:
            raise StopAsyncIteration
