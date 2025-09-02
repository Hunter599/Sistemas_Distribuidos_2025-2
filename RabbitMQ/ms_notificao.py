import json
import pika
from utils.rabbitmq_utils import get_connection, declare_exchange, declare_queue

connection = get_connection()
channel = connection.channel()

declare_exchange(channel, "leilao", "direct")

declare_queue(channel, "leilao_iniciado", "leilao", "lance_lanzado")
declare_queue(channel, "leilao_vencedor_q", "auction_exchange", "leilao_vencedor")

def callback(ch, method, properties, body):
    event = json.loads(body)
    auction_id = event["auction_id"]
    queue_name = f"leilao_{auction_id}"
    channel.queue_declare(queue=queue_name, durable=True)
    channel.basic_publish(exchange="", routing_key=queue_name, body=json.dumps(event))
    print(f"[MS NOTIFICAÇÃO] Enviado evento para {queue_name}: {event}")

channel.basic_consume(queue="lance_lanzado", on_message_callback=callback, auto_ack=True)
channel.basic_consume(queue="leilao_vencedor_q", on_message_callback=callback, auto_ack=True)

print("[MS NOTIFICAÇÃO] Aguardando eventos...")
channel.start_consuming()
