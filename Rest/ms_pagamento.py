import pika
import json
import threading
import requests
import uuid
import time
from queue import Queue
from flask import Flask, request, jsonify, Response, stream_with_context

app = Flask(__name__)

bids = {}
activeAuctions = set()
auctionLock = threading.Lock()

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()
channel.exchange_declare(exchange='auction_exchange', exchange_type='direct', durable=True)

EXTERNAL_PAYMENT_SYSTEM_URL = "https://localhost:5005"

pendingTransactions = {}


def consume_auction_winners():
    
    consumerConnection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    consumerChannel = consumerConnection.channel()
    consumerChannel.exchange_declare(exchange='auction_exchange', exchange_type='direct', durable=True)

    result = consumerChannel.queue_declare(queue='', exclusive=True)
    queueName = result.method.queue
    consumerChannel.queue_bind(exchange='auction_exchange', queue=queueName, routing_key='leilao_vencedor')

    def callback(ch, method, properties, body):
        winnerData = json.loads(body)
        auctionId = winnerData['auctionId']
        userId = winnerData['winnerId']
        value = winnerData['bidValue']

        print(f"[MS Pagamento] Vencedor recebido: {userId} do leilao {auctionId}. Valor: {value}")

        transactionId = str(uuid.uuid4())

        pendingTransactions[transactionId] = {
            "auctionId": auctionId,
            "userId": userId
        }

        try:
            paymentRequestDate = {
                "transactionId": transactionId,
                "userId": userId,
                "value": value,
                "webhookUrl": "http://localhost:5003/pagamento/webhook"
            }

            print(f"[MS Pagamento] Cirando link de pagamento para {transactionId}")
            response = request.post(f"{EXTERNAL_PAYMENT_SYSTEM_URL}/create_payment",json= paymentRequestDate)
            response.raise_for_status()

            paymentLink = response.json()['payment_link']

            linkMessage = {
                "auctionId": auctionId,
                "userId": userId,
                "paymentLink": paymentLink
            }

            channel.basic_publish(exchange='auction_exchange',routing_key= 'link_pagamento', body= json.dumps(linkMessage))
            print(f"[MS Pagamento] Link de pagamento publicado para {userId}")
        
        except request.exceptions.RequestException as e:
            print(f"[MS Pagamento] Erro ao contatar sistema externo de pagamento: {e}")
        
    consumerChannel.basic_consume(queue=queueName, on_message_callback=callback, auto_ack=True)
    print("[MS Pagamento] aguardando vencedores de leiloes")
    consumerChannel.start_consuming()

@app.route('/pagamento/webhook', methods=['POST'])
def payment_webhook():
    data = request.get_json()
    transactionId = data['transactionId']
    status = data['status']

    print(f"[MS Pagamento] Webhook recebidp. Transação {transactionId}, for {status}")

    transactionInfo = pendingTransactions.pop(transactionId, None)

    if (transactionInfo):
        statusMessage = {

            "auctionId": transactionInfo['auctionId'],
            "userId": transactionInfo['userId'],
            "status": status
        }

        channel.basic_publish(exchange='auction_exchange', routing_key='status_pagamento', body=json.dumps(statusMessage))

        print(f"[MS Pagamento] Status de pagamento publicado para {transactionId}")
    else:
        print(f"[MS Pagamento] Webhook para transacao desconhecida: {transactionId}")
        return jsonify({"error": "Transaction not found"}), 404
    
if __name__ == '__main__':
    consumerThread = threading.Thread(target=consume_auction_winners, daemon=True)
    consumerThread.start()

    print("[MS Pagamento] Servidor REWST/Webhookd iniciado")
    app.run(port=5003, host="0.0.0.0", threaded= True)