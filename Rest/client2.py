import pika
import threading
import json 
import os
import time
import queue

from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256

CLIENT_ID = "cliente2"
PRIVATE_KEY_PATH = os.path.join("clientes", CLIENT_ID, "private", "private.pem")

try:
    with open(PRIVATE_KEY_PATH, "r") as f:
        private_key = RSA.import_key(f.read())
except FileNotFoundError:
    print(f"Error with Private key, client - {CLIENT_ID} - {PRIVATE_KEY_PATH}")
    exit()

def sign_message(message):
    message_str = json.dumps(message, sort_keys=True)
    hash_obj = SHA256.new(message_str.encode())
    signature = pkcs1_15.new(private_key).sign(hash_obj)
    return signature.hex()

sharedQueue = queue.Queue()
subscribedAuction = set()

# RabbitMq Connection
connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()

channel.exchange_declare(exchange='auction_exchange', exchange_type='direct', durable=True)

def run_subscriber():


    subConnection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))

    # Subscriber own channel
    subChannel = subConnection.channel()

    subChannel.exchange_declare(exchange='auction_exchange', exchange_type='direct', durable=True)

    result = subChannel.queue_declare(queue='', exclusive=True)
    queueName = result.method.queue

    subChannel.queue_bind(exchange='auction_exchange', queue=queueName, routing_key='leilao_iniciado')

    print(f"\n Subscriber Thread listering on private queue '{queueName}'")

    print("\n Waiting for auction messages...")

   

    def callback(ch, method, properties, body):
        
        if ( method.routing_key == 'leilao_iniciado' ):

            print(f"\n Novo leilao iniciado: {body.decode()}")

        else:
            mess = json.loads(body.decode())
            if ( 'user_id' in mess ):
                print(f"\n Notificacao do leilao {mess['auction_id']}:")

                print(f"\n Lance de {mess['user_id']} - valor: {mess['bid_value']}")

            elif ( "winner_id" in mess ):
                
                print(f"\n Vencedor leilao {mess['auction_id']}!")

                print(f"\n Vencedor {mess['winner_id']} com o lance de {mess['bid_value']}.")
    
    subChannel.basic_consume(queue=queueName, on_message_callback=callback, auto_ack=True)

    def binding_requests():
        try:
            routingKey = sharedQueue.get_nowait()
            if routingKey:
                if routingKey not in subscribedAuction:
                    print(f"\n Subscribing to notifications for {routingKey}...")
                    subChannel.queue_bind(exchange='auction_exchange', queue=queueName, routing_key=routingKey)
                    subscribedAuction.add(routingKey)
                    sharedQueue.task_done()
        except queue.Empty:
            pass

        subConnection.call_later(1, binding_requests)

    subConnection.call_later(1, binding_requests)
    subChannel.start_consuming()

subscriberThread = threading.Thread(target=run_subscriber, daemon= True)
subscriberThread.start()

time.sleep(1)
print(f"\n {CLIENT_ID} ready. Ready to send bids.")

try:
    while True:

        bidInput = input("\n >> Bid <auction_id> <value> \n")
        params = bidInput.split()

        if ( len(params) == 3 and params[0] == 'bid' ):
            auctionId = params[1]
            value = int(params[2])
            userId = CLIENT_ID

            message = {
                "auction_id": auctionId,
                "user_id": userId,
                "bid_value": value

            }

            signature_hex = sign_message(message)

            payload = { "message": message, "signature": signature_hex}

            body = json.dumps(payload)

            channel.basic_publish(exchange='auction_exchange', routing_key='lance_realizado', body=body)

            print(f"\n Bid sent for auction {auctionId}: User{userId} with value {value}")

            if ( auctionId not in subscribedAuction ):
                routingKey = f"leilao_{auctionId}"

                sharedQueue.put(routingKey)
                subscribedAuction.add(auctionId)
                
        
        else:
            print("\n Invalid command -- Format: bid <auction_id> <user_id> <value>")

except KeyboardInterrupt:
    print("\n Shutting down client...")
    connection.close()

