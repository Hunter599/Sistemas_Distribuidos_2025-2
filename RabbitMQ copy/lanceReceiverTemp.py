# temp_lance_receiver.py
import pika
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()
channel.exchange_declare(exchange='leilao', exchange_type='direct')
channel.queue_declare(queue='lance_realizado', durable=True)
channel.queue_bind(exchange='leilao', queue='lance_realizado', routing_key='lance_lanzado')
def callback(ch, method, properties, body):
    print(f" [x] Received Bid: {body.decode()}")
channel.basic_consume(queue='lance_realizado', on_message_callback=callback, auto_ack=True)
print(' [*] Waiting for bids.')
channel.start_consuming()