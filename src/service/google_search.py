from googleapiclient.discovery import build


class GoogleSearch:

    def __init__(self, api_key, cse_id):
        self.service = build('customsearch',
                             'v1',
                             developerKey=api_key,
                             static_discovery=False)
        self.cse_id = cse_id

    def search(self, keyword, country='TW', language='zh-TW'):
        return self.service.cse().list(q=keyword,
                                       cx=self.cse_id,
                                       cr='country' + country,
                                       hl=language).execute()

    # keys : ['kind', 'url', 'queries', 'context', 'searchInformation', 'items']
    # `items` is a list of dicts represent 10 search result:
    # keys in each item: dict_keys(['kind', 'title', 'htmlTitle', 'link', 'displayLink',
    # 'snippet', 'htmlSnippet', 'cacheId', 'formattedUrl', 'htmlFormattedUrl', 'pagemap'])
    # 這個函數會把它濃縮成一個包含 'result01' ~ 'result10' 的dict 並且每個內涵 title, link, snippet
    def json_abstract(self, result: dict):
        condense = {}
        items = result['items']
        for i in range(len(items)):
            dict_key = 'search_result_{}'.format(i)
            condense[dict_key] = {
                'title': items[i]['title'],
                'url': items[i]['link'],
                'snippet': items[i]['snippet']
            }
        return condense

    def abstract(self, result: dict):
        condense = []
        items = result['items']
        for index in range(len(items)):
            content = '''搜尋結果{}
            主旨: {}
            url: {}
            網址的內容摘要: {}
            '''.format(index, items[index]['title'], items[index]['link'],
                       items[index]['snippet'])

            condense.append(content)

        return condense
