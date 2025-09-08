import pika
import time

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()

channel.exchange_declare(exchange='auction_exchange', exchange_type='direct', durable=True)

currentTimestamp = int(time.time())

leiloes = [
    {
        "id": "1",
        "description": "Notebook",
        "start_time": currentTimestamp + 5,
        "end_time": currentTimestamp + 30,
        "status": "nao iniciado"
    },
    {
        "id": "2",
        "description": "Notebook2",
        "start_time": currentTimestamp + 6,
        "end_time": currentTimestamp + 31,
        "status": "nao iniciado"
    }
]

try:

    while True:
        currentTimestamp = int(time.time())

        for leilao in leiloes:

            if (currentTimestamp >= leilao['start_time'] and leilao['status'] == 'nao iniciado'):

                leilao['status'] = 'ativo'

                message = f"ID:{leilao['id']},DESC:{leilao['description']},END:{leilao['end_time']}"

                channel.basic_publish(exchange='auction_exchange', routing_key='leilao_iniciado', body=message)

                print(f"\n Leilao iniciado para: {leilao['id']} - {leilao['description']}")

                time.sleep(1)

            elif (currentTimestamp >= leilao['end_time'] and leilao['status'] == 'ativo'):

                leilao['status'] = 'encerrado'

                message = f"ID:{leilao['id']}"

                channel.basic_publish(exchange='auction_exchange', routing_key='leilao_finalizado', body=message)

                print(f"\n Leilao finalizado para: {leilao['id']} - {leilao['description']}")
            
        time.sleep(1)

except KeyboardInterrupt:
    print("\n Shutting down MS Leilao...")
    connection.close()