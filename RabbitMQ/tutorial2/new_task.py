import sys, pika

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()

channel.queue_declare(queue='MyQueue', durable=True)


message = ' '.join(sys.argv[1:]) or "Hello World"
channel.basic_publish(exchange='', routing_key='MyQueue', body=message, properties=pika.BasicProperties(delivery_mode=pika.DeliveryMode.Persistent))
print(f" [x] Sent {message}")

connection.close()