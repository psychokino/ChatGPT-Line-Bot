from dotenv import load_dotenv
from flask import Flask, request, abort
from linebot import (LineBotApi, WebhookHandler)
from linebot.exceptions import (InvalidSignatureError)
from linebot.models import (MessageEvent, TextMessage, TextSendMessage,
                            ImageSendMessage, AudioMessage)
import os
import uuid
import json

from src.models import OpenAIModel
from src.memory import Memory
from src.logger import logger
from src.storage import Storage as db
from src.utils import get_role_and_content, Decoder
from src.service.youtube import Youtube, YoutubeTranscriptReader
from src.service.website import Website, WebsiteReader
from src.mongodb import mongodb
from src.service.google_search import GoogleSearch
from src.service.calculator import Calculator
from collections import defaultdict

import openai
import datetime

load_dotenv('.env')

app = Flask(__name__)
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))
storage = None
youtube = Youtube(step=4)
website = Website()
openai_api = str(os.getenv('OPENAI_API'))
google_key = str(os.getenv('GOOGLE_API'))
google_cse_id = str(os.getenv('GOOGLE_CSE_ID'))
google = GoogleSearch(google_key, google_cse_id)

memory = Memory(system_message=os.getenv('SYSTEM_MESSAGE'))

model_management = {}
api_keys = {}
allow_mode_switch = [
    'U3cbfef46cb6b39364be80fc2ec1fa9a2', 'Ca735a624e5bc89ad45e5dbd0000deaa2'
]

administrator = 'U3cbfef46cb6b39364be80fc2ec1fa9a2'
maintaining = False


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print(
            "Invalid signature. Please check your channel access token/channel secret."
        )
        abort(400)
    return 'OK'


@app.route("/ping", methods=['GET'])
def ping():
    return 'OK'


def get_dialog_info(event):
    bot_info = line_bot_api.get_bot_info()
    account_name = '@{}'.format(bot_info.display_name)
    is_group = False
    role_name = ''
    group_name = ''

    user_id = event.source.user_id
    source_type = type(event.source).__name__
    if source_type == 'SourceGroup':
        is_group = True
        try:
            role_name = line_bot_api.get_profile(user_id).display_name
        except:
            role_name = 'a group user'

        user_id = event.source.group_id
        group_name = line_bot_api.get_group_summary(user_id).group_name
        logger.info(f'Group: {group_name}')

    else:
        profile = line_bot_api.get_profile(user_id)
        role_name = profile.display_name
        logger.info(f'User: {role_name}')

    return is_group, user_id, account_name, role_name, group_name


