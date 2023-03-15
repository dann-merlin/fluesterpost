#!/usr/bin/env python3

import http.server
import json
import argparse
import base64
import subprocess
from http import HTTPStatus
from pathlib import Path
import hashlib
from threading import Thread, Lock
import logging
import secrets
import string

logger = logging.getLogger(__name__)

API_KEY_LENGTH = 32

alphabet = string.ascii_letters + string.digits

supported_languages = ["en","zh","de","es","ru","ko","fr","ja","pt","tr","pl",
        "ca","nl","ar","sv","it","id","hi","fi","vi","iw","uk","el","ms","cs",
        "ro","da","hu","ta","no","th","ur","hr","bg","lt","la","mi","ml","cy",
        "sk","te","fa","lv","bn","sr","az","sl","kn","et","mk","br","eu","is",
        "hy","ne","mn","bs","kk","sq","sw","gl","mr","pa","si","km","sn","yo",
        "so","af","oc","ka","be","tg","sd","gu","am","yi","lo","uz","fo","ht",
        "ps","tk","nn","mt","sa","lb","my","bo","tl","mg","as","tt","haw","ln",
        "ha","ba","jw","su"]

models_by_lang = {
    'en': './models/ggml-tiny.en.bin',
    'auto': './models/ggml-tiny.bin',
}

def select_correct_model(lang):
    global models_by_lang

    try:
        return models_by_lang[lang]
    except KeyError:
        return models_by_lang['auto']

def transcribe(file_path, lang):
    global WHISPERCPP_DIR

    model = select_correct_model(lang)
    cmd = ['./main', '--no-timestamps', '--model', model, '--file', file_path.resolve(), '--language', lang]
    try:
        output = subprocess.check_output(cmd, cwd=WHISPERCPP_DIR, stderr=subprocess.DEVNULL)
        response = output.strip()
    except subprocess.CalledProcessError as e:
        return None

class TranscriptionHandler(http.server.BaseHTTPRequestHandler):
    def __init__(self, audio_cache_dir, max_file_size, max_cache_size, apikey, *args):
        self.audio_cache_dir = Path(audio_cache_dir)
        if not self.audio_cache_dir.exists():
            self.audio_cache_dir.mkdir(parents=True)
        self.max_file_size = max_file_size
        self.max_cache_size = max_cache_size
        self.lock = Lock()
        self.salt = ''.join(secrets.choice(alphabet) for i in range(API_KEY_LENGTH))
        self.apikeyhash = hashlib.sha256((apikey + self.salt).encode('ascii')).digest()
        http.server.BaseHTTPRequestHandler.__init__(self, *args)

    def do_GET(self):
        pass

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            self.send_error(HTTPStatus.LENGTH_REQUIRED, 'Content-Length required')
            return

        if content_length > self.max_file_size:
            self.send_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, 'File size exceeds maximum allowed')
            return

        # content_type = self.headers.get('Content-Type')
        # if !content_type.lower().startswith("audio/wav"):
        #     self.send_error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, 'Invalid Content-Type')
        #     return

        apikey = self.headers.get('ApiKey')
        if apikey is None or hashlib.sha256((apikey + self.salt).encode('ascii')).digest() != self.apikeyhash:
            return

        audio_data = self.rfile.read(content_length)

        lang = self.headers.get('Lang')
        if lang not in supported_languages:
            logger.warning(f'Unsupported lang: {lang} - trying auto')
            lang = 'auto'

        file_hash = hashlib.sha256(audio_data).hexdigest()
        file_path = self.audio_cache_dir / f"{file_hash}.wmv"
        if not file_path.exists():
            with file_path.open('wb') as f:
                f.write(audio_data)

        response = transcribe(file_path, lang)
        if not response:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f'Transcription failed')
            return
        print('transcribed:', response.decode('utf-8'))
        self.send_response(HTTPStatus.OK)
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Content-Length', len(response))
        self.end_headers()
        self.wfile.write(response)

        def cleanup():
            with self.lock:
                # Limit the size of the audio_cache directory
                total_cache_size = sum(f.stat().st_size for f in self.audio_cache_dir.iterdir() if f.is_file())
                while total_cache_size > self.max_cache_size - self.max_file_size:
                    oldest_file = min(self.audio_cache_dir.iterdir(), key=lambda f: f.stat().st_mtime)
                    oldest_file.unlink()
                    total_cache_size -= oldest_file.stat().st_size

        Thread(target=cleanup).start()

def setup_if_necessary():
    global WHISPERCPP_DIR
    global models_by_lang

    def try_run(condition, cmd, cwd=None):
        if condition():
            p = subprocess.run(cmd, cwd=cwd)
            if p.returncode != 0:
                exit(1)

    try_run(lambda: not WHISPERCPP_DIR.is_dir(), ['git', 'clone', 'https://github.com/ggerganov/whisper.cpp.git', str(WHISPERCPP_DIR)])

    try_run(lambda: not (WHISPERCPP_DIR / 'main').exists(), ['make'], WHISPERCPP_DIR.resolve())

    for model in ('tiny', 'tiny.en'):
        try_run(lambda: True, ['./download-ggml-model.sh', model], (WHISPERCPP_DIR / 'models').resolve())

def main(server_address, audio_cache_dir, max_file_size, max_cache_size, apikey):
    apikey = apikey if apikey else ''.join(secrets.choice(alphabet) for i in range(API_KEY_LENGTH))
    print("Api Key:", apikey)
    def handler(*args):
        TranscriptionHandler(audio_cache_dir, max_file_size, max_cache_size, apikey, *args)

    httpd = http.server.HTTPServer(server_address, handler)
    print('Listening on', server_address[0], 'and port', server_address[1])
    httpd.serve_forever()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='HTTP Server')
    parser.add_argument('--api-key', type=str, help='The api key to use. If not specified generates a secure random key that is printed on startup.')
    parser.add_argument('--ip', default='0.0.0.0', type=str, help='listening ip')
    parser.add_argument('--port', default=21483, type=int, help='listening port')
    parser.add_argument('--audio-cache-dir', default='audio_cache', type=str, help='cache directory to store audio files')
    parser.add_argument('--max-file-size', default=200 * 1024 * 1024, type=int, help='maximum file size')
    parser.add_argument('--max-cache-size', type=int, default=5 * 1024 * 1024 * 1024, help='The maximum size in bytes of the audio cache directory.')
    parser.add_argument('--whispercpp-dir', type=str, default='./whisper.cpp/', help='Path to the whisper.cpp directory. If it does not exist, it is created.')
    args = parser.parse_args()

    WHISPERCPP_DIR = Path(args.whispercpp_dir)
    setup_if_necessary()

    server_address = (args.ip, args.port)
    main(server_address, args.audio_cache_dir, args.max_file_size, args.max_cache_size, args.api_key)
