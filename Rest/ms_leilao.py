import pika
import time
import json
import threading
from flask import Flask, request, jsonify

# Flask web server instance
app = Flask(__name__)

# Connection to RabbitMQ used for publishing
connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()
channel.exchange_declare(exchange='auction_exchange', exchange_type='direct', durable=True)

# Simple list that stores all auction objects
auctions = []

# Lock to protect the auctions list
auctionLock = threading.Lock()

# 
def manage_auctions():
    while True:

        # Get current timestamp
        currentTimestamp = int(time.time())
        # Use a copy of the list for safe iteration
        for auction in auctions[:]:
            try:
                # Check if its time to start the auction
                if ( (currentTimestamp >= auction["start_time"]) and (auction["status"] == "nao iniciado") ):

                    # Updates the status
                    auction["status"] = "ativo"
                    # Preapre the message body for event
                    body = {
                        "id": auction["id"],
                        "description": auction["description"],
                        "end_time": auction["end_time"]
                    }

                    # Publish the 'leilao iniciado' event to RabbitMQ
                    channel.basic_publish( exchange='auction_exchange', routing_key='leilao_iniciado', body=json.dumps(body))
                    
                    print(f"[MS Leilao] Leilao iniciado: {auction['id']}")
                
                # Check if it's time to end the auction
                elif ( (currentTimestamp >= auction["end_time"]) and (auction["status"] == "ativo") ):

                    # Updates the status
                    auction["status"] = "encerrado"

                    #Prepares the message body
                    body = {"id": auction["id"]}

                    # Publishes the 'leilao_finalizado' event to RabbitMQ
                    channel.basic_publish(exchange='auction_exchange', routing_key='leilao_finalizado', body=json.dumps(body))
                    print(f"[MS Leilao] Leilao finalizado: {auction['id']}")

            except Exception as e:
                print(f"[MS Leilao] Error managing auction {auction.get('id')}: {e}")
    
        time.sleep(1)


# Creates a new auction object
@app.route('/leiloes', methods=['POST'])
def create_auction():

    # Get the JSON data from the API gateway's request
    data = request.get_json()

    # Validation
    if not data or not all( parameters in data for parameters in ["id", "description", "start_time", "end_time"]):
        return jsonify({"error": "Missing data"}), 400

    # Creates the new auction object
    newAuction = {
        "id": data["id"],
        "description": data["description"],
        "start_time": int(data["start_time"]), 
        "end_time": int(data["end_time"]),     
        "status": "nao iniciado"
    }

    # Uses the lock to safely append the new auction to the shared list
    with auctionLock:
        auctions.append(newAuction)

    print(f"[MS Leilao] Novo leilao criado: {newAuction['id']}")

    # Return the new auction object with a "201 created" status code
    return (jsonify(newAuction), 201)


# Endpoint that gets all currently active auctions
@app.route('/leiloes', methods=['GET'])
def get_active_auctions():

    activeAuctions = []

    # Use the lock to safely read from the shared auctions list
    with auctionLock:
        # Gets the auctions that have status 'active'
        activeAuctions = [active for active in auctions if active["status"] == "ativo"]
    
    # Returns the list of active auctions
    return (jsonify(activeAuctions), 200)

if __name__ == "__main__":

    # Thread to 'manage_auctions'
    auctionManagerThread = threading.Thread(target=manage_auctions, daemon=True)
    auctionManagerThread.start()

    print(f"[MS Leilao] Servidor REST iniciado na porta 5001")
    # Flask web server runs in the main thread
    app.run(port=5001, host="0.0.0.0")