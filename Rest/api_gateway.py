# api_gateway.py (Corrected)

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

client_queues = {} 
client_lock = threading.Lock() 

@app.route('/leiloes', methods=['POST'])
def create_auction():
    data = request.get_json()
    print(f" [API Gateway] Recebido POST /leiloes: {data}")

    try:
        response = requests.post(f"{MS_LEILAO_URL}/leiloes", json=data)
        response.raise_for_status()
        return response.json(), response.status_code
    
    except requests.exceptions.RequestException as e:
        return jsonify({"Error": str(e)}), 500
    
@app.route('/leiloes', methods=['GET'])
def get_active_auctions():
    print("[API Gateway] Recebido GET /leiloes")

    try:
        response = requests.get(f"{MS_LEILAO_URL}/leiloes")
        response.raise_for_status()
        return response.json(), response.status_code
    
    except requests.exceptions.RequestException as e: 
        return jsonify({"Error": str(e)}), 500
    
@app.route('/lances', methods=['POST'])
def place_bid():
    data = request.get_json()
    print(f"[API Gateway] Recebido POST /lances: {data}")

    try:
        response = requests.post(f"{MS_LANCE_URL}/lances", json=data) 
        response.raise_for_status()
        return response.json(), response.status_code
    
    except requests.exceptions.RequestException as e: 
        return jsonify({"Error": str(e)}), 500
    

#
# >>> THIS IS THE BROKEN PART IN YOUR OLD FILE <<<
# Make sure your file has this corrected version
#
@app.route('/stream/<client_id>')
def stream(client_id): 

    def event_stream():
        queue = Queue()
        with client_lock:
            client_queues[client_id] = queue
        
        # This is the line that must appear in your terminal
        print(f"[API Gateway] Cliente {client_id} conectado para SSE")

        try:
            while True:
                event_data = queue.get()
                if event_data is None:
                    break
                yield (f"data: {json.dumps(event_data)}\n\n" )
        
        finally:
            with client_lock:
                del client_queues[client_id]
            print(f"[API Gateway] Cliente {client_id} desconectado")
    
    return Response(stream_with_context(event_stream()), content_type='text/event-stream')


def consume_notifications():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()
    channel.exchange_declare(exchange='auction_exchange', exchange_type='direct', durable=True)

    queues_to_bind = {
        'lance_validado': 'lance_validado',
        'lance_invalidado': 'lance_invalidado',
        'leilao_vencedor': 'leilao_vencedor',
        'link_pagamento': 'link_pagamento',
        'status_pagamento': 'status_pagamento'
    }

    result = channel.queue_declare(queue='', exclusive=True)
    queue_name = result.method.queue

    for routing_key in queues_to_bind.values():
        channel.queue_bind(exchange='auction_exchange', queue=queue_name, routing_key=routing_key)
    
    def callback(ch, method, properties, body):
        event_message = json.loads(body)
        event_type = method.routing_key

        print(f"[API Gateway] Evento recebido de RabbitMQ ({event_type}): {event_message}")

        event = {
            "type": event_type,
            "data": event_message
        }

        with client_lock:
            if (event_type == 'link_pagamento' or event_type == 'status_pagamento'):
                # Look for 'user_id' (snake_case)
                user_id = event_message.get('user_id') 

                if (user_id in client_queues):
                    client_queues[user_id].put(event)
            else:
                for client_id, queue in client_queues.items():
                    queue.put(event)
        
    channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)
    print("[API Gateway] Consumidor RabbitMQ iniciado.")
    channel.start_consuming()


if __name__ == '__main__':
    consumerThread = threading.Thread(target=consume_notifications, daemon=True)
    consumerThread.start()

    print("[API Gateway] Servidor REST/SSE iniciado na porta 5000")
    app.run(port=5000, host="0.0.0.0", threaded= True)