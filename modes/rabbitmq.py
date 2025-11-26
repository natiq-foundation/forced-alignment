from __future__ import annotations
import os
import time
import json
import uuid
import socket
from dataclasses import dataclass
import boto3
from kombu import Connection, Queue, Consumer, Exchange
from kombu.exceptions import OperationalError

from core.align import align_audio

@dataclass
class QueueInfo:
    name: str
    exchange: str
    routing_key: str
    celery_task_name: str


@dataclass
class S3Config:
    bucket: str
    prefix: str = ""
    region: str = "us-east-1"
    endpoint_url: str | None = None

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


def _get_s3_client(s3_config: S3Config):
    client_kwargs = {}
    if s3_config.endpoint_url:
        client_kwargs["endpoint_url"] = s3_config.endpoint_url
    return boto3.client("s3", **client_kwargs)


def _upload_alignment_to_s3(words_timestamps, additional, s3_config: S3Config) -> str:
    bucket = s3_config.bucket
    prefix = (s3_config.prefix or "").strip("/")
    object_key = f"{prefix + '/' if prefix else ''}{uuid.uuid4().hex}.json"

    payload = {
        "results": words_timestamps,
        "meta": additional,
    }
    body = json.dumps(payload).encode("utf-8")

    s3 = _get_s3_client(s3_config)
    s3.put_object(
        ACL="public-read",
        Bucket=bucket,
        Key=object_key,
        Body=body,
        ContentType="application/json",
    )

    if s3_config.endpoint_url:
        endpoint = s3_config.endpoint_url.rstrip("/")
        url = f"{endpoint}/{bucket}/{object_key}"
    else:
        url = f"https://{bucket}.s3.{s3_config.region}.amazonaws.com/{object_key}"
    return url


def callback(prod, body, message, task_queue, s3_config: S3Config):
    print('RECEIVED MESSAGE: {0!r}'.format(body))
    print(message)
    try:
        [audio_url, text, additional] = body[0]

        words_timestamps = align_audio(audio_url, text)

        s3_url = _upload_alignment_to_s3(words_timestamps, additional, s3_config)

        message.ack()

        return_results(task_queue, prod, s3_url, additional)
    except Exception as e:
        print(f'Error processing message: {e}')
        message.reject(requeue=False)

def start_consumer(consume_queue_name, consume_routing_key, rabbitmq_url, task_queue, s3_config: S3Config):
    print("Started to listen...")
    print("Consume queue name:", consume_queue_name)
    queue = Queue(consume_queue_name, routing_key=consume_routing_key)
    while True:
        try:
            with Connection(rabbitmq_url) as conn:
                producer = conn.Producer()
                with conn.channel() as channel:
                    channel.basic_qos(prefetch_size=0, prefetch_count=1, a_global=False)
                    consumer = Consumer(channel, queue, accept=['json'])
                    consumer.register_callback(
                        lambda body, message: callback(producer, body, message, task_queue, s3_config)
                    )
                    with consumer:
                        while True:
                            try:
                                conn.drain_events(timeout=30)
                            except TimeoutError:
                                continue
        except KeyboardInterrupt:
            print("Consumer interrupted. Shutting down.")
            break
        except OperationalError as exc:
            print(f"Connection lost ({exc}). Reconnecting in 5 seconds...")
            time.sleep(5)
        except Exception as exc:
            print(f"Unexpected consumer error ({exc}). Reconnecting in 5 seconds...")
            time.sleep(5)
