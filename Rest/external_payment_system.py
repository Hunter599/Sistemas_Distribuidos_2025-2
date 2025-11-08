# external_payment_system.py (Corrected)

import time
import threading
import requests
import random
from flask import Flask, request, jsonify

app = Flask(__name__)

def simulate_payment_processing(transaction_id, webhook_url): # FIX: snake_case

    print(f"[External System] Processing transaction {transaction_id}")

    # FIX: Corrected typo 'ranint' to 'randint'
    time.sleep(random.randint(5, 10)) 

    status = random.choice(["aprovado", "recusado"])

    # FIX: Standardized keys to snake_case
    webhookData = {
        "transaction_id": transaction_id,
        "status": status,
        "value": 123
    }

    try:
        # FIX: Print the URL, not the data object
        print(f"[External System] Sending webhook for {transaction_id} to {webhook_url}")
        requests.post(webhook_url, json=webhookData)
    except requests.exceptions.RequestException as e:
        print(f"[External System] Failed to send webhook for {transaction_id}: {e}")


@app.route('/create_payment', methods = ['POST'])
def create_payment():
    data = request.get_json()

    # FIX: Standardized keys to snake_case and fixed typo 'trasctionId'
    transactionId = data['transaction_id']
    webhookUrl = data['webhook_url']
    userId = data['user_id']

    print(f"[External System] Payment creation request received for {userId}. Transaction ID: {transactionId}")

    threading.Thread(target=simulate_payment_processing, args=(transactionId, webhookUrl), daemon=True).start()

    paymentLink = f"http://payment-provider.com/pay?id={transactionId}"

    return jsonify({"payment_link": paymentLink}), 200 # FIX: snake_case

if __name__ == '__main__':
    print("[External System] Simulador de Pagamento iniciado na porta 5004")
    # FIX: Standardized port to 5004
    app.run(port=5004, host='0.0.0.0')