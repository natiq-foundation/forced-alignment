import os
from modes.rabbitmq import start_consumer, QueueInfo
from dotenv import load_dotenv
from modes.http import start_http_server

load_dotenv()

if __name__ == "__main__":
	
    mode = os.environ.get("MODE", "rabbitmq")

    if mode == "rabbitmq":
        consume_queue_name = os.environ.get("CONSUME_QUEUE_NAME", "forced_alignment")
        consume_routing_key = os.environ.get("CONSUME_ROUTING_KEY", "forcedalignment.processing")
        rabbitmq_url = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672//")
        celery_task_name = os.environ.get("RESULT_CELERY_TASK_NAME", 'forced-alignment-done')
        result_queue_name = os.environ.get("RESULT_QUEUE_NAME", 'forced_alignment_done')
        result_queue_exchange = os.environ.get("RESULT_QUEUE_EXCHANGE",'forced_alignment_done')
        result_queue_routing_key = os.environ.get("RESULT_QUEUE_ROUTING_KEY", 'forcedalignment_done.processing')

        start_consumer(
    		consume_queue_name,
    		consume_routing_key,
    		rabbitmq_url,
    		QueueInfo(
    			result_queue_name,
    			result_queue_exchange,
    			result_queue_routing_key,
    			celery_task_name
    		)
    	)
    elif mode == "http":
        host = os.environ.get("HTTP_HOST", "0.0.0.0")
        port = os.environ.get("HTTP_PORT", "5000")
        start_http_server(host, int(port))
