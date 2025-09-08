
import pika, sys, os, time


connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()

channel.exchange_declare(exchange='direct_logs', exchange_type='direct')

result = channel.queue_declare(queue='Myqueue', exclusive=True)
queue_name = result.method.queue

infos = sys.argv[1:]
if not infos:
    sys.stderr.write("Usage: %s [info] [warning] [error]\n" % sys.argv[0])
    sys.exit(1)

for info in infos:
    channel.queue_bind(exchange='direct_logs', queue=queue_name, routing_key=info)

print(" [*] Waiting for logs...")

def callback(ch, method, properties, body):
    print(f" [x] {method.routing_key}:{body}")

channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)

print( " [*] Waiting for messages. ")
channel.start_consuming()


