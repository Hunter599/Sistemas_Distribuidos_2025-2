# nameserver_helper.py
# Helper para localizar ou criar um NameServer Pyro5 (evita múltiplas instâncias).
import threading
import time
import Pyro5.api
import Pyro5.nameserver

def get_or_start_nameserver(host="localhost", port=9090, try_connect_timeout=2.0):
    """
    Tenta localizar um NameServer. Se não existir, tenta iniciar um em thread.
    Retorna o proxy para o nameserver.
    """
    try:
        ns = Pyro5.api.locate_ns(host=host, port=port)
        print("[NameServer] Encontrado NameServer existente.")
        return ns
    except Exception as e:
        print("[NameServer] NameServer não encontrado, tentando iniciar um novo...")

    # Start NS loop in a background thread
    def ns_thread():
        try:
            Pyro5.nameserver.start_ns_loop(host=host, port=port)
        except Exception as ex:
            print("[NameServer thread] falha ao iniciar nameserver:", ex)

    t = threading.Thread(target=ns_thread, daemon=True)
    t.start()

    # esperar um pouco para o ns subir
    deadline = time.time() + try_connect_timeout
    while time.time() < deadline:
        try:
            ns = Pyro5.api.locate_ns(host=host, port=port)
            print("[NameServer] NameServer iniciado e localizado.")
            return ns
        except Exception:
            time.sleep(0.2)

    raise RuntimeError("Não foi possível localizar ou iniciar o Pyro NameServer.")

