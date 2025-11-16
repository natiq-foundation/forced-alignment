from __future__ import annotations
import os
from kombu import Connection,Queue,Consumer,Exchange
import uuid
import socket

from core.align import align_audio
from dataclasses import dataclass

@dataclass
class QueueInfo:
    name: str
    exchange: str
    routing_key: str
    celery_task_name: str

def return_results(task_queue, producer, *messages):
    args = list(messages)
    kwargs = {}
    queue = Queue(task_queue.name, Exchange(task_queue.exchange), routing_key=task_queue.routing_key) 

    task_id = str(uuid.uuid4())

    producer.publish(
        [args, kwargs, None],
        exchange=queue.exchange,
        routing_key=queue.routing_key,
        declare=[queue],
        serializer="json",
        headers={
            'id': task_id,
            'lang': 'py',
            'task': task_queue.celery_task_name,
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

def callback(prod, body, message, task_queue):
    print('RECEIVED MESSAGE: {0!r}'.format(body))
    print(message)
    try:
        [audio_url, text, additional] = body[0]
        words_timestamps = align_audio(audio_url, text)
        message.ack()
        return_results(task_queue, prod, words_timestamps, additional)
    except Exception as e:
        print(f'Error processing message: {e}')
        message.reject(requeue=False)
        raise

def start_consumer(consume_queue_name, consume_routing_key, rabbitmq_url, task_queue):
    print("Started to listen...")
    print("Consume queue name:", consume_queue_name)
    queue = Queue(consume_queue_name, routing_key=consume_routing_key)
    with Connection(rabbitmq_url) as conn:
        producer = conn.Producer()
        with conn.channel() as channel:
            # Set prefetch_count=1 to only receive one message at a time
            channel.basic_qos(prefetch_size=0, prefetch_count=1, a_global=False)
            consumer = Consumer(channel, queue, accept=['json'])
            consumer.register_callback(lambda body, message: callback(producer, body, message, task_queue))
            with consumer:
                while True:
                    try:
                        conn.drain_events(timeout=30)
                    except TimeoutError:
                        # Timeout is expected when no messages arrive - continue polling
                        continue