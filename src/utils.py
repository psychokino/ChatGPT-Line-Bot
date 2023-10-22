import opencc
import json

s2t_converter = opencc.OpenCC('s2t')
t2s_converter = opencc.OpenCC('t2s')


class ChatCompletion:

    def __init__(self, request_body):
        self.body = request_body

    def role(self):
        return self.body['choices'][0]['message']['role']

    def content(self):
        content = self.body['choices'][0]['message']['content'].strip()
        content = s2t_converter.convert(content)
        return content

    def is_function_call(self):
        return 'function_call' in self.body['choices'][0]['message'].keys()

    def function_name(self):
        return self.body['choices'][0]['message']['function_call']['name']

    def function_call_arg(self, key):
        try:
            args = json.loads(self.body['choices'][0]['message']
                              ['function_call']['arguments'])
            if key not in args.keys():
                return None

            return args[key]

        except:
            return None

    def message(self):
        return self.body['choices'][0]['message']


def get_role_and_content(response: str):
    role = response['choices'][0]['message']['role']
    try:
        content = response['choices'][0]['message']['content'].strip()
        content = s2t_converter.convert(content)
    except:
        content = ''
    return role, content
