import time
import threading
import requests
import random
from flask import Flask, request, jsonify

app = Flask(__name__)

def simulate_payment_processing(transactionId, webhookURL):

    print(f"[External System] Processing transaction {transactionId}")

    time.sleep(random.ranint(5, 10))

    status = random.choice(["aprovado", "recusado"])

    webhookData = {
        "transactionId": transactionId,
        "status": status,
        "value": 123
    }

    try:
        print(f"[External System] Sending webhook for {transactionId} to {webhookData}")
        requests.post(webhookURL, json=webhookData)
    except requests.exceptions.RequestException as e:
        print(f"[External System] Failed to send webhook for {transactionId}: {e}")


@app.route('/create_payment', methods = ['POST'])
def create_payment():
    data = request.get_json()

    transactionId = data['trasctionId']
    webhookUrl = data['webhookUrl']
    userId = data['userId']

    print(f"[External System] Payment creatin request received for {userId}. Transaction ID: {transactionId}")

    threading.Thread(target=simulate_payment_processing, args=(transactionId, webhookUrl), daemon=True).start()

    paymentLink = f"http://payment-provider.com/pay?id={transactionId}"

    return jsonify({"paymentLink": paymentLink}), 200

if __name__ == '__main__':
    print("[External System] Simulador de Pagamento iniciado")
    app.run(port=5006, host='0.0.0.0')