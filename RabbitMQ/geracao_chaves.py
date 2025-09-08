import os
from Crypto.PublicKey import RSA

# Número de clientes
num_clients = 5

# Diretório raiz onde as chaves vão ser salvas
base_dir = "clientes"

for i in range(1, num_clients + 1):
    client_dir = os.path.join(base_dir, f"cliente{i}")
    private_dir = os.path.join(client_dir, "private")
    
    # Criar diretórios (se não existirem)
    os.makedirs(private_dir, exist_ok=True)
    
    # Gerar chave RSA
    key = RSA.generate(2048)
    
    # Salvar chave privada
    private_key = key.export_key()
    with open(os.path.join(private_dir, "private.pem"), "wb") as f:
        f.write(private_key)
    
    # Salvar chave pública
    public_key = key.publickey().export_key()
    with open(os.path.join(client_dir, "receiver.pem"), "wb") as f:
        f.write(public_key)
    
    print(f"Chaves geradas para {client_dir}")
