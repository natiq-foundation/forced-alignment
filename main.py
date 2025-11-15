from __future__ import annotations
import requests
import tempfile
import os
from pydub import AudioSegment
from ctc_forced_aligner import (
    load_audio,
    load_alignment_model,
    generate_emissions,
    preprocess_text,
    get_alignments,
    get_spans,
    postprocess_results,
)
import torch
from kombu import Connection,Queue,Consumer,Exchange
import uuid
import socket
from dotenv import load_dotenv

load_dotenv()

def download_and_convert_mp3_to_wav(mp3_url: str) -> str:
    response = requests.get(mp3_url)
    if response.status_code != 200:
        return "failed to download"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as mp3_file:
        mp3_file.write(response.content)
        mp3_path = mp3_file.name
    wav_path = mp3_path.replace(".mp3", ".wav")
    audio = AudioSegment.from_mp3(mp3_path)
    audio.export(wav_path, format="wav")
    os.remove(mp3_path)
    return wav_path

def align_audio(mp3_url, text, batch_size = 4, romanize = True, language = "ar"):
    wav_path = download_and_convert_mp3_to_wav(mp3_url)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    alignment_model, alignment_tokenizer = load_alignment_model(
        device,
        dtype=torch.float16 if device == "cuda" else torch.float32,
    )
    audio_waveform = load_audio(wav_path, alignment_model.dtype, alignment_model.device)
    os.remove(wav_path)
    text = text.strip().replace("\n", " ")
    emissions, stride = generate_emissions(
        alignment_model, audio_waveform, batch_size=batch_size
    )
    tokens_starred, text_starred = preprocess_text(
        text,
        romanize=romanize,
        language=language,
    )
    segments, scores, blank_token = get_alignments(
        emissions,
        tokens_starred,
        alignment_tokenizer,
    )
    spans = get_spans(tokens_starred, segments, blank_token)
    word_timestamps = postprocess_results(text_starred, spans, stride, scores)
    return word_timestamps


task_queue = Queue(
    os.environ.get("RESULT_QUEUE_NAME", 'forced_alignment_done'),
    Exchange(os.environ.get("RESULT_QUEUE_EXCHANGE",'forced_alignment_done')),
    routing_key=os.environ.get("RESULT_QUEUE_ROUTING_KEY", 'forcedalignment_done.processing')
)
def return_results(producer, *messages):
    args = list(messages)
    kwargs = {}

    task_id = str(uuid.uuid4())

    producer.publish(
        [args, kwargs, None],  # Pass Python object directly, let kombu serialize it
        exchange=task_queue.exchange,
        routing_key=task_queue.routing_key,
        declare=[task_queue],
        serializer="json",
        headers={
            'id': task_id,
            'lang': 'py',
            'task': os.environ.get("RESULT_CELERY_TASK_NAME", 'forced-alignment-done'),
            'argsrepr': repr(args),
            'kwargsrepr': repr(kwargs),
            'origin': f'{os.getpid()}@{socket.gethostname()}'
        },
        properties={
            'correlation_id': task_id,
            'content_type': 'application/json',
            'content_encoding': 'utf-8',
        }
    )

def callback(prod, body, message):
    print('RECEIVED MESSAGE: {0!r}'.format(body))
    print(message)
    [audio_url, text, additional] = body[0]
    words_timestamps = align_audio(audio_url, text)
    message.ack()
    return_results(prod, words_timestamps, additional)

if __name__ == '__main__':
    print("Started to listen...")

    consume_queue_name = os.environ.get("CONSUME_QUEUE_NAME", "forced_alignment")
    consume_routing_key = os.environ.get("CONSUME_ROUTING_KEY", "forcedalignment.processing")
    rabbitmq_url = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672//")

    queue = Queue(consume_queue_name, routing_key=consume_routing_key)
    with Connection(rabbitmq_url) as conn:
        producer = conn.Producer()
        with conn.channel() as channel:
            # Set prefetch_count=1 to only receive one message at a time
            channel.basic_qos(prefetch_size=0, prefetch_count=1, a_global=False)
            consumer = Consumer(channel, queue, accept=['json'])
            consumer.register_callback(lambda x,y: callback(producer, x, y))
            with consumer:
                while True:
                    conn.drain_events(timeout=1000)