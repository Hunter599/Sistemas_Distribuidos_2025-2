import time
import threading
import requests
import random
from flask import Flask, request, jsonify

app = Flask(__name__) # Flask web server instance

# Background simulation thread

def simulate_payment_processing(transaction_id, webhook_url): # FIX: snake_case

    print(f"[External System] Processing transaction {transaction_id}")

    # Mimics the time is takes for a payment to clear
    time.sleep(random.randint(5, 10)) 

    # Randomly decides if the status is approved or refused
    status = random.choice(["aprovado", "recusado"])

    # Prepare the data to send back in the webhook
    webhookData = {
        "transaction_id": transaction_id,
        "status": status,
        "value": 123 # Dummy value
    }

    try:
        # The callback that makes the POST request to the webhook URL that ms_pagamento provided
        print(f"[External System] Sending webhook for {transaction_id} to {webhook_url}")
        requests.post(webhook_url, json=webhookData)

    except requests.exceptions.RequestException as e:
        # ms_pagamento is down
        print(f"[External System] Failed to send webhook for {transaction_id}: {e}")

# Endpoint that ms_pagamento calls

@app.route('/create_payment', methods = ['POST'])
def create_payment():

    # Get the order data from ms_pagamento
    data = request.get_json()

    transactionId = data['transaction_id']
    webhookUrl = data['webhook_url'] # "Pager number"
    userId = data['user_id']

    print(f"[External System] Payment creation request received for {userId}. Transaction ID: {transactionId}")

    # Starts the simulation in the background thread, letting give an immediate response
    threading.Thread(target=simulate_payment_processing, args=(transactionId, webhookUrl), daemon=True).start()

    # Immediately returns a fake payment link, ms_pagamento gets this response right away 
    paymentLink = f"http://payment-provider.com/pay?id={transactionId}"

    return jsonify({"payment_link": paymentLink}), 200 

if __name__ == '__main__':
    print("[External System] Simulador de Pagamento iniciado na porta 5004")
    # Flask web server
    app.run(port=5004, host='0.0.0.0')