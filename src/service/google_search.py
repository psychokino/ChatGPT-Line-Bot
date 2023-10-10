from googleapiclient.discovery import build

def google_search(api_key, cse_id, query):
    service = build("customsearch", "v1", developerKey=api_key)
    results = service.cse().list(q=query, cx=cse_id).execute()
    return results

api_key = "您的API金鑰"
cse_id = "您的自定義搜索引擎ID"
query = "要搜索的詞語"

results = google_search(api_key, cse_id, query)