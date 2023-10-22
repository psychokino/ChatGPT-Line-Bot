from typing import List, Dict
import requests
from src.service.calculator import Calculator


class ModelInterface:

    def check_token_valid(self) -> bool:
        pass

    def chat_completions(self, messages: List[Dict], model_engine: str) -> str:
        pass

    def audio_transcriptions(self, file, model_engine: str) -> str:
        pass

    def image_generations(self, prompt: str) -> str:
        pass


class OpenAIModel(ModelInterface):
    functions = [{
        "name": "perform_google_search",
        "description":
        "performs a google search, call this if you want to search anythings",
        "parameters": {
            "type": "object",
            "properties": {
                "key1": {
                    "type":
                    "string",
                    "description":
                    "the most important keyword performing this search"
                },
                "key2": {
                    "type": "string",
                    "description": "second important keyword for searching"
                },
                "key3": {
                    "type": "string",
                    "description": "third important keyword for searching"
                },
                "key4": {
                    "type": "string",
                    "description": "less important keyword for searching"
                },
            },
            "required": ["key1"]
        }
    }, {
        "name": "view_website",
        "description":
        "view content for a given url, call this if you found url link from google_search or user",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "website url for viewing content"
                },
                "keyword": {
                    "type":
                    "string",
                    "description":
                    "interested keyword you want to pay more addition to the website"
                }
            },
            "required": ["key1"]
        }
    }, {
        "name": "get_time",
        "description": "抓取系統目前的時間和日期，請務必使用這個功能獲取時間，不要擅自回答或決定現在的時間",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }, {
        "name": Calculator.name(),
        "description": Calculator.description(),
        "parameters": Calculator.parameters()
    }]

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = 'https://api.openai.com/v1'

    def _request(self, method, endpoint, body=None, files=None):
        self.headers = {'Authorization': f'Bearer {self.api_key}'}
        try:
            if method == 'GET':
                r = requests.get(f'{self.base_url}{endpoint}',
                                 headers=self.headers)
            elif method == 'POST':
                if body:
                    self.headers['Content-Type'] = 'application/json'
                r = requests.post(f'{self.base_url}{endpoint}',
                                  headers=self.headers,
                                  json=body,
                                  files=files)
            r = r.json()
            if r.get('error'):
                return False, None, r.get('error', {}).get('message')
        except Exception:
            return False, None, 'OpenAI API 系統不穩定，請稍後再試'

        return True, r, None

    def check_token_valid(self):
        return self._request('GET', '/models')

    def chat_completions(self,
                         messages,
                         model_engine,
                         use_function=False) -> str:
        json_body = {'model': model_engine, 'messages': messages}
        if use_function:
            json_body['functions'] = self.functions

        return self._request('POST', '/chat/completions', body=json_body)

    def audio_transcriptions(self, file_path, model_engine) -> str:
        files = {
            'file': open(file_path, 'rb'),
            'model': (None, model_engine),
        }
        return self._request('POST', '/audio/transcriptions', files=files)

    def image_generations(self, prompt: str) -> str:
        json_body = {"prompt": prompt, "n": 1, "size": "1024x1024"}
        return self._request('POST', '/images/generations', body=json_body)
