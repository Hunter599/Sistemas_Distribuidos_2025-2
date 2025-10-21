import pika
import json
import threading
import requests
import time
from queue import Queue
from flask import Flask, request, jsonify, Response, stream_with_context

app = Flask(__name__)

MS_LEILAO_URL = "http://localhost:5001"
MS_LANCE_URL = "http://localhost:5002"

clientQueues = {}
clientLock = threading.Lock()

@app.route('/leiloes', methods=['POST'])
def create_auction():
    data = request.get_json()
    print(f" [API Gateway] Recebido POST /leiloes: {data}")

    try:
        response = requests.post(f"{MS_LEILAO_URL}/leiloes", json=data)
        response.raise_for_status()

        return response.json(), response.status_code()
    
    except requests.exceptions.RequestException as e:
        return jsonify({"Error": str(e)}), 500
    
@app.route('/leiloes', methods=['GET'])
def get_active_auctions():
    print("[API Gateway] Recebido GET /leiloes")

    try:
        response = request.get(f"{MS_LEILAO_URL}/leiloes")
        response.raise_for_status()
        return response.json(), response.status_code
    except request.exceptions.RequesteException as e:
        return jsonify({"Error": str(e)}), 500
    
@app.route('/lances', methods=['POST'])
def place_bid():
    data = request.get_json()
    print(f"[API Gateway] Recebido POST /lances: {data}")

    try:
        response = request.get(f"{MS_LANCE_URL}/lances")
        response.raise_for_status()
        return response.json(), response.status_code
    except request.exceptions.RequesteException as e:
        return jsonify({"Error": str(e)}), 500
    

@app.route('/stream/<client_id>')
def stream(clientId):

    def event_stream():

        queue = Queue()
        with clientLock:
            clientQueues[clientId] = queue
        
        print(f"[API Gateway] Cliente {clientId} conectado para SSE")

        try:
            while True:

                eventData = queue.get()

                if eventData is None:
                    break

                yield (f"data: {json.dumps(eventData)}\n\n" )
        
        finally:
            with clientLock:
                del clientQueues[clientId]
            print(f"[API Gateway] Cliente {clientId} desconectado")
    
    return Response(stream_with_context(event_stream()), content_type='text/event-stream')


def consume_notifications():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()
    channel.exchange_declare(exchange='auction_exchange', exchange_type='direct', durable=True)

    queuesToBind = {
        'lance_validado': 'lance_validado',
        'lance_invalidado': 'lance_invalidado',
        'leilao_vencedor': 'leilao_vencedor'
    }

    result = channel.queue_declare(queue='', exclusive=True)
    queueName = result.method.queue

    for routingKey in queuesToBind.values():
        channel.queue_bind(exchange='auction_exchange', queue=queueName, routing_key=routingKey)
    
    def callback(ch, method, properties, body):
        eventMessage = json.loads(body)
        eventType = method.routingKey

        print(f"[API Gateway] Evento recebido de RabbitMQ ({eventType}): {eventMessage}")

        event = {
            "type": eventType,
            "data": eventMessage
        }

        with clientLock:
            for clientId, queue in clientQueues.items():
                queue.put(event)
        
        channel.basic_consume(queue=queueName, on_message_callback=callback, auto_ack=True)
        print("[API Gatewat] Consumidor RabbitMQ iniciado.")
        channel.start_consuming()



if __name__ == '__main__':
    consumerThread = threading.Thread(target=consume_notifications, daemon=True)
    consumerThread.start()

    print("[API Gateway] Servidor REST/SSE iniciado")
    app.run(port=5004, host="0.0.0.0", threaded= True)