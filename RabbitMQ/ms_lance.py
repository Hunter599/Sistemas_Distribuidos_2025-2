import json
import pika
import os
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from utils.rabbitmq_utils import get_connection, declare_exchange, declare_queue

# ===============================
# Configura os diretórios dos clientes
# ===============================
CLIENTS_DIR = "clientes"
public_keys = {c: os.path.join(CLIENTS_DIR, c, "receiver.pem") for c in os.listdir(CLIENTS_DIR)}

# ===============================
# Dicionário para armazenar lances
# {auction_id: (user_id, bid_value)}
# ===============================
bids = {}

# ===============================
# Função para verificar assinatura
# ===============================
def verify_signature(pub_key_path, message: str, signature_hex: str):
    with open(pub_key_path, "r") as f:
        pub_key = RSA.import_key(f.read())
    h = SHA256.new(message.encode())
    signature = bytes.fromhex(signature_hex)
    try:
        pkcs1_15.new(pub_key).verify(h, signature)
        return True
    except (ValueError, TypeError):
        return False

# ===============================
# Callback ao receber um lance
# ===============================
def callback(ch, method, properties, body):
    payload = json.loads(body)
    message = payload["message"]
    signature = payload["signature"]

    auction_id = message["auction_id"]
    user_id = message["user_id"]
    bid_value = message["bid_value"]

    msg_str = json.dumps(message)
    pub_key_path = public_keys.get(user_id)

    if pub_key_path and verify_signature(pub_key_path, msg_str, signature):
        last_bid = bids.get(auction_id, (None, 0))
        if bid_value > last_bid[1]:
            bids[auction_id] = (user_id, bid_value)
            print(f"[MS LANCE] Lance válido de {user_id} no leilão {auction_id} por {bid_value}.")
            channel.basic_publish(
                exchange="leilao",
                routing_key="lance_lanzado",
                body=json.dumps(message)
            )
        else:
            print(f"[MS LANCE] Lance de {user_id} menor que o último lance.")
    else:
        print(f"[MS LANCE] Lance inválido de {user_id}.")

# ===============================
# Conexão e filas
# ===============================
connection = get_connection()
channel = connection.channel()

declare_exchange(channel, "auction_exchange", "direct")
declare_queue(channel, "lance_lanzado", "auction_exchange", "lance_realizado")

# Consome a fila de lances realizados
channel.basic_consume(queue="lance_lanzado", on_message_callback=callback, auto_ack=True)

print("[MS LANCE] Aguardando lances...")
channel.start_consuming()
