from typing import Dict
from collections import defaultdict
import tiktoken


class MemoryInterface:

  def append(self, user_id: str, message: Dict) -> None:
    pass

  def get(self, user_id: str) -> str:
    return ""

  def remove(self, user_id: str) -> None:
    pass


class Memory(MemoryInterface):

    def __init__(self,
               system_message,
               memory_message_count,
               max_tokens=4070):
        self.storage = defaultdict(list)
        self.settings = defaultdict(dict)
        self.system_messages = defaultdict(str)
        self.default_system_message = system_message
        self.memory_message_count = memory_message_count
        self.max_tokens = max_tokens
        self.default_settings = {
            'is_lazy': True,
            'gpt_mode': 'gpt-3.5-turbo'
        }
    
    def _initialize(self, user_id: str):
        self.storage[user_id] = [{
            'role':
            'system',
            'content':
            self.system_messages.get(user_id) or self.default_system_message
        }]
    
    def _drop_message(self, user_id: str):
        if len(
            self.storage.get(user_id)) >= (self.memory_message_count + 1) * 2 + 1:
          self.storage[user_id] = [
              self.storage[user_id][0]
          ] + self.storage[user_id][-(self.memory_message_count * 2):]
        
        while self._get_token_length(user_id) > self.max_tokens:
          if len(self.storage[user_id]) > 2:
            self.storage[user_id] = [self.storage[user_id][0]
                                     ] + self.storage[user_id][2:]
          else:
            raise Exception('你傳的字數太多了，你傳了 {} 個字詞，但我最多只接受 {} 個'.format(
                self._get_token_length(user_id), self.max_tokens))
        
        return self.storage.get(user_id)
    
    def _get_token_length(self, user_id: str) -> int:
        #total_length = sum(
        #    len(message['content']) for message in self.storage[user_id])
        total_length = sum(
            len(tiktoken.encoding_for_model(attribute(user_id, 'gpt_mode'))
                .encode((message['content'])))
                for message in self.storage[user_id])
        return total_length
    
    def change_system_message(self, user_id, system_message):
        self.system_messages[user_id] = system_message
        self.remove(user_id)
    
    def append(self, user_id: str, role: str, content: str) -> None:
        if self.storage[user_id] == []:
          self._initialize(user_id)
        self.storage[user_id].append({'role': role, 'content': content})
        self._drop_message(user_id)
    
    def get(self, user_id: str) -> str:
        return self.storage[user_id]
        
    def remove(self, user_id: str) -> None:
        self.storage[user_id] = []
    
    def attribute(self, user_id, name):
        if user_id not in self.settings or name not in self.settings[user_id]:
            self.settings[user_id][name] = self.default_settings[name]

        return self.settings[user_id][name]

    def configure(self, user_id, name, value):
        self.settings[user_id][name] = value

