import pika
import time
import json
import threading
from flask import Flask, request, jsonify

app = Flask(__name__)

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()
channel.exchange_declare(exchange='auction_exchange', exchange_type='direct', durable=True)

auctions = []
auctionLock = threading.Lock()

def manage_auctions():
    while True:
        currentTimestamp = int(time.time())
        for auction in auctions:
            if ( (currentTimestamp >= auction["startTime"]) and (auction["status"] == "nao iniciado") ):
                auction["status"] = "ativo"
                body = {
                    "id": auction["id"],
                    "description": auction["description"],
                    "endTime": auction["endTime"]
                }

                channel.basic_publish( exchange='auction_exchange', routing_key='leilao_iniciado', body=json.dumps())
                
                print(f"[MS Leilao] Leilao iniciado: {auction["id"]}")
    
        time.sleep(1)


@app.route('/auctions', methods=['POST'])

def create_auction():
    data = request.get_json()

    if not data or not all( parameters in data for parameters in ["id", "description", "startTime", "endTime"]):
        return jsonify({"error": "Missing data"}), 400
    
    newAuction = {
        "id": data["id"],
        "description": data["description"],
        "startTime": int(data["StartTime"]),
        "endTime": int(data["endTime"]),
        "status": "nao iniciado"
    }

    with auctionLock:
        auctions.append(newAuction)

    print(f"[MS Leilao] Novo leilao cirado: {newAuction["id"]}")
    return (jsonify(newAuction), 201)


@app.route('/auctions', methods=['GET'])
def get_active_auctions():
    activeAuctions = []
    with auctionLock:
        activeAuctions = [active for active in auctions if active["status"] == "ativo"]
    
    return (jsonify(activeAuctions), 200)

if __name__ == "__main__":
    auctionManagerThread = threading.Thread(target=manage_auctions, daemon=True)
    auctionManagerThread.start()

    print(f"[MS Leilao] Servidor REST iniciado")
    app.run(port=5001, host="0.0.0.0")
    


