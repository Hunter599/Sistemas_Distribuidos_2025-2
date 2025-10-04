# cli.py
# Interface simples para interagir com um peer já em execução.
# Uso: python cli.py <PeerName> <peer_uri>  OR para procurar via nameserver: python cli.py <PeerName> --ns
import sys
import time
import Pyro5.api

def usage():
    print("Uso:")
    print("  python cli.py <PeerName> <peer_uri>")
    print("  python cli.py <PeerName> --ns [ns_host ns_port]  # procura URI no nameserver")
    sys.exit(1)

def main():
    if len(sys.argv) < 3:
        usage()
    name = sys.argv[1]
    if sys.argv[2] == "--ns":
        ns_host = "localhost"
        ns_port = 9090
        if len(sys.argv) >= 5:
            ns_host = sys.argv[3]
            ns_port = int(sys.argv[4])
        ns = Pyro5.api.locate_ns(host=ns_host, port=ns_port)
        info = ns.lookup(name)
        uri = info
    else:
        uri = sys.argv[2]

    print(f"Conectando a {name} em {uri}")
    try:
        proxy = Pyro5.api.Proxy(uri)
    except Exception as e:
        print("Falha ao criar proxy:", e)
        sys.exit(1)

    def print_menu():
        print("\nComandos:")
        print(" 1 - request_cs (pedir seção crítica)")
        print(" 2 - release_cs  (liberar seção crítica)")
        print(" 3 - list_peers")
        print(" 4 - info")
        print(" 5 - shutdown peer (desregistrar e desligar)")
        print(" q - sair CLI")

    while True:
        print_menu()
        cmd = input("Escolha: ").strip()
        if cmd == "1":
            try:
                ok = proxy.request_cs()
                print("request_cs ->", ok)
            except Exception as e:
                print("Erro calling request_cs:", e)
        elif cmd == "2":
            try:
                proxy.release_cs()
                print("release_cs enviado.")
            except Exception as e:
                print("Erro calling release_cs:", e)
        elif cmd == "3":
            try:
                peers = proxy.list_active_peers()
                print("Active peers:", peers)
            except Exception as e:
                print("Erro calling list_active_peers:", e)
        elif cmd == "4":
            try:
                info = proxy.info()
                print("Info:", info)
            except Exception as e:
                print("Erro calling info:", e)
        elif cmd == "5":
            try:
                proxy.shutdown()
                print("Shutdown solicitado ao peer (ele seguirá desligando).")
            except Exception as e:
                print("Erro calling shutdown:", e)
        elif cmd.lower() == "q":
            print("Saindo CLI.")
            break
        else:
            print("Comando desconhecido.")

if __name__ == "__main__":
    main()

