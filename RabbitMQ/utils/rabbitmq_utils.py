import pika

def get_connection():
    return pika.BlockingConnection(pika.ConnectionParameters(host="localhost"))

def declare_exchange(channel, exchange_name, exchange_type="direct"):
    channel.exchange_declare(exchange=exchange_name, exchange_type=exchange_type, durable=True)

def declare_queue(channel, queue_name, exchange_name, routing_key):
    channel.queue_declare(queue=queue_name, durable=True)
    channel.queue_bind(exchange=exchange_name, queue=queue_name, routing_key=routing_key)
