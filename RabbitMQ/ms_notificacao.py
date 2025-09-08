import json
import pika
from utils.rabbitmq_utils import get_connection, declare_exchange, declare_queue

connection = get_connection()
channel = connection.channel()

declare_exchange(channel, "auction_exchange", "direct")

declare_queue(channel, "lance_validado_q", "auction_exchange", "lance_validado")
declare_queue(channel, "leilao_vencedor_q", "auction_exchange", "leilao_vencedor")

def callback(ch, method, properties, body):
    event = json.loads(body)
    auction_id = event["auction_id"]
    queue_name = f"leilao_{auction_id}"
    channel.basic_publish(exchange="auction_exchange", routing_key=queue_name, body=json.dumps(event))
    print(f"[MS NOTIFICAÇÃO] Enviado evento para {queue_name}: {event}")

channel.basic_consume(queue="lance_validado_q", on_message_callback=callback, auto_ack=True)
channel.basic_consume(queue="leilao_vencedor_q", on_message_callback=callback, auto_ack=True)

print("[MS NOTIFICAÇÃO] Aguardando eventos...")
channel.start_consuming()

