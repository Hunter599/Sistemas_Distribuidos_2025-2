import json
import pika
import os
import threading
from flask import Flask, request, jsonify

app = Flask(__name__)

bids = {}
activeAuctions = set()
auctionLock = threading.Lock()

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()
channel.exchange_declare(exchange='auction_exchange', exchange_type='direct', durable=True)

def consume_auction_events():
    consumerConnection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    consumerChannel = consumerConnection.channel()
    consumerChannel.exchange_declare(exchange='auction_exchange', exchange_type='direct', durable=True)

    resultStarted = consumerChannel.queue_declare(queue='', exclusive=True)
    queueStarted_Name = resultStarted.method.queue
    consumerChannel.queue_bind(exchange='auction_exchange', queue=queueStarted_Name, routing_key='leilao_finalizado')

    resultEnded = consumerChannel.queue_declare(queue='', exclusive=True)
    queueEnded_Name = resultEnded.method.queue
    consumerChannel.queue_bind(exchange='auction_exchange', queue=queueEnded_Name, routing_key='leilao_finalizado')


    def auction_started_callback(ch, method, properties, body):
        message = json.loads(body)
        auctionId = message["id"]
        
        with auctionLock:
            activeAuctions.add(auctionId)
        
        print(f"[MS Lance] Leilao {auctionId} iniciado. Agora aceitando lances")

    def auction_ended_callback(ch, method, properties, body):
        message = json.loads(body)
        auctionId = message["id"]

        with auctionLock:
            if (auctionId in activeAuctions):
                activeAuctions.remove(auctionId)
            
            winnerInfo = bids.get(auctionId)
        
        if (winnerInfo):
            winnerId, bidValue = winnerInfo
            winnerData = {
                "auctionId": auctionId,
                "winnerId": winnerId,
                "bidValue": bidValue
            }

            channel.basic_publish(exchange='auction_exchange', routing_key='leilao_vencedor', body=json.dumps(winnerData))
            print(f"[MS Lance] Leilao {auctionId} finalizado. Vencedor: {winnerId}")
        
        else:

            print(f"[MS Lance] Leilao {auctionId} finalizado. Sem lances")
        
    consumerChannel.basic_consume(queue=queueStarted_Name, on_message_callback=auction_started_callback, auto_ack=True)
    consumerChannel.basic_consume(queue=queueEnded_Name, on_message_callback=auction_ended_callback, auto_ack=True)

    print("[MS Lance] Aguardando eventos de leilao... ")
    consumerChannel.start_consuming()
            
@app.route("/lances", methods=['POST'])
def place_bid():
    data = request.get_json()
    auctionId = data["auctionId"]
    userId = data["userId"]
    bidValue = data["bidValue"]

    eventMessage = {
        "auctionId": auctionId,
        "userId": userId,
        "bidValue": bidValue
    }

    with auctionLock:

        if (auctionId not in activeAuctions):
            print(f"[MS Lance] Lance rejeitado (leilao {auctionId}) nao ativo")
            channel.basic_publish(exchange='auction_exchange', routing_key="lance_invalido", body=json.dumps(eventMessage))
            return jsonify({"status": "rejected", "reason": "Auction not active"}), 400
        
        lastBidValue = bids.get(auctionId, (None, 0))[1]
        if (bidValue <= lastBidValue):
            print(f"[MS Lance] Lance rejeitado (valor {bidValue}) inferior ou igual a {lastBidValue}")
            channel.basic_publish(exchange='auction_exchange', routing_key="lance_invalido", body=json.dumps(eventMessage))
            return jsonify({"status": "rejected", "reason": "Bid not higher than leading bid"}), 400
        
        bids[auctionId] = (userId, bidValue)
        print(f"[MS Lance] Lance valido de {userId} no leilao {auctionId} por {bidValue}")
        channel.basic_publish(exchange='auction_exchange', routing_key='lance_validado', body=json.dumps(eventMessage))
        return jsonify({"status": "accepted"}), 200
    

if __name__ == '__main__':

    consumerThread = threading.Thread(target= consume_auction_events, daemon=True)
    consumerThread.start()

    print("[MS Lance] Servidor Rest iniciado")
    app.run(port=5002, host='0.0.0.0')
