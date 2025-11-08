# ms_leilao.py (Corrected)

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
        # Use a copy of the list for safe iteration
        for auction in auctions[:]:
            try:
                # Check auction start
                if ( (currentTimestamp >= auction["start_time"]) and (auction["status"] == "nao iniciado") ):
                    auction["status"] = "ativo"
                    body = {
                        "id": auction["id"],
                        "description": auction["description"],
                        "end_time": auction["end_time"]
                    }

                    # FIX: Added the 'body' variable to the dumps() function
                    channel.basic_publish( exchange='auction_exchange', routing_key='leilao_iniciado', body=json.dumps(body))
                    
                    print(f"[MS Leilao] Leilao iniciado: {auction['id']}")
                
                # FIX: Added missing auction end logic
                elif ( (currentTimestamp >= auction["end_time"]) and (auction["status"] == "ativo") ):
                    auction["status"] = "encerrado"
                    body = {"id": auction["id"]}
                    channel.basic_publish(exchange='auction_exchange', routing_key='leilao_finalizado', body=json.dumps(body))
                    print(f"[MS Leilao] Leilao finalizado: {auction['id']}")

            except Exception as e:
                print(f"[MS Leilao] Error managing auction {auction.get('id')}: {e}")
    
        time.sleep(1)


# FIX: Changed route to '/leiloes' to match API Gateway
@app.route('/leiloes', methods=['POST'])
def create_auction():
    data = request.get_json()

    # FIX: Standardized keys to snake_case
    if not data or not all( parameters in data for parameters in ["id", "description", "start_time", "end_time"]):
        return jsonify({"error": "Missing data"}), 400
    
    newAuction = {
        "id": data["id"],
        "description": data["description"],
        "start_time": int(data["start_time"]), # FIX: snake_case
        "end_time": int(data["end_time"]),     # FIX: snake_case
        "status": "nao iniciado"
    }

    with auctionLock:
        auctions.append(newAuction)

    print(f"[MS Leilao] Novo leilao criado: {newAuction['id']}")
    return (jsonify(newAuction), 201)


# FIX: Changed route to '/leiloes' to match API Gateway
@app.route('/leiloes', methods=['GET'])
def get_active_auctions():
    activeAuctions = []
    with auctionLock:
        activeAuctions = [active for active in auctions if active["status"] == "ativo"]
    
    return (jsonify(activeAuctions), 200)

if __name__ == "__main__":
    auctionManagerThread = threading.Thread(target=manage_auctions, daemon=True)
    auctionManagerThread.start()

    print(f"[MS Leilao] Servidor REST iniciado na porta 5001")
    app.run(port=5001, host="0.0.0.0")