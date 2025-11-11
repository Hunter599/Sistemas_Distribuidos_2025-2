import pika
import json
import threading
import requests
import time
from queue import Queue
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

MS_LEILAO_URL = "http://localhost:5001"
MS_LANCE_URL = "http://localhost:5002"

# Dictionary that maps a client_id to they personal message queue
client_queues = {} # Format: {"client1": <Queue1>}

# Lock for the dictionary of clients
client_lock = threading.Lock() 

# Dictionary that maps the auction_id to a set of clients subscrited to it
auction_subscriptions = {} # Format: {"auction1: {client1, client2, ...} , ..."}

# Rest Endpoints - "Proxy"

# Handles create auction 
@app.route('/leiloes', methods=['POST'])
def create_auction():

    # Get JSON data that the React app sent
    data = request.get_json()
    print(f" [API Gateway] Recebido POST /leiloes: {data}")

    try:
        # Forwards the data to the ms_leilao service
        response = requests.post(f"{MS_LEILAO_URL}/leiloes", json=data)
        response.raise_for_status() # Checks for error
        return response.json(), response.status_code # returns the response to the react app
    
    except requests.exceptions.RequestException as e:
        return jsonify({"Error": str(e)}), 500
    
@app.route('/leiloes', methods=['GET'])
def get_active_auctions():
    print("[API Gateway] Recebido GET /leiloes")

    try:
        # FOrwards the GET request to the ms_leilao service
        response = requests.get(f"{MS_LEILAO_URL}/leiloes")
        response.raise_for_status()
        #returns the response to the react app
        return response.json(), response.status_code
    
    except requests.exceptions.RequestException as e: 
        return jsonify({"Error": str(e)}), 500
    
@app.route('/lances', methods=['POST'])
def place_bid():

    # Get the JSON data for the bid from React
    data = request.get_json()
    print(f"[API Gateway] Recebido POST /lances: {data}")

    try:
        # Forward the bid data to the ms_lance service
        response = requests.post(f"{MS_LANCE_URL}/lances", json=data) 
        response.raise_for_status()
        # Returns "Accepted" or "Rejected" response to the react app
        return response.json(), response.status_code
    
    except requests.exceptions.RequestException as e: 
        return jsonify({"Error": str(e)}), 500
    
# Subscription 

# "Follow" button 
@app.route('/auctions/<auction_id>/subscribe', methods=['POST'])
def subscribe_to_auction(auction_id):
    
    # Get client_id from JSON data
    data = request.get_json()
    client_id = data.get('client_id')

    if not client_id:
        return jsonify({"error": "client_id is required"}), 400

    # Using lock to modify the subscription list
    with client_lock:
        #Find or create the set for this auction
        if auction_id not in auction_subscriptions:
            auction_subscriptions[auction_id] = set()
        
        #Add the client to the set
        auction_subscriptions[auction_id].add(client_id)

    print(f"[API Gateway] Cliente {client_id} se inscreveu no leilao {auction_id}")
    return jsonify({"status": "subscribed", "auction": auction_id, "client": client_id}), 200



@app.route('/stream/<client_id>')
def stream(client_id): 

    # This function returns a "generator" (event_stream)
    def event_stream():

        #Create a new message queue for this specific client
        queue = Queue()

        # Uses the lock to add this client to the 'connected' list
        with client_lock:
            client_queues[client_id] = queue
        
        # This is the line that must appear in your terminal
        print(f"[API Gateway] Cliente {client_id} conectado para SSE")

        try:
            # WHile the connection is open...
            while True:

                # Awaits until a message is put in the queue
                event_data = queue.get()

                # 'None' message is a signal to shutdown
                if event_data is None:
                    break

                # When a message is received sends it to the client
                yield (f"data: {json.dumps(event_data)}\n\n" )
        
        finally:
            # If the connection is close cleans up
            with client_lock:
                del client_queues[client_id]

                for auction_id in auction_subscriptions:
                    auction_subscriptions[auction_id].discard(client_id)

            print(f"[API Gateway] Cliente {client_id} desconectado")
    
    # Return the generator function as a streaming response
    return Response(stream_with_context(event_stream()), content_type='text/event-stream')


# RabbitMQ consumer thread - Runs in the backgroud

def consume_notifications():

    # RabbitMQ connection
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()
    channel.exchange_declare(exchange='auction_exchange', exchange_type='direct', durable=True)

    # List all 5 notification events we want to listen for
    queues_to_bind = {
        'leilao_iniciado': 'leilao_iniciado',     
        'leilao_finalizado': 'leilao_finalizado', 
        'lance_validado': 'lance_validado',
        'lance_invalidado': 'lance_invalidado',
        'leilao_vencedor': 'leilao_vencedor',
        'link_pagamento': 'link_pagamento',
        'status_pagamento': 'status_pagamento'
    }

    # Creates a single private queue for the gateway
    result = channel.queue_declare(queue='', exclusive=True)
    queue_name = result.method.queue

    # Binds the created queue to all 5 event types
    for routing_key in queues_to_bind.values():
        channel.queue_bind(exchange='auction_exchange', queue=queue_name, routing_key=routing_key)
    
    # Callback function that runs every time a message arrives
    def callback(ch, method, properties, body): 

        # Gets info
        event_message = json.loads(body)
        event_type = method.routing_key

        print(f"[API Gateway] Evento recebido de RabbitMQ ({event_type}): {event_message}")

        # PAckage the event in the format our React app expects
        event = {
            "type": event_type,
            "data": event_message
        }

        # Uses the lock for accesing the client dictionaries
        with client_lock:

            if (event_type == 'link_pagamento' or event_type == 'status_pagamento'):

                # Private message, send to one user
                user_id = event_message.get('user_id') 
                if (user_id in client_queues):
                    # Puts the message in the client's personal queue
                    client_queues[user_id].put(event)
            
            else:
                # This is a public event (lance_validado, leilao_vencedor, etc.)
                # Get the auction_id from the event data
                auction_id = event_message.get('auction_id')
    
                if not auction_id:
                    # If that fails, try to get 'id' (for auction start/end events)
                    auction_id = event_message.get('id')
                
                if auction_id:
                    # Get the set of subscribed clients for this auction
                    # .get(auction_id, set()) returns an empty set if no one is subscribed
                    subscribed_clients = auction_subscriptions.get(auction_id, set())
                    
                    # Loop ONLY through the subscribed clients
                    for client_id in subscribed_clients:
                        # Check if that client is still connected
                        if client_id in client_queues:
                            # Send them the notification
                            client_queues[client_id].put(event)
    
    # Sets RabbitMQ to start listening and call out 'callback' fucntion
    channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
    print("[API Gateway] Consumidor RabbitMQ iniciado.")
    channel.start_consuming()


if __name__ == '__main__':
    consumerThread = threading.Thread(target=consume_notifications, daemon=True)
    consumerThread.start()

    print("[API Gateway] Servidor REST/SSE iniciado na porta 5000")
    app.run(port=5000, host="0.0.0.0", threaded= True)