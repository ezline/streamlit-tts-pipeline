import os
import numpy as np
from google.cloud import texttospeech
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = ''


def synthesize_text(client, text, language_code):

    input_text = texttospeech.SynthesisInput(text=text)
    names = list(map(lambda x:x.name, client.list_voices(language_code=language_code).voices))
    names = list(filter(lambda x:'Studio' not in x, names))
    names = list(filter(lambda x:'Chirp3' not in x, names))
    name = np.random.choice(names)
    
    voice = texttospeech.VoiceSelectionParams(
        language_code=language_code,
        name=name
    )
    audio_config = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.LINEAR16,
    speaking_rate=np.random.triangular(left=0.8, mode=1.0, right=1.5),
    pitch=np.random.triangular(left=-5, mode=0, right=5),
    volume_gain_db=np.random.triangular(left=-2, mode=0, right=2),
    sample_rate_hertz=16000,
    )
    response = client.synthesize_speech(
        request={"input": input_text, "voice": voice, "audio_config": audio_config}
    )

    return response, name