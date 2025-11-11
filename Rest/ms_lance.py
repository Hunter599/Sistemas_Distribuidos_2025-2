# ms_lance.py (Corrected)

import json
import pika
import os
import threading
from flask import Flask, request, jsonify

# Flask web server instance
app = Flask(__name__)

# Dictionary stores the current highest bid for each auction
bids = {} # Format: { "auction1": ("client1", 150), ...}

# Stores the IDs of all auctions that are currently 'active'
activeAuctions = set()

# Lock for bids and active auctions
auctionLock = threading.Lock()

# Connection to RabbitMQ for publishing messages (lance_validado, leilao_vencedor)
connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()
channel.exchange_declare(exchange='auction_exchange', exchange_type='direct', durable=True)

# RabbitMq consumer thread
def consume_auction_events():

    # New separate connection to RabbitMQ for this thread
    consumerConnection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    consumerChannel = consumerConnection.channel()
    consumerChannel.exchange_declare(exchange='auction_exchange', exchange_type='direct', durable=True)

    # Creates private queue for 'leilao_iniciado' events
    resultStarted = consumerChannel.queue_declare(queue='', exclusive=True)
    queueStarted_Name = resultStarted.method.queue
    consumerChannel.queue_bind(exchange='auction_exchange', queue=queueStarted_Name, routing_key='leilao_iniciado')

    # Create a private queue for 'leilao_finalizado' events
    resultEnded = consumerChannel.queue_declare(queue='', exclusive=True)
    queueEnded_Name = resultEnded.method.queue
    consumerChannel.queue_bind(exchange='auction_exchange', queue=queueEnded_Name, routing_key='leilao_finalizado')

    # Callback for when a 'leulao_iniciado' message arrives
    def auction_started_callback(ch, method, properties, body):
        message = json.loads(body)
        auctionId = message["id"]
        
        # Uses the lock to modify the 'activeAuctions' set
        with auctionLock:
            activeAuctions.add(auctionId)
        
        print(f"[MS Lance] Leilao {auctionId} iniciado. Agora aceitando lances")

    # Callback for when a 'leilao_finalizado' message arrives
    def auction_ended_callback(ch, method, properties, body):
        message = json.loads(body)
        auctionId = message["id"] # 'id' is fine, it's consistent

        # lock for safety
        with auctionLock:
            # Removes the auction from the active set
            if (auctionId in activeAuctions):
                activeAuctions.remove(auctionId)
            
            # Get the highest bid from our 'bids' dictionary
            winnerInfo = bids.get(auctionId)
        

        # If winner exists...
        if (winnerInfo):

            # Prepare the winner data
            winnerId, bidValue = winnerInfo
            winnerData = {
                "auction_id": auctionId,
                "winner_id": winnerId,
                "bid_value": bidValue
            }

            # Pusblish the 'leilao_vencedor' event
            channel.basic_publish(exchange='auction_exchange', routing_key='leilao_vencedor', body=json.dumps(winnerData))
            print(f"[MS Lance] Leilao {auctionId} finalizado. Vencedor: {winnerId}")
        
        else:
            print(f"[MS Lance] Leilao {auctionId} finalizado. Sem lances")
    
    # Tell RabbitMQ to start listening and use our callback functions
    consumerChannel.basic_consume(queue=queueStarted_Name, on_message_callback=auction_started_callback, auto_ack=True)
    consumerChannel.basic_consume(queue=queueEnded_Name, on_message_callback=auction_ended_callback, auto_ack=True)

    print("[MS Lance] Aguardando eventos de leilao... ")
    consumerChannel.start_consuming()

# Endpoint that the API Gateway calls for bids

@app.route("/lances", methods=['POST'])
def place_bid():

    # Get the bid data from the API Gateway's request
    data = request.get_json()
    auctionId = data["auction_id"]
    userId = data["user_id"]
    bidValue = data["bid_value"]

    # Prepare the message to be published (for success or failure)
    eventMessage = {
        "auction_id": auctionId,
        "user_id": userId,
        "bid_value": bidValue
    }

    # Uses the lock for reading 'activeAuctions' and read/write 'bids'
    with auctionLock:

        # Is the auction active?
        if (auctionId not in activeAuctions):
            print(f"[MS Lance] Lance rejeitado (leilao {auctionId}) nao ativo")
            # Publish an 'invalid' event
            channel.basic_publish(exchange='auction_exchange', routing_key="lance_invalidado", body=json.dumps(eventMessage))
            # Returns a 400 to the API gateway
            return jsonify({"status": "rejected", "reason": "Auction not active"}), 400

        # Checks if the last bid is high enough
        lastBidValue = bids.get(auctionId, (None, 0))[1]
        if (bidValue <= lastBidValue):
            print(f"[MS Lance] Lance rejeitado (valor {bidValue}) inferior ou igual a {lastBidValue}")
            # Publish an 'invalid' event
            channel.basic_publish(exchange='auction_exchange', routing_key="lance_invalidado", body=json.dumps(eventMessage))
            # Returns a 400 to the API gateway
            return jsonify({"status": "rejected", "reason": "Bid not higher than leading bid"}), 400
        
        # else... the bid is valid
        bids[auctionId] = (userId, bidValue)
        print(f"[MS Lance] Lance valido de {userId} no leilao {auctionId} por {bidValue}")

        # Publishes the 'lance_validado' event and return 200 status code
        channel.basic_publish(exchange='auction_exchange', routing_key='lance_validado', body=json.dumps(eventMessage))
        return jsonify({"status": "accepted"}), 200
    

if __name__ == '__main__':
    # Create and start background consumer thread
    consumerThread = threading.Thread(target= consume_auction_events, daemon=True)
    consumerThread.start()

    # Main thread
    print("[MS Lance] Servidor Rest iniciado na porta 5002")
    app.run(port=5002, host='0.0.0.0')