import os

from dotenv import load_dotenv

from modes.http import start_http_server
from modes.rabbitmq import start_consumer, QueueInfo, S3Config


load_dotenv()

if __name__ == "__main__":
    mode = os.environ.get("MODE", "rabbitmq")

    if mode == "rabbitmq":
        consume_queue_name = os.environ.get("CONSUME_QUEUE_NAME", "forced_alignment")
        consume_routing_key = os.environ.get(
            "CONSUME_ROUTING_KEY", "forcedalignment.processing"
        )
        rabbitmq_url = os.environ.get(
            "RABBITMQ_URL", "amqp://guest:guest@localhost:5672//"
        )

        celery_task_name = os.environ.get(
            "RESULT_CELERY_TASK_NAME", "forced-alignment-done"
        )
        result_queue_name = os.environ.get(
            "RESULT_QUEUE_NAME", "forced_alignment_done"
        )
        result_queue_exchange = os.environ.get(
            "RESULT_QUEUE_EXCHANGE", "forced_alignment_done"
        )
        result_queue_routing_key = os.environ.get(
            "RESULT_QUEUE_ROUTING_KEY", "forcedalignment_done.processing"
        )
        s3_bucket = os.environ["AWS_S3_BUCKET"]
        s3_prefix = os.environ.get("AWS_S3_PREFIX", "")
        s3_region = os.environ.get("AWS_REGION", "us-east-1")
        s3_endpoint_url = os.environ.get("AWS_S3_ENDPOINT_URL")

        s3_config = S3Config(
            bucket=s3_bucket,
            prefix=s3_prefix,
            region=s3_region,
            endpoint_url=s3_endpoint_url,
        )

        start_consumer(
            consume_queue_name,
            consume_routing_key,
            rabbitmq_url,
            QueueInfo(
                result_queue_name,
                result_queue_exchange,
                result_queue_routing_key,
                celery_task_name,
            ),
            s3_config,
        )
    elif mode == "http":
        host = os.environ.get("HTTP_HOST", "0.0.0.0")
        port = os.environ.get("HTTP_PORT", "5000")
        start_http_server(host, int(port))
