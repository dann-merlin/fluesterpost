# fluesterpost
A simple Transcriptor HTTP Service using whisper by OpenAI ([whisper.cpp](https://github.com/ggerganov/whisper.cpp)) written in python

This script can be used in combination with my fork of the buster extension, which supports a custom HTTP API like this one.

There's a hopefully very helpful help page, when fluesterpost is called with the help flag:

```
# or ./fluesterpost.py -h
$ ./fluesterpost.py --help
usage: fluesterpost.py [-h] [--api-key API_KEY] [--ip IP] [--port PORT]
                       [--audio-cache-dir AUDIO_CACHE_DIR]
                       [--max-file-size MAX_FILE_SIZE] [--max-cache-size MAX_CACHE_SIZE]
                       [--whispercpp-dir WHISPERCPP_DIR]

HTTP Server

options:
  -h, --help            show this help message and exit
  --api-key API_KEY     The api key to use. If not specified generates a secure random
                        key that is printed on startup.
  --ip IP               listening ip
  --port PORT           listening port
  --audio-cache-dir AUDIO_CACHE_DIR
                        cache directory to store audio files
  --max-file-size MAX_FILE_SIZE
                        maximum file size
  --max-cache-size MAX_CACHE_SIZE
                        The maximum size in bytes of the audio cache directory.
  --whispercpp-dir WHISPERCPP_DIR
                        Path to the whisper.cpp directory. If it does not exist, it is
                        created.
```

Apart from the obvious flags (`--ip`, `--port`, `--help`) here are the explanations of the other flags:

## Usage

You basically just run the python script.

```
python3 fluesterpost.py
```

When a file that can be transcribed with `whisper.cpp` is received via a POST request and the API key is correct,
the transcription is sent back in text after a few seconds (or however long your system takes).

## Flags

### Api Key

Optionally an API key can be specified. The length can be anything really (actually I don't know the theoretical limit).
It can also be empty.
The API key is expected to be received via an "ApiKey" HTTP Header.
By default the API Key is generated each time the script is started to be random and secure and printed on launch.

So to have a persistent API Key, it needs to be specified.

### Audio cache directory

The audio files received are stored on disk (because whisper.cpp needs that).
The folder in which these files are stored can be specified using this option.
By default it is `./audio_cache`.

### Maximum file size

The maximum file size limits the size the files that may be transmitted to the server.
The default is `200MB`.

### Maximum cache size

The maximum cache size limits the summarized size of the files in the audio cache directory.
If the threshold is reached, files are deleted (by creation date), until the size is below the threshold again.
The default is `5GB`.

### `whisper.cpp` directory

The script checks if whisper.cpp is cloned to `./whisper.cpp/`, compiled and if the models are downloaded in `./whisper.cpp/models`.
A folder different from `./whisper.cpp` can also be specified using the --whispercpp-dir flag.

