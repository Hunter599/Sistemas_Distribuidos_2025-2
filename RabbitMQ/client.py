import pika
import threading

# RabbitMq Connection
connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()

channel.exchange_declare(exchange='leilao', exchange_type='direct')

def run_subscriber():

    subConnection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))

    # Subscriber own channel
    subChannel = subConnection.channel()

    subChannel.exchange_declare(exchange='leilao', exchange_type='direct')

    subChannel.queue_declare(queue='leilao_iniciado', durable=True)

    subChannel.queue_bind(exchange='leilao', queue='leilao_iniciado', routing_key='leilao_iniciado')

    print("\n Waiting for auction messages...")


    def callback(ch, method, properties, body):
        print(f"\n{body.decode()}")

    subChannel.basic_consume(queue='leilao_iniciado', on_message_callback=callback, auto_ack=True)
    subChannel.start_consuming()

subscriberThread = threading.Thread(target=run_subscriber, daemon= True)
subscriberThread.start()

print("\n Client's ready. Ready to send bids.")

try:
    while True:

        bidInput = input(">> Bid <auction_id> <user_id> <value>")
        params = bidInput.split()

        if ( len(params) == 4 and params[0] == 'bid' ):
            auctionId = params[1]
            userId = params[2]
            value = params[3]

            message = f"\n ID:{auctionId} - User:{userId} - Value:{value}"

            channel.basic_publish(exchange='leilao', routing_key='lance_lanzado', body=message)

            print(f"\n Bid sent for auction {auctionId}: User{userId} with value {value}")
        
        else:
            print("\n Invalid command -- Format: bid <auction_id> <user_id> <value>")

except KeyboardInterrupt:
    print("\n Shutting down client...")
    connection.close()

