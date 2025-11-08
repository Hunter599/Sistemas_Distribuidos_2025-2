# ms_pagamento.py (Corrected)

import pika
import json
import threading
import requests # Make sure this is 'requests'
import uuid
import time
from queue import Queue
from flask import Flask, request, jsonify, Response, stream_with_context

app = Flask(__name__)

# Note: Removed unused variables (bids, activeAuctions, etc.)

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()
channel.exchange_declare(exchange='auction_exchange', exchange_type='direct', durable=True)

# FIX: Port and protocol. Point to port 5004 and use http.
EXTERNAL_PAYMENT_SYSTEM_URL = "http://localhost:5004" 

pendingTransactions = {}

def consume_auction_winners():
    
    consumerConnection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    consumerChannel = consumerConnection.channel()
    consumerChannel.exchange_declare(exchange='auction_exchange', exchange_type='direct', durable=True)

    result = consumerChannel.queue_declare(queue='', exclusive=True)
    queueName = result.method.queue
    consumerChannel.queue_bind(exchange='auction_exchange', queue=queueName, routing_key='leilao_vencedor')

    def callback(ch, method, properties, body):
        # FIX: Standardized keys to snake_case
        winnerData = json.loads(body)
        auctionId = winnerData['auction_id']
        userId = winnerData['winner_id']
        value = winnerData['bid_value']

        print(f"[MS Pagamento] Vencedor recebido: {userId} do leilao {auctionId}. Valor: {value}")

        transactionId = str(uuid.uuid4())

        pendingTransactions[transactionId] = {
            "auction_id": auctionId, # FIX: snake_case
            "user_id": userId      # FIX: snake_case
        }

        try:
            # FIX: Standardized keys to snake_case
            paymentRequestData = { 
                "transaction_id": transactionId,
                "user_id": userId,
                "value": value,
                "webhook_url": "http://localhost:5003/pagamento/webhook"
            }

            print(f"[MS Pagamento] Criando link de pagamento para {transactionId}") # FIX: Typo 'Cirando'
            # FIX: Use 'requests.post', not 'request.post'
            response = requests.post(f"{EXTERNAL_PAYMENT_SYSTEM_URL}/create_payment",json=paymentRequestData) 
            response.raise_for_status()

            paymentLink = response.json()['payment_link'] # FIX: key 'payment_link'

            # FIX: Standardized keys to snake_case
            linkMessage = {
                "auction_id": auctionId,
                "user_id": userId,
                "payment_link": paymentLink
            }

            channel.basic_publish(exchange='auction_exchange',routing_key= 'link_pagamento', body= json.dumps(linkMessage))
            print(f"[MS Pagamento] Link de pagamento publicado para {userId}")
        
        # FIX: Use 'requests.exceptions.RequestException'
        except requests.exceptions.RequestException as e: 
            print(f"[MS Pagamento] Erro ao contatar sistema externo de pagamento: {e}")
        
    consumerChannel.basic_consume(queue=queueName, on_message_callback=callback, auto_ack=True)
    print("[MS Pagamento] aguardando vencedores de leiloes")
    consumerChannel.start_consuming()

@app.route('/pagamento/webhook', methods=['POST'])
def payment_webhook():
    data = request.get_json()
    # FIX: Standardized keys to snake_case
    transactionId = data['transaction_id']
    status = data['status']

    print(f"[MS Pagamento] Webhook recebido. Transacao {transactionId}, foi {status}") # FIX: Typo 'recebidp'

    transactionInfo = pendingTransactions.pop(transactionId, None) # Key is transactionId, that's fine

    if (transactionInfo):
        # FIX: Standardized keys to snake_case
        statusMessage = {
            "auction_id": transactionInfo['auction_id'],
            "user_id": transactionInfo['user_id'],
            "status": status
        }

        channel.basic_publish(exchange='auction_exchange', routing_key='status_pagamento', body=json.dumps(statusMessage))

        print(f"[MS Pagamento] Status de pagamento publicado para {transactionId}")
        return jsonify({"status": "received"}), 200 # Return a success response
    else:
        print(f"[MS Pagamento] Webhook para transacao desconhecida: {transactionId}")
        return jsonify({"error": "Transaction not found"}), 404
    
if __name__ == '__main__':
    consumerThread = threading.Thread(target=consume_auction_winners, daemon=True)
    consumerThread.start()

    print("[MS Pagamento] Servidor REST/Webhook iniciado na porta 5003") # FIX: Typo
    app.run(port=5003, host="0.0.0.0", threaded= True)