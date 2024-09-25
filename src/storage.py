import json
import datetime
import os
import psycopg2

from collections import defaultdict

from enum import Enum
from replit import db

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

    columns = [
        'id', 'user_id', 'alias', 'priviledge', 'gpt_mode', 'is_lazy',
        'group_user', 'chat_history', 'function_call', 'is_group', 'max_token', 
        'note'
    ]

    #class Column(Enum):
    #    priviledge = 1
    #    gpt_mode = 2
    #    is_lazy = 3
    #    is_group = 4

    #    user_in_group = 1000

    def __init__(self, file_name):
        self.fine_name = file_name
        self.history = defaultdict(dict)
        self.reload()

    def dbsave(self, user_id, item, value):
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        conn.autocommit = True
        postgre = conn.cursor()
        if item == 'group_user' or item == 'alias':
            old = self.dbread(user_id, item)
            if not old:
                value = json.dumps([value], ensure_ascii=False)
            else:
                #j = json.loads(old)
                j = old
                if value in j:
                    postgre.close()
                    conn.close()
                    return None

                if isinstance(j, str):
                    j = [j, value]
                else:
                    j.append(value)
                    
                j.append(value)
                value = json.dumps(j, ensure_ascii=False)
        print(f'saving and caching {user_id}/{item}: {value}')
        sql = f"UPDATE userlist SET {item} = '{value}' WHERE user_id = '{user_id}';"
        print(sql)
        
        postgre.execute(sql)
        self.history[user_id][item] = value
        postgre.close()
        conn.close()

    def dbusercheck(self, user_id):
        if user_id not in self.history.keys():
            print(f'dbusercheckcache miss for {user_id}, creating')
            conn = psycopg2.connect(os.getenv('DATABASE_URL'))
            conn.autocommit = True
            postgre = conn.cursor()
            sql = f"INSERT INTO userlist (user_id) VALUES ('{user_id}');"
            print(sql)
            self.history[user_id] = {}
            postgre.execute(sql)
            postgre.close()
            conn.close()
        

    def dbread(self, user_id, item):
        if user_id not in self.history.keys():
            self.dbusercheck(user_id)

        if item in self.history[user_id].keys():
            print(f'dbread cache hit for {user_id}/{item} ')
            return self.history[user_id][item]

        print(f'dbread cache miss for {user_id}/{item}, creating...')
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        conn.autocommit = True
        postgre = conn.cursor()
        sql = f"SELECT {item} FROM userlist WHERE user_id ='{user_id}';"
        print(sql)
        postgre.execute(sql)
        ret = postgre.fetchall()
        postgre.close()
        conn.close()
        if not ret or not ret[0]:
            return None

        for j in range(len(ret[0])):
            self.history[user_id][self.columns[j]] = ret[0][j]

        return ret[0][0]


    def ids(self):
        return self.history.keys()

    def commons(self, user_id):
        mode = self.dbread(user_id, 'gpt_mode')
        lazy = self.dbread(user_id, 'is_lazy')
        chats = self.dbread(user_id, 'chat_history')

        return mode, lazy, chats

    def reload(self):
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        conn.autocommit = True
        postgre = conn.cursor()
        postgre.execute(f"SELECT * FROM userlist;")
        result = postgre.fetchall()

        if result and result[0]:
            data = {}
            for i in range(len(result)):
                user_id = result[i][1]
                self.history[user_id] = {}
                print(f'caching {user_id}:')
                for j in range(len(result[i])):
                    #print(f'assign {self.columns[j]} to {result[i][j]}')
                    self.history[user_id][self.columns[j]] = result[i][j]

                db[user_id] = data
                print(f'{self.history[user_id]}')

        postgre.close()
        conn.close()