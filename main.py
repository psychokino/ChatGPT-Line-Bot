from dotenv import load_dotenv
from flask import Flask, request, abort
from linebot import (LineBotApi, WebhookHandler)
from linebot.exceptions import (InvalidSignatureError)
from linebot.models import (MessageEvent, TextMessage, TextSendMessage,
                            ImageSendMessage, AudioMessage)
import os
import uuid

from src.models import OpenAIModel
from src.memory import Memory
from src.logger import logger
from src.storage import Storage, FileStorage, MongoStorage
from src.utils import get_role_and_content
from src.service.youtube import Youtube, YoutubeTranscriptReader
from src.service.website import Website, WebsiteReader
from src.mongodb import mongodb

load_dotenv('.env')

app = Flask(__name__)
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))
storage = None
youtube = Youtube(step=4)
website = Website()
openai_api = str(os.getenv('OPENAI_API'))

memory = Memory(system_message=os.getenv('SYSTEM_MESSAGE'),
                memory_message_count=10)



model_management = {}
api_keys = {}


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


@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):

    user_id = event.source.user_id
    source_type = type(event.source).__name__
    if source_type == 'SourceGroup':
        logger.info(f'GROUP USER')
        user_id = event.source.group_id

    text = event.message.text.strip()
    logger.info(f'{user_id}: {text}')
    
    try:
        if user_id not in model_management:
          model = OpenAIModel(api_key=openai_api)
          is_successful, _, _ = model.check_token_valid()
          if not is_successful:
            raise ValueError('Invalid API token')
        
          model_management[user_id] = model
          storage.save({user_id: '123'})
          #msg = TextSendMessage(text='註冊使用者成功, 用戶 {}'.format(user_id))

        if text.startswith('/gpt4mode'):
            memory.configure(user_id, 'gpt_mode', 'gpt-4')
            msg = TextSendMessage(text="切換成功，我現在是 GPT-4")
            line_bot_api.reply_message(event.reply_token, msg)
            return True

        if text.startswith('/gpt3.5'):
            memory.configure(user_id, 'gpt_mode', 'gpt-3.5-turbo')
            msg = TextSendMessage(text="切換成功，我現在是 GPT-3.5")
            line_bot_api.reply_message(event.reply_token, msg)
            return True

        if text.startswith('/gpt?'):
            msg = TextSendMessage(text="你現在用的模式是{}".format(
                memory.attribute(user_id, 'gpt_mode')))
            line_bot_api.reply_message(event.reply_token, msg)
            return True
        
        if text.startswith('/切換懶人模式'):
            memory.configure(user_id, 'is_lazy', True)
            msg = TextSendMessage(text="切換成功，我現在是懶人模式")
            line_bot_api.reply_message(event.reply_token, msg)
            return True
        
        if text.startswith('/切換多話模式'):
            memory.configure(user_id, 'is_lazy', False)
            msg = TextSendMessage(text="切換成功，你現在說什麼我都會回答你")
            line_bot_api.reply_message(event.reply_token, msg)
            return True
        
        if text.startswith('/help'):
            msg = TextSendMessage(text="""
指令：
/切換懶人模式
👉 切換成只有在最前面打上`@諺喝諺喝`我才會回你訊息的模式

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

""")
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
            memory.append(user_id, 'user', prompt)
            is_successful, response, error_message = model_management[
                user_id].image_generations(prompt)
            
            if not is_successful:
                raise Exception(error_message)
        
            url = response['data'][0]['url']
            msg = ImageSendMessage(original_content_url=url, preview_image_url=url)
            memory.append(user_id, 'assistant', url)
            line_bot_api.reply_message(event.reply_token, msg)
            return True

        # laze mode will ignore any dialog, just listening
        if memory.attribute(user_id, 'is_lazy') and not text.startswith('@諺喝諺喝'):
            memory.append(user_id, 'user', text)
            return True
        
        if memory.attribute(user_id, 'is_lazy'):
            text = text[5:].strip()

        # 主要邏輯
        user_model = model_management[user_id]
        memory.append(user_id, 'user', text)
        url = website.get_url_from_text(text)
        if url:
            if youtube.retrieve_video_id(text):
                is_successful, chunks, error_message = youtube.get_transcript_chunks(
                    youtube.retrieve_video_id(text))
                
                if not is_successful:
                    raise Exception(error_message)
                    
                transcript = YoutubeTranscriptReader(user_model, os.getenv('OPENAI_MODEL_ENGINE'))
                is_successful, response, error_message = transcript.summarize(chunks)
                if not is_successful:
                    raise Exception(error_message)
                    
                role, response = get_role_and_content(response)
                msg = TextSendMessage(text=response)
            
            else:
                chunks = website.get_content_from_url(url)
                if len(chunks) == 0:
                    raise Exception('無法撈取此網站文字')
                website_reader = WebsiteReader(user_model,
                                             os.getenv('OPENAI_MODEL_ENGINE'))
                is_successful, response, error_message = website_reader.summarize(
                    chunks)
                if not is_successful:
                    raise Exception(error_message)
                role, response = get_role_and_content(response)
                msg = TextSendMessage(text=response)
            
        else:
            is_successful, response, error_message = user_model.chat_completions(
                memory.get(user_id), memory.attribute(user_id, 'gpt_mode'))
            if not is_successful:
                raise Exception(error_message)
                
            role, response = get_role_and_content(response)
            msg = TextSendMessage(text=response)
            memory.append(user_id, role, response)
            
    except ValueError:
        msg = TextSendMessage(text='python script value error, please debug')
        
    except KeyError:
        msg = TextSendMessage(text='python script key error, please debug')
        
    except Exception as e:
        memory.remove(user_id)
        if str(e).startswith('Incorrect API key provided'):
            msg = TextSendMessage(text='OpenAI API Token 有誤，請重新註冊。')
        elif str(e).startswith(
                'That model is currently overloaded with other requests.'):
            msg = TextSendMessage(text='已超過負荷，請稍後再試')
        else:
            msg = TextSendMessage(text=str(e))
    
    line_bot_api.reply_message(event.reply_token, msg)


@handler.add(MessageEvent, message=AudioMessage)
def handle_audio_message(event):
    user_id = event.source.user_id
    audio_content = line_bot_api.get_message_content(event.message.id)
    input_audio_path = f'{str(uuid.uuid4())}.m4a'
    with open(input_audio_path, 'wb') as fd:
        for chunk in audio_content.iter_content():
            fd.write(chunk)

    try:
        if not model_management.get(user_id):
          raise ValueError('Invalid API token')
    
        elif memory.attribute(user_id, 'is_lazy'):
          is_successful, response, error_message = model_management[
              user_id].audio_transcriptions(input_audio_path, 'whisper-1')
          if not is_successful:
            raise Exception(error_message)
          msg = TextSendMessage(text=response['text'])
    
        else:
          is_successful, response, error_message = model_management[
              user_id].audio_transcriptions(input_audio_path, 'whisper-1')
          if not is_successful:
            raise Exception(error_message)
          memory.append(user_id, 'user', response['text'])
          is_successful, response, error_message = model_management[
              user_id].chat_completions(memory.get(user_id), memory.attribute(user_id, 'gpt_mode'))
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
  if os.getenv('USE_MONGO'):
    mongodb.connect_to_database()
    storage = Storage(MongoStorage(mongodb.db))
  else:
    storage = Storage(FileStorage('db.json'))
  try:
    data = storage.load()
    for user_id in data.keys():
      model_management[user_id] = OpenAIModel(api_key=openai_api)
  except FileNotFoundError:
    pass
  app.run(host='0.0.0.0', port=8080)
