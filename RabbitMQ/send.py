import pika

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))

channel = connection.channel()

channel.queue_declare(queue='myQueue')

channel.basic_publish(exchange='', routing_key='myQueue', body='Hello! ')

print("[x] Sent 'Hello!' ")

connection.close()