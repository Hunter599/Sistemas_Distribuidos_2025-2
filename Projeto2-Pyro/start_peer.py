# start_peer.py
# Uso: python start_peer.py <PeerName> <port> [nameserver_host] [nameserver_port]
import sys
import threading
import time
import Pyro5.api
from nameserver_helper import get_or_start_nameserver
from peer import Peer

def main():
    if len(sys.argv) < 3:
        print("Uso: python start_peer.py <PeerName> <port> [ns_host] [ns_port]")
        sys.exit(1)
    name = sys.argv[1]
    port = int(sys.argv[2])
    ns_host = "localhost"
    ns_port = 9090
    if len(sys.argv) >= 4:
        ns_host = sys.argv[3]
    if len(sys.argv) >= 5:
        ns_port = int(sys.argv[4])

    # Localizar ou criar NameServer
    ns = get_or_start_nameserver(host=ns_host, port=ns_port)

    # cria a instância peer
    p = Peer(name=name)

    # cria daemon Pyro em porta especificada
    daemon = Pyro5.api.Daemon(host="localhost", port=port)
    uri = daemon.register(p)
    try:
        # registra no nameserver (se já existir um registro com mesmo nome, sobrescreve)
        ns.register(name, uri)
        print(f"[start_peer] Registrado {name} no NameServer com URI {uri}")
    except Exception as e:
        print("[start_peer] Erro ao registrar no NameServer:", e)
        # tenta remover registro antigo e registrar novamente
        try:
            ns.remove(name)
            ns.register(name, uri)
            print(f"[start_peer] Registrado {name} após remover registro antigo.")
        except Exception as e2:
            print("[start_peer] Falha ao registrar:", e2)
            daemon.shutdown()
            sys.exit(1)

    # inicia thread para atualizar peers periodicamente consultando nameserver
    def discovery_loop():
    	while True:
        	try:
            		# cada thread precisa criar seu proxy pro NameServer
            		local_ns = Pyro5.api.locate_ns(host=ns_host, port=ns_port)
            		p.update_peers_from_nameserver(local_ns)
        	except Exception as ex:
            		print("[discovery_loop] erro:", ex)
        	time.sleep(1.0)
        
    t = threading.Thread(target=discovery_loop, daemon=True)
    t.start()

    print(f"[start_peer] {name} rodando em {uri}. CTRL+C para encerrar.")
    try:
        daemon.requestLoop()
    except KeyboardInterrupt:
        print("[start_peer] KeyboardInterrupt, encerrando.")
    finally:
        try:
            ns.remove(name)
            print(f"[start_peer] Removido {name} do nameserver.")
        except Exception:
            pass
        try:
            p.shutdown()
        except:
            pass
        daemon.shutdown()

if __name__ == "__main__":
    main()

