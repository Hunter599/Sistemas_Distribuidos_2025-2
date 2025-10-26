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

# Dicionário para armazenar interesse de clientes por leilão
# {auction_id: set(client_ids)}
auctionInterests = {}

@app.route('/leiloes', methods=['POST'])
def create_auction():
    data = request.get_json()
    print(f"[API Gateway] Recebido POST /leiloes: {data}")

    try:
        response = requests.post(f"{MS_LEILAO_URL}/leiloes", json=data)
        response.raise_for_status()
        return response.json(), response.status_code
    except requests.exceptions.RequestException as e:
        print(f"[API Gateway] Erro ao criar leilão: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/leiloes', methods=['GET'])
def get_active_auctions():
    print("[API Gateway] Recebido GET /leiloes")

    try:
        response = requests.get(f"{MS_LEILAO_URL}/leiloes")
        response.raise_for_status()
        return response.json(), response.status_code
    except requests.exceptions.RequestException as e:
        print(f"[API Gateway] Erro ao consultar leilões: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/lances', methods=['POST'])
def place_bid():
    data = request.get_json()
    print(f"[API Gateway] Recebido POST /lances: {data}")

    try:
        response = requests.post(f"{MS_LANCE_URL}/lances", json=data)
        response.raise_for_status()
        return response.json(), response.status_code
    except requests.exceptions.RequestException as e:
        print(f"[API Gateway] Erro ao enviar lance: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/interesse', methods=['POST'])
def registrar_interesse():
    data = request.get_json()
    client_id = data.get("clientId")
    auction_id = data.get("auctionId")

    if not client_id or not auction_id:
        return jsonify({"error": "clientId e auctionId são obrigatórios"}), 400

    with clientLock:
        if auction_id not in auctionInterests:
            auctionInterests[auction_id] = set()
        auctionInterests[auction_id].add(client_id)

    print(f"[API Gateway] Cliente {client_id} registrou interesse no leilão {auction_id}")
    return jsonify({"status": "registrado"}), 200


@app.route('/cancelar_interesse', methods=['POST'])
def cancelar_interesse():
    data = request.get_json()
    client_id = data.get("clientId")
    auction_id = data.get("auctionId")

    if not client_id or not auction_id:
        return jsonify({"error": "clientId e auctionId são obrigatórios"}), 400

    with clientLock:
        if auction_id in auctionInterests and client_id in auctionInterests[auction_id]:
            auctionInterests[auction_id].remove(client_id)

    print(f"[API Gateway] Cliente {client_id} cancelou interesse no leilão {auction_id}")
    return jsonify({"status": "cancelado"}), 200


@app.route('/stream/<client_id>')
def stream(client_id):
    def event_stream():
        queue = Queue()
        with clientLock:
            clientQueues[client_id] = queue

        print(f"[API Gateway] Cliente {client_id} conectado para SSE")

        try:
            while True:
                eventData = queue.get()
                if eventData is None:
                    break
                yield f"data: {json.dumps(eventData)}\n\n"
        finally:
            with clientLock:
                clientQueues.pop(client_id, None)
            print(f"[API Gateway] Cliente {client_id} desconectado")

    return Response(stream_with_context(event_stream()), content_type='text/event-stream')


def consume_notifications():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()
    channel.exchange_declare(exchange='auction_exchange', exchange_type='direct', durable=True)

    queuesToBind = [
        'lance_validado',
        'lance_invalidado',
        'leilao_vencedor',
        'link_pagamento',
        'status_pagamento'
    ]

    result = channel.queue_declare(queue='', exclusive=True)
    queueName = result.method.queue

    for routingKey in queuesToBind:
        channel.queue_bind(exchange='auction_exchange', queue=queueName, routing_key=routingKey)

    def callback(ch, method, properties, body):
        eventMessage = json.loads(body)
        eventType = method.routing_key

        print(f"[API Gateway] Evento recebido ({eventType}): {eventMessage}")

        event = {
            "type": eventType,
            "data": eventMessage
        }

        auction_id = eventMessage.get("auctionId")

        with clientLock:
            for client_id, queue in clientQueues.items():
                # Se for evento relacionado a leilão, verifica interesse
                if auction_id and auction_id in auctionInterests:
                    if client_id not in auctionInterests[auction_id]:
                        continue
                queue.put(event)

    channel.basic_consume(queue=queueName, on_message_callback=callback, auto_ack=True)
    print("[API Gateway] Consumidor RabbitMQ iniciado.")
    channel.start_consuming()


if __name__ == '__main__':
    consumerThread = threading.Thread(target=consume_notifications, daemon=True)
    consumerThread.start()

    print("[API Gateway] Servidor REST/SSE iniciado")
    app.run(port=5004, host="0.0.0.0", threaded=True)
