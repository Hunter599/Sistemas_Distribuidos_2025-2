import sys, pika

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()

channel.exchange_declare(exchange='direct_logs', exchange_type='direct')

info = sys.argv[1] if len(sys.argv) > 1 else 'info'
message = ' '.join(sys.argv[1:]) or "Hello World"
channel.basic_publish(exchange='direct_logs', routing_key=info, body=message)

print(f" [x] Sent {info}:{message}")

connection.close()