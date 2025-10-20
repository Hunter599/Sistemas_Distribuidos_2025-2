import base64
import hashlib
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

def sign_message(private_key_path, message: str) -> str:
    """Assina a mensagem com a chave privada (retorna assinatura base64)."""
    with open(private_key_path, "rb") as f:
        private_key = RSA.import_key(f.read())
    h = hashlib.sha256(message.encode()).digest()
    signature = pkcs1_15.new(private_key).sign(RSA._RSAobj.import_key(private_key.export_key()).publickey().hashAndSign(h)) if hasattr(RSA._RSAobj, 'hashAndSign') else pkcs1_15.new(private_key).sign(hashlib.sha256(message.encode()))
    return base64.b64encode(signature).decode()

def verify_signature(public_key_path, message: str, signature_b64: str) -> bool:
    """Verifica se a assinatura é válida."""
    with open(public_key_path, "rb") as f:
        public_key = RSA.import_key(f.read())
    h = hashlib.sha256(message.encode())
    signature = base64.b64decode(signature_b64)
    try:
        pkcs1_15.new(public_key).verify(h, signature)
        return True
    except (ValueError, TypeError):
        return False