@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):

    is_group, user_id, called_keyword, role_name, group_name = get_dialog_info(
        event)

    text = event.message.text.strip()
    logger.info(f'{user_id}: {text}')

    #try:
    if user_id not in model_management:
        model = OpenAIModel(api_key=openai_api)
        is_successful, _, _ = model.check_token_valid()
        if not is_successful:
            raise ValueError('Invalid API token')

        model_management[user_id] = model
        storage.save(user_id, 'is_group', is_group)

        #msg = TextSendMessage(text='註冊使用者成功, 用戶 {}'.format(user_id))

    if storage.read(user_id, 'priviledge') != 1:
        msg = TextSendMessage(text='非認證的使用者，請聯絡作者'.format(user_id))
        line_bot_api.reply_message(event.reply_token, msg)
        return True

    gpt_mode = storage.read(user_id, 'gpt_mode')
    is_lazy = storage.read(user_id, 'is_lazy')
    chat_history = storage.read(user_id, 'chat_history')
    can_use_function = storage.read(user_id, 'function_call')

    storage.add(user_id, 'group_users', role_name)
    if is_group:
        storage.add(user_id, 'alias', group_name)

    if text.startswith('/gpt4mode'):
        if user_id not in allow_mode_switch:
            msg = TextSendMessage(text="只有特定群組或特定人員才可以切換模式喔")
            line_bot_api.reply_message(event.reply_token, msg)
            return True

        storage.save(user_id, 'gpt_mode', 'gpt-4-1106-preview')
        storage.save(user_id, 'chat_history', 3)
        msg = TextSendMessage(text="切換成功，我現在是 GPT-4")
        line_bot_api.reply_message(event.reply_token, msg)
        return True

    if text.startswith('/gpt3.5'):
        storage.save(user_id, 'gpt_mode', 'gpt-3.5-turbo-1106')
        storage.save(user_id, 'chat_history', 20)
        msg = TextSendMessage(text="切換成功，我現在是 GPT-3.5")
        line_bot_api.reply_message(event.reply_token, msg)
        return True

    if text.startswith('/gpt?'):
        msg = TextSendMessage(text="你現在用的模式是{}".format(gpt_mode))
        line_bot_api.reply_message(event.reply_token, msg)
        return True

    if text.startswith('/切換懶人模式'):
        storage.save(user_id, 'is_lazy', True)
        msg = TextSendMessage(text="切換成功，我現在是懶人模式")
        line_bot_api.reply_message(event.reply_token, msg)
        return True

    if text.startswith('/切換多話模式'):
        storage.save(user_id, 'is_lazy', False)
        msg = TextSendMessage(text="切換成功，你現在說什麼我都會回答你")
        line_bot_api.reply_message(event.reply_token, msg)
        return True

    if text.startswith('/function_call'):
        switch = text[15:].strip()
        storage.save(user_id, 'function_call', switch == 'on')
        msg = TextSendMessage(text="網路搜尋功能 {}".format(switch == 'on'))
        line_bot_api.reply_message(event.reply_token, msg)
        return True

    if text.startswith('/help'):
        msg = TextSendMessage(text="""
指令：
/切換懶人模式
👉 切換成只有在最前面打上`{}`我才會回你訊息的模式

/切換多話模式
👉 切換成有話必回的模式

/AI角色 + 文字
👉 可以讓AI扮演某個角色，例如：請你扮演擅長做總結的人

/清除
👉 這個指令能夠清除歷史訊息

/圖像 + Prompt
👉 會用 AI 把文字想像成圖片

語音輸入
👉 懶人模式會直接把語音轉換成文字
👉 多話模式會把你說的話用 ChatGPT 回覆

直接輸入文字
👉 多話模式會直接用 ChatGPT 回覆

""".format(called_keyword))
        line_bot_api.reply_message(event.reply_token, msg)
        return True

    if text.startswith('/AI角色'):
        memory.change_system_message(user_id, text[5:].strip())
        msg = TextSendMessage(text='輸入成功')
        line_bot_api.reply_message(event.reply_token, msg)
        return True

    if text.startswith('/清除'):
        memory.remove(user_id)
        msg = TextSendMessage(text='歷史訊息清除成功')
        line_bot_api.reply_message(event.reply_token, msg)
        return True

    if text.startswith('/圖像'):
        prompt = text[3:].strip()
        prompt = """
把非英文轉成英文:
""" + prompt
        memory.append(user_id, role_name, prompt)

        user_model = model_management[user_id]
        is_successful, response, error_message = user_model.chat_completions(
            memory.get(user_id, chat_history), 'gpt-4')
        if not is_successful:
            raise Exception(error_message)

        role, response = get_role_and_content(response)
        msg = TextSendMessage(text='產生圖片中...提詞: {}'.format(response))
        line_bot_api.push_message(user_id, msg)

        is_successful, response, error_message = model_management[
            user_id].image_generations(response)

        if not is_successful:
            raise Exception(error_message)

        url = response.data[0].url
        msg = ImageSendMessage(original_content_url=url,
                               preview_image_url=url)
        memory.append(user_id, 'assistant', url)
        line_bot_api.reply_message(event.reply_token, msg)
        return True

    # laze mode will ignore any dialog, just listening
    if is_lazy and not text.startswith(called_keyword):
        memory.append(user_id, role_name, text)
        return True

    if maintaining and user_id != administrator:
        msg = TextSendMessage(text='維修改版中，敬請期待!')
        line_bot_api.reply_message(event.reply_token, msg)
        return True

    if is_lazy:
        text = text[len(called_keyword):].strip()

    # 主要邏輯
    user_model = model_management[user_id]
    memory.append(user_id, role_name, text)
    url = website.get_url_from_text(text)
    if url:
        if youtube.retrieve_video_id(text):
            is_successful, chunks, error_message = youtube.get_transcript_chunks(
                youtube.retrieve_video_id(text))

            if not is_successful:
                raise Exception(error_message)

            transcript = YoutubeTranscriptReader(user_model, gpt_mode)
            is_successful, response, error_message = transcript.summarize(
                chunks)
            if not is_successful:
                raise Exception(error_message)

            role, response = get_role_and_content(response)
            msg = TextSendMessage(text=response)

        else:
            chunks = website.get_content_from_url(url)
            if len(chunks) == 0:
                raise Exception('無法撈取此網站文字')
            website_reader = WebsiteReader(user_model, gpt_mode)
            is_successful, response, error_message = website_reader.summarize(
                chunks)
            if not is_successful:
                raise Exception(error_message)
            role, response = get_role_and_content(response)
            msg = TextSendMessage(text=response)

    else:
        iteration = 1
        while iteration < 10:
            if iteration == 9:
                can_use_function = False

            if iteration > 3:
                gpt_mode = 'gpt-3.5-turbo'
                chat_history = 999

            is_successful, response, error_message = user_model.chat_completions(
                memory.get(user_id, chat_history), gpt_mode,
                can_use_function)
            if not is_successful:
                raise Exception(error_message)

            body = Decoder(response)
            if not body.is_function_call():
                memory.append(user_id, body.role(), body.content())
                msg = TextSendMessage(text=body.content())
                break

            iteration = iteration + 1

            name = body.function_name()
            logger.info(f'calling function: {name}')
            if name == 'perform_google_search':
                key1 = body.function_call_arg('key1')
                key2 = body.function_call_arg('key2')
                key3 = body.function_call_arg('key3')
                key4 = body.function_call_arg('key4')

                query = '{} {} {} {}'.format(key1, key2 or '', key3 or '',
                                             key4 or '')

                msg = TextSendMessage(text='正在幫你google關鍵字 {}'.format(query))
                line_bot_api.push_message(user_id, msg)

                memory.append(
                    user_id, 'system',
                    '你呼叫了 perform_google_search 並且關鍵字是 {}'.format(query))

                result = google.abstract(google.search(query.strip()))

                conclude = '以下是搜尋結果，請自行決定是否持續呼叫 view_website function'
                '來瀏覽「url」的任何內容，或是直接參考「網址的內容摘要」，不要做重複的搜尋:\n' + '\n\n'.join(result)

                memory.append(user_id, 'system', conclude)
                continue

            if name == 'view_website':

                url = body.function_call_arg('url')
                keyword = body.function_call_arg('keyword')

                if keyword:
                    #msg = TextSendMessage(text='正在嘗試尋找網頁 {} 有沒有 {} 的資訊'.format(url, keyword))
                    #line_bot_api.push_message(user_id, msg)
                    memory.append(
                        user_id, 'system',
                        '你呼叫了 view_website 並且網址是 {} 關鍵字是 {}'.format(
                            url, keyword))
                else:
                    #msg = TextSendMessage(text='正在嘗試瀏覽網頁 {}'.format(url))
                    #line_bot_api.push_message(user_id, msg)
                    memory.append(user_id, 'system',
                                  '你呼叫了 view_website 並且網址是 {}'.format(url))

                chunks = website.get_content_from_url(url)
                if len(chunks) == 0:
                    memory.append(user_id, 'system',
                                  '無法取得 {} 網站的文字，請嘗試從前面的搜尋記錄中的其他網址繼續view_website，或考慮直接使用前面搜尋紀錄的「網址的內容摘要」當成結論'.format(url))
                    continue

                website_reader = WebsiteReader(user_model, 'gpt-3.5-turbo')
                is_successful, response, error_message = website_reader.summarize(
                    chunks, keyword)
                if not is_successful:
                    raise Exception(error_message)

                role, response = get_role_and_content(response)
                memory.append(user_id, 'system',
                              'view_website的結果:\n。請決定是否要繼續從前面搜尋記錄中的其他網址做view_website，或是從前面搜尋記錄的「網址的內容摘要」當成這次的結論，又或者可以再次嘗試perform_google_search並使用和前面不同的關鍵字' + response)

            if name == 'get_time':
                memory.append(user_id, 'system', '你呼叫了 get_time')
                now = datetime.datetime.now() + datetime.timedelta(
                    hours=8)  # UTC+8
                chinese_time = now.strftime("現在時間 %Y年%m月%d日 %H點%M分%S秒")
                memory.append(user_id, 'system', chinese_time)

            if name == Calculator.name():
                msg = TextSendMessage(text='正在使用計算機...')
                line_bot_api.push_message(user_id, msg)
                
                operator = body.function_call_arg('operator')
                operands = body.function_call_arg('value')
                str_val_list = str(operands).replace('[', '').replace(
                    ']', '')
                prompt = '你呼叫了 {} 的 {}，去運算 {}'.format(
                    Calculator.name(), operator, str_val_list)

                memory.append(user_id, 'system', prompt)
                result = Calculator.decode(operator, operands)
                memory.append(user_id, 'system', '運算結果是{}'.format(result))

    #except ValueError:
    #    msg = TextSendMessage(text='python script value error, please debug')

    #except KeyError:
    #    msg = TextSendMessage(text='python script key error, please debug')

    #except openai.APIConnectionError as e:
    #    print("The server could not be reached")
    #    print(e.__cause__)  # an underlying Exception, likely raised within httpx.
    #    msg = TextSendMessage(text="連線失敗，請再試一次")

    #except openai.RateLimitError as e:
    #    print("A 429 status code was received; we should back off a bit.")
    #    msg = TextSendMessage(text="訊息太密集了，請等一下再試試")

    #except openai.APIStatusError as e:
    #    print("Another non-200-range status code was received")
    #    print(e.status_code)
    #    print(e.response)
    #    msg = TextSendMessage(text="系統錯誤，請再試一次")

