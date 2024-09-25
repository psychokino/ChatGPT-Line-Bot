from typing import Dict
from collections import defaultdict
import tiktoken
import base64
import json

# OpenAI API Key
api_key = "YOUR_OPENAI_API_KEY"
class MemoryInterface:

    def append(self, user_id: str, message: Dict) -> None:
        pass

    def get(self, user_id: str) -> str:
        return ""

    def remove(self, user_id: str) -> None:
        pass


class Memory(MemoryInterface):

    def __init__(self, system_message, db_instance):
        self.storage = defaultdict(list)
        self.settings = defaultdict(dict)
        self.system_messages = defaultdict(str)
        self.default_system_message = system_message
        self.db = db_instance
        #self.default_settings = {'is_lazy': True, 'gpt_mode': 'gpt-3.5-turbo'}
        self.default_settings = {}

    def _initialize(self, user_id: str):
        self.storage[user_id] = [{
            'role':
            'system',
            'content':
            self.system_messages.get(user_id) or self.default_system_message
        }]

    def _drop_message(self, user_id: str, type = 'text'):
        specific_max_tokens = self.db.dbread(user_id, 'max_token')
        if type == 'image':
            specific_max_tokens = 10000000
            
        memory_message_count = 30
        if len(self.storage.get(
                user_id)) >= (memory_message_count + 1) * 2 + 1:
            self.storage[user_id] = [
                self.storage[user_id][0]
            ] + self.storage[user_id][-(memory_message_count * 2):]

        print('shrinking...')
        while self._get_token_length(user_id) > specific_max_tokens:
            if len(self.storage[user_id]) > 2:
                self.storage[user_id] = [self.storage[user_id][0]
                                         ] + self.storage[user_id][2:]
            else:
                raise Exception('你傳的字數太多了，你傳了 {} 個字詞，但我最多只接受 {} 個'.format(
                    self._get_token_length(user_id), specific_max_tokens))

        return self.storage.get(user_id)

    def _get_token_length(self, user_id: str) -> int:
        #total_length = sum(len(
        #        tiktoken.encoding_for_model('gpt-3.5-turbo').encode((
        #            message['content']))) for message in self.storage[user_id])

        # titoken doesn't suppor gpt-4o
        # token is not critical spending money now(2024/05)
        total_length = 0
        model = self.db.dbread(user_id, 'gpt_mode')
        for message in self.storage[user_id]:
            if isinstance(message, str):
                total_length += len(tiktoken
                                   .encoding_for_model('gpt-4-turbo')
                                   .encode(message['content']))
            else:
                content = json.dumps(message['content'])
                total_length += len(tiktoken
                                   .encoding_for_model('gpt-4-turbo')
                                   .encode(content))
            
        return total_length

    def change_system_message(self, user_id, system_message):
        self.system_messages[user_id] = system_message
        self.remove(user_id)

    def append(self,
               user_id: str,
               role: str,
               content: str,
               type: str = 'text') -> None:
        api_support = ['assistant', 'user', 'system', 'function']
        if self.storage[user_id] == []:
            self._initialize(user_id)

        if "'" in content:
            content = content.replace("'", "\\'")

        if role not in api_support:
            role = 'user'

        if type == 'text':
            self.storage[user_id].append({'role': role, 'content': content})

        if type == 'image':
            body = {}
            body['type'] = 'image_url'
            url = {'url': f"data:image/jpeg;base64,{content}"}
            body['image_url'] = url
            print('appending image to messages')
            #print(body)
            self.storage[user_id].append({
                'role': role,
                'content': [body]
            })

        print('dropping unwanted messages...')
        self._drop_message(user_id, type)

    # let user can further shrink chat history if use more expensive model
    # _drop_message::memory_message_count defined max recorded chat history
    def get(self, user_id: str, shrink_mesg_round=15):
        expected_round = shrink_mesg_round * 2 + 1
        if len(self.storage[user_id]) > expected_round:
            mesg = [self.storage[user_id][0]]
            mesg.extend(self.storage[user_id][-shrink_mesg_round * 2:])
            return mesg
        return self.storage[user_id]

    def remove(self, user_id: str) -> None:
        self.storage[user_id] = []

    def attribute(self, user_id, name):
        if user_id not in self.settings or name not in self.settings[user_id]:
            self.settings[user_id][name] = self.default_settings[name]

        return self.settings[user_id][name]

    def configure(self, user_id, name, value):
        self.settings[user_id][name] = value

    # Function to encode the image
    def encode_image(self, image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    # called after append image
    def image_conclusion(self, user_id, conclude):
        self.storage[user_id].pop()
        self.append(user_id, 'user', '(使用者傳了一張圖片在這裡，你已經看過了並做出結論，為了節省空間圖片已不再顯示於此。)')
        self.append(user_id, 'assistant', conclude)
        
    