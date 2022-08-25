from slack_sdk import WebClient
from pymongo import MongoClient
from time import time
from operator import itemgetter
import jwt
import requests
import json
import arrow
import os


def generate_token():
    zoom_api_key = os.environ.get("ZOOM_API_KEY")
    zoom_api_secret = os.environ.get("ZOOM_API_SECRET")
    token = jwt.encode({"iss": zoom_api_key, 'exp': time() + 5000},
    zoom_api_secret, algorithm='HS256')

    return token


def get_recording(meeting_id):
    headers = {"authorization": f"Bearer {generate_token()}", 
               "content-type": "application/json"}
    recording = requests.get(f'https://api.zoom.us/v2/meetings/{meeting_id}/recordings', 
                              headers=headers)
    dados = json.loads(recording.text)
    obj = {}
    obj['disciplina'] = dados['topic']
    obj['data'] = arrow.get(dados['start_time']).datetime
    obj['data_str'] = arrow.get(dados['start_time']).format("DD/MM/YY")
    files = sorted(dados['recording_files'], key=itemgetter('file_size'), reverse=True)
    obj['video_url'] = files[0]['play_url']
    obj['audio_url'] = [x for x in files if x['recording_type'] == 'audio_only'][0]['play_url']
    obj['psw'] = dados['password']
    obj['meeting_id'] = meeting_id
    obj['recording_id'] = files[0]['id']
    return obj


def msg_nova_gravacao(json, client):
    t = f":red_circle: A gravação da última aula da disciplina *{json['disciplina']}* já está disponível!\n"
    t += f"Clique <{json['video_url']}|aqui> para acessar o vídeo.\n"
    t += f"senha: {json['psw']}\n"
    block = [{"type": "section", "text": {"type": "mrkdwn", "text": t}}]
    client.chat_postMessage(channel="general", text="", blocks=block)
    print("Message sent")


def check_recordings():
    user = os.environ.get('MONGODB_USER')
    psw = os.environ.get('MONGODB_PSW')
    mongo_uri = os.environ.get('MONGODB_URI')
    uri = f'mongodb://{user}:{psw}@{mongo_uri}/mjd?ssl=true'
    db = MongoClient(uri, ssl=True, tlsAllowInvalidCertificates=True).mjd
    client = WebClient(token=slack_bot_token)
    for disciplina in db.disciplinas.find():
        last = get_recording(disciplina['zoom_id'])
        if db.gravacoes.find_one({"recording_id": last['recording_id']}):
            print("Gravação já consta no banco de dados")
            continue
        else:
            print("Acrescentando gravação")
            msg_nova_gravacao(last, client)
            db.gravacoes.insert_one(last)


if __name__ == '__main__':
    check_recordings()