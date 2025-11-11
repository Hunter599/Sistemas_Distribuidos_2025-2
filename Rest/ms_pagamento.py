import pika
import json
import threading
import requests # act as a client to call the external payment system
import uuid # unique transactions IDs
import time
from queue import Queue
from flask import Flask, request, jsonify, Response, stream_with_context

# Flask web server instance (this server's main job is to host the webhook)
app = Flask(__name__)

# Connection to RabbitMQ for publishing messages (link_pagamento, status_pagamento)
connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()
channel.exchange_declare(exchange='auction_exchange', exchange_type='direct', durable=True)

EXTERNAL_PAYMENT_SYSTEM_URL = "http://localhost:5004" 

# Dictionary for pending transactions
pendingTransactions = {} # Format: { "Transaction": {"auction_id": "a1", "user_id": "u1"}, ...}

# Background RabbitMQ consumer thread
# Listens for messages from ms_lance

def consume_auction_winners():
    
    # Creates a new separate connection to RabbitMQ for this thread
    consumerConnection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    consumerChannel = consumerConnection.channel()
    consumerChannel.exchange_declare(exchange='auction_exchange', exchange_type='direct', durable=True)

    # Create a private queue for 'leilao_vencedor' events
    result = consumerChannel.queue_declare(queue='', exclusive=True)
    queueName = result.method.queue

    # Bidn this queue to the 'leilao_vencedor' routing key
    consumerChannel.queue_bind(exchange='auction_exchange', queue=queueName, routing_key='leilao_vencedor')

    # Callback that runs when a winner is declared
    def callback(ch, method, properties, body):

        # Gets winner data from the message
        winnerData = json.loads(body)
        auctionId = winnerData['auction_id']
        userId = winnerData['winner_id']
        value = winnerData['bid_value']

        print(f"[MS Pagamento] Vencedor recebido: {userId} do leilao {auctionId}. Valor: {value}")

        # Generates a unique order number for this payment
        transactionId = str(uuid.uuid4())

        # Stores the transaction info in the pendingTransaction dictionary
        pendingTransactions[transactionId] = {
            "auction_id": auctionId, 
            "user_id": userId      
        }

        try:

            # Prepares the order ticket for the external system
            paymentRequestData = { 
                "transaction_id": transactionId,
                "user_id": userId,
                "value": value,
                "webhook_url": "http://localhost:5003/pagamento/webhook" # Webhook, our "callback URL"
            }   

            print(f"[MS Pagamento] Criando link de pagamento para {transactionId}") 
            
            # Using the 'request.post' to act as a client
            response = requests.post(f"{EXTERNAL_PAYMENT_SYSTEM_URL}/create_payment",json=paymentRequestData) 
            response.raise_for_status()

            # Get the immediate response 
            paymentLink = response.json()['payment_link'] 

            # Prepare the notification for our client
            linkMessage = {
                "auction_id": auctionId,
                "user_id": userId,
                "payment_link": paymentLink
            }

            # Publish the payment link, the API gets this and sends it to the winning client
            channel.basic_publish(exchange='auction_exchange',routing_key= 'link_pagamento', body= json.dumps(linkMessage))
            print(f"[MS Pagamento] Link de pagamento publicado para {userId}")
        
        
        except requests.exceptions.RequestException as e: 
            print(f"[MS Pagamento] Erro ao contatar sistema externo de pagamento: {e}")
    
    # Tell RabbitMQ to start listening and use the callback
    consumerChannel.basic_consume(queue=queueName, on_message_callback=callback, auto_ack=True)
    print("[MS Pagamento] aguardando vencedores de leiloes")
    consumerChannel.start_consuming()

# Webhook endpoint
# URL given to the external system, it's for the external system to call

@app.route('/pagamento/webhook', methods=['POST'])
def payment_webhook():
    # Get the data sent
    data = request.get_json()
    transactionId = data['transaction_id']
    status = data['status']

    print(f"[MS Pagamento] Webhook recebido. Transacao {transactionId}, foi {status}") 

    # Retrieves and removes the transactiong from the dictionary
    transactionInfo = pendingTransactions.pop(transactionId, None) # Key is transactionId, that's fine

    if (transactionInfo):
        
        # Found for who the payment is for
        statusMessage = {
            "auction_id": transactionInfo['auction_id'],
            "user_id": transactionInfo['user_id'],
            "status": status
        }

        # Publish the final status, API gets this and sends it to the client, ends the loop
        channel.basic_publish(exchange='auction_exchange', routing_key='status_pagamento', body=json.dumps(statusMessage))

        print(f"[MS Pagamento] Status de pagamento publicado para {transactionId}")
        return jsonify({"status": "received"}), 200 # Return a success response
    else:
        print(f"[MS Pagamento] Webhook para transacao desconhecida: {transactionId}")
        return jsonify({"error": "Transaction not found"}), 404
    
if __name__ == '__main__':
    # RabbitMQ consumer in a background thread
    consumerThread = threading.Thread(target=consume_auction_winners, daemon=True)
    consumerThread.start()

    print("[MS Pagamento] Servidor REST/Webhook iniciado na porta 5003") 
    app.run(port=5003, host="0.0.0.0", threaded= True) # Webhook in mainthread