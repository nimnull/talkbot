import asyncio

import inject
import pandas as pd

from PIL import Image
from imagehash import hex_to_hash
from motor.motor_asyncio import AsyncIOMotorDatabase
from sklearn.ensemble import GradientBoostingClassifier

from . import commands
from .entities import Reaction, ImageFinger, Config
from .logger import log
from .utils import calc_scores, HASH_SIZE, get_diff_vector


class MessageReactor:   # TODO: add tests
    config = inject.attr(Config)
    image_model = inject.attr(GradientBoostingClassifier)

    next_step = None

    commands_map = {
        'add_reaction': commands.add_reaction,
        'start': commands.start,
        'help': commands.help
    }

    def __init__(self, message, bot_instance):
        self.message = message
        self.chat_id = message.get('chat', {}).get('id')
        self.message_text = message.get('text')
        self.response = None
        self.db = inject.instance(AsyncIOMotorDatabase)
        self.response = {}
        self.bot = bot_instance

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
                try:
                    if asyncio.iscoroutinefunction(command_executor):
                        log.debug("Executor is coroutine")
                        return await command_executor(self, cmd, message)
                    else:
                        return command_executor(self, cmd, message)
                except:
                    log.error("Failed to process command %s", cmd, exc_info=True)
                    self.response = {
                        'text': "Failed to process %s" % cmd
                    }
                    return
            else:
                name = message['from'].get('username', message['from']['first_name'])
                self.response = {
                    'text': "There is no command '/{}', @{}".format(cmd, name)
                }
                return

        self.next_step = self.search_reactions
        return True

    async def search_reactions(self, message):
        log.debug("Process reactions")
        # short circuit
        if not self.message_text:
            log.debug("no messages here, moving forward")
            self.next_step = self.check_repetitions
            return True

        found = None
        # TODO: optimize it
        async for reaction in Reaction.find():
            r = Reaction.from_dict(**reaction)
            for pattern in r.patterns:
                if pattern in self.message_text.lower():
                    found = r

        # short circuit
        if not found or found.on_hold:
            return
        log.debug("Got reaction: %s", found)

        if found.image_id or found.image_url:
            self.response['photo'] = found.image_id or found.image_url
        elif found.text:
            self.response['text'] = found.text
        else:
            log.debug("Broken reaction: %s", found.to_dict())
        found.update_usage()

    def __aiter__(self):
        self.next_step = self.process_commands
        return self

    async def __anext__(self):
        proceed = await self.next_step(self.message)
        if proceed:
            return proceed
        else:
            raise StopAsyncIteration

    async def check_repetitions(self, message):
        if 'photo' not in message:
            return

        images_by_size = sorted(message['photo'], key=lambda img: img['file_size'], reverse=True)
        image_info = images_by_size[0]

        finger = await ImageFinger.find_one({'chat_id': self.chat_id, 'file_id': image_info['file_id']})
        log.debug("Fingerprint: %s", finger)

        if finger:
            self.response = {
                'text': "100% было",
                'reply_to_message_id': self.message['message_id']
            }
            return

        data = await self.bot.get_file(image_info['file_id'])
        buffer = await self.bot.download_file(data['file_path'])

        img = Image.open(buffer)
        scores = calc_scores(img)
        bool_repr = False
        class_prob = 0
        duplicate = None

        async for finger in ImageFinger.find():
            scores2 = [(name, hex_to_hash(bytes_str, HASH_SIZE))
                       for name, bytes_str in finger['vectors']]
            vector = pd.DataFrame.from_dict([get_diff_vector(scores, scores2)])
            duplicate = finger
            predicted = self.image_model.predict(vector)
            class_probs = self.image_model.predict_proba(vector)
            log.debug("Predict res: %s", predicted)
            log.debug("Probs: %s", class_probs)
            p_class = predicted[0]

            class_prob = class_probs[0][int(p_class)]
            bool_repr = bool(int(p_class))

        if bool_repr:
            self.response = {
                'reply_to_message_id': self.message['message_id'],
                'Text': "Баян (%d%%)" % int(class_prob * 100)
            }
        else:
            await ImageFinger.create({
                'id': None,
                'vectors': ((name, str(img_hash)) for name, img_hash in scores),
                'message': message,
                'file_id': image_info['file_id'],
                'chat_id': self.chat_id
            })


