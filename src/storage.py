import json
import datetime
import os

from collections import defaultdict

from enum import Enum


class Storage:

    default_settings = {
        'priviledge': 1,
        'gpt_mode': 'gpt-3.5-turbo',
        'is_lazy': True,
        'is_group': False,
        'group_users': [],
        'alias': '',
        'role_play': '',
        'chat_history': 15,
        'function_call': 0
    }

    #class Column(Enum):
    #    priviledge = 1
    #    gpt_mode = 2
    #    is_lazy = 3
    #    is_group = 4

    #    user_in_group = 1000

    def __init__(self, file_name):
        self.fine_name = file_name
        self.history = defaultdict(dict)

    def save(self, user_id, item, value):
        if user_id not in self.history:
            self.history[user_id] = {}

        self.history[user_id][item] = value
        with open(self.fine_name, 'w', newline='') as f:
            json.dump(self.history, f, ensure_ascii=False, indent=4)

    def load(self, user_id=None):
        if not os.path.exists(self.fine_name):
            f = open(self.fine_name, 'w', newline='')
            f.close()

        with open(self.fine_name, newline='') as jsonfile:
            data = json.load(jsonfile)

        #for key, val in data.items():
        #    if type(val) != dict:
        #        data[key] = {'priviledge': '1'}

        self.history = data

    def read(self, user_id=None, item=None):
        if not user_id:
            return self.history.keys()
        if not item:
            return self.history[user_id].keys()

        if not self.history[user_id]:
            self.history[user_id] = {}

        if item not in self.history[user_id]:
            self.save(user_id, item, Storage.default_settings[item])

        return self.history[user_id][item]

    # used when item is a list instead of single value
    def add(self, user_id, item, data):
        if user_id not in self.history:
            self.history[user_id] = {item: []}

        if item not in self.history[user_id]:
            self.history[user_id][item] = []

        if data in self.history[user_id][item]:
            return True

        self.history[user_id][item].append(data)
        with open(self.fine_name, 'w', newline='') as f:
            json.dump(self.history, f, ensure_ascii=False, indent=4)

        return True
