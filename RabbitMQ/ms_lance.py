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
activeAuctions = set()

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

    if ( auction_id not in activeAuctions ):
        print(f"\n [MS LANCE] Lance rejeitado. Leilao {auction_id} nao ativo.")
        return

    msg_str = json.dumps(message, sort_keys=True)
    pub_key_path = public_keys.get(user_id)

    if pub_key_path and verify_signature(pub_key_path, msg_str, signature):
        last_bid = bids.get(auction_id, (None, 0))
        if bid_value > last_bid[1]:
            bids[auction_id] = (user_id, bid_value)
            print(f"[MS LANCE] Lance válido de {user_id} no leilão {auction_id} por {bid_value}.")
            channel.basic_publish(
                exchange="auction_exchange",
                routing_key="lance_validado",
                body=json.dumps(message)
            )
        else:
            print(f"[MS LANCE] Lance de {user_id} menor que o último lance.")
    else:
        print(f"[MS LANCE] Lance inválido de {user_id}.")

def auctionStartedCallback(ch, method, properties, body):
    parts = body.decode().split(',')
    auctionId = parts[0].split(':')[1]
    activeAuctions.add(auctionId)
    print(f"\n [MS LANCE] Leilao {auctionId} iniciado.")

def auctionFinishedCallback(ch, method, properties, body):
    auctionId = body.decode().split(':')[1]

    if ( auctionId in activeAuctions ):
        activeAuctions.remove(auctionId)
    
    winnerInfo = bids.get(auctionId)
    

    if ( winnerInfo ):
        winnerId, bidValue = winnerInfo
        print(f"\n [MS LANCE] Leilao {auctionId} finalizado - Vencedor: {winnerId} com {bidValue}")

        winnerData = {
            "auction_id": auctionId,
            "winner_id": winnerId,
            "bid_value": bidValue
        }
    
        channel.basic_publish(exchange="auction_exchange", routing_key="leilao_vencedor", body=json.dumps(winnerData))
    
    else:
        print(f"\n [MS LANCE] Leilao {auctionId} finalizado sem lances.")

    

# ===============================
# Conexão e filas
# ===============================
connection = get_connection()
channel = connection.channel()

declare_exchange(channel, "auction_exchange", "direct")
declare_queue(channel, "lance_realizado_q", "auction_exchange", "lance_realizado")

# Consome a fila de lances realizados
channel.basic_consume(queue="lance_realizado_q", on_message_callback=callback, auto_ack=True)

declare_queue(channel, "leilao_iniciado_lance_q", "auction_exchange", "leilao_iniciado")
channel.basic_consume(queue="leilao_iniciado_lance_q", on_message_callback=auctionStartedCallback, auto_ack=True)

declare_queue(channel, "leilao_finalizado_q", "auction_exchange", "leilao_finalizado")
channel.basic_consume(queue="leilao_finalizado_q", on_message_callback=auctionFinishedCallback, auto_ack=True)

print("[MS LANCE] Aguardando lances...")
channel.start_consuming()