#    except Exception as e:
#        memory.remove(user_id)
#        msg = TextSendMessage(text="程式錯誤，請再試一次")

    line_bot_api.reply_message(event.reply_token, msg)


@handler.add(MessageEvent, message=AudioMessage)
def handle_audio_message(event):

    is_group, user_id, called_keyword, role_name, group_name = get_dialog_info(
        event)
    gpt_mode = storage.read(user_id, 'gpt_mode')
    is_lazy = storage.read(user_id, 'is_lazy')
    chat_history = storage.read(user_id, 'chat_history')

    storage.add(user_id, 'group_users', role_name)
    if is_group:
        storage.add(user_id, 'alias', group_name)

    audio_content = line_bot_api.get_message_content(event.message.id)
    input_audio_path = f'{str(uuid.uuid4())}.m4a'
    with open(input_audio_path, 'wb') as fd:
        for chunk in audio_content.iter_content():
            fd.write(chunk)

    try:
        if not model_management.get(user_id):
            raise ValueError('Invalid API token')

        elif is_lazy:
            is_successful, response, error_message = model_management[
                user_id].audio_transcriptions(input_audio_path, 'whisper-1')
            if not is_successful:
                raise Exception(error_message)
            msg = TextSendMessage(text=response.text)

        else:
            is_successful, response, error_message = model_management[
                user_id].audio_transcriptions(input_audio_path, 'whisper-1')
            if not is_successful:
                raise Exception(error_message)
            memory.append(user_id, role_name, response.text)
            is_successful, response, error_message = model_management[
                user_id].chat_completions(memory.get(user_id, chat_history),
                                          gpt_mode)
            if not is_successful:
                raise Exception(error_message)
            role, response = get_role_and_content(response)
            memory.append(user_id, role, response)
            msg = TextSendMessage(text=response)

    except ValueError:
        msg = TextSendMessage(text='請先註冊你的 API Token，格式為 /註冊 [API TOKEN]')
    except KeyError:
        msg = TextSendMessage(text='請先註冊 Token，格式為 /註冊 sk-xxxxx')
    except Exception as e:
        memory.remove(user_id)
        if str(e).startswith('Incorrect API key provided'):
            msg = TextSendMessage(text='OpenAI API Token 有誤，請重新註冊。')
        else:
            msg = TextSendMessage(text=str(e))

    os.remove(input_audio_path)
    line_bot_api.reply_message(event.reply_token, msg)


@app.route("/", methods=['GET'])
def home():
    return 'Hello World'


if __name__ == "__main__":

    storage = db('db.json')
    storage.load()
    try:
        data = storage.read()
        for user_id in data:
            model_management[user_id] = OpenAIModel(api_key=openai_api)
    except FileNotFoundError:
        pass
    app.run(host='0.0.0.0', port=8080)
