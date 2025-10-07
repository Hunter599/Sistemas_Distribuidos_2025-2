import threading
import time
import Pyro5.api
from collections import deque

# ----------------------
# Códigos ANSI de cores
# ----------------------
RESET = "\033[0m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"

@Pyro5.api.expose
@Pyro5.api.behavior(instance_mode="single")
class Peer:
    def __init__(self, name, access_time_limit=10.0, heartbeat_interval=1.0, heartbeat_timeout=3.0, reply_timeout=25.0):
        self.name = name
        self.clock = 0
        self.requesting = False
        self.request_timestamp = None
        self.deferred_replies = deque()
        self.replies_received = set()

        self.active_peers = {}
        self.active_lock = threading.Lock()

        self.last_heartbeat = {}
        self.hb_interval = heartbeat_interval
        self.hb_timeout = heartbeat_timeout

        self.access_time_limit = access_time_limit
        self.reply_timeout = reply_timeout

        self.in_cs = False
        self.cs_lock = threading.Lock()
        self.cs_timer = None

        self._stop = False
        self.threads = []
        self._start_background_threads()

    # ----------------------
    # Logger colorido
    # ----------------------
    def log(self, msg, level="info"):
        color = RESET
        if level == "request":
            color = BLUE
        elif level == "reply":
            color = GREEN
        elif level == "hb":
            color = YELLOW
        elif level == "error":
            color = RED
        elif level == "sc":
            color = CYAN
        print(f"{color}[{time.strftime('%H:%M:%S')}] [{self.name}] {msg}{RESET}")

    # ----------------------
    # Lamport clock
    # ----------------------
    def bump_clock(self, remote_ts=None):
        if remote_ts is None:
            self.clock += 1
        else:
            self.clock = max(self.clock, remote_ts) + 1
        return self.clock

    def update_peers_from_nameserver(self, ns):
        try:
            names = ns.list(prefix="")
            with self.active_lock:
                for nm, uri in names.items():
                    if nm == self.name or nm == "Pyro.NameServer":
                        continue
                    if nm not in self.active_peers:
                        self.log(f"Descoberto peer: {nm}", level="hb")
                        self.active_peers[nm] = uri
                        self.last_heartbeat[nm] = time.time()
                for nm in list(self.active_peers.keys()):
                    if nm not in names:
                        self.log(f"Peer removido do NS: {nm}", level="error")
                        self.active_peers.pop(nm, None)
                        self.last_heartbeat.pop(nm, None)
            return True
        except Exception as e:
            self.log(f"Falha ao consultar NS: {e}", level="error")
            return False

    # ----------------------
    # Ricart & Agrawala
    # ----------------------
    def request_cs(self):
        with self.cs_lock:
            if self.in_cs:
                self.log("Já está na seção crítica.", level="error")
                return False
            self.bump_clock()
            self.request_timestamp = self.clock
            self.requesting = True
            with self.active_lock:
                targets = list(self.active_peers.keys())
            self.replies_received = set()
            self.log(f"Solicitando SC (ts={self.request_timestamp}) para {targets}", level="request")

            for peer_name in targets:
                uri = self.active_peers.get(peer_name)
                if not uri:
                    continue
                try:
                    with Pyro5.api.Proxy(uri) as proxy:
                        proxy._pyroTimeout = self.reply_timeout
                        proxy.receive_request(self.name, self.request_timestamp)
                except Exception as e:
                    self.log(f"Falha ao enviar REQUEST para {peer_name}: {e}", level="error")

            deadline = time.time() + self.reply_timeout
            while time.time() < deadline:
                with self.active_lock:
                    needed = set(self.active_peers.keys()) - self.replies_received
                if not needed:
                    break
                time.sleep(0.05)

            with self.active_lock:
                still_needed = set(self.active_peers.keys()) - self.replies_received
            
            if still_needed:
                self.log(f"TIMEOUT! Não recebeu permissão de {still_needed}. Removendo-os.", level="error")
                with self.active_lock:
                    for peer_name in still_needed:
                        self.active_peers.pop(peer_name, None)
                        self.last_heartbeat.pop(peer_name, None)
                self.requesting = False
                return False

            self.in_cs = True
            self.log(">>> Entrou na SEÇÃO CRÍTICA <<<", level="sc")
            self.cs_timer = threading.Timer(self.access_time_limit, self._auto_release_cs)
            self.cs_timer.start()
            return True

    def release_cs(self):
        with self.cs_lock:
            if not self.in_cs:
                self.log("Não está na SC.", level="error")
                return
            self.in_cs = False
            self.requesting = False
            self.request_timestamp = None
            if self.cs_timer:
                self.cs_timer.cancel()
                self.cs_timer = None
            self.log("<<< Saiu da SEÇÃO CRÍTICA >>>", level="sc")
            while self.deferred_replies:
                peer_name = self.deferred_replies.popleft()
                uri = self.active_peers.get(peer_name)
                if uri:
                    try:
                        with Pyro5.api.Proxy(uri) as proxy:
                            proxy.receive_reply(self.name)
                            self.log(f"Enviou REPLY (adiado) para {peer_name}", level="reply")
                    except:
                        self.log(f"Falha enviando REPLY para {peer_name}", level="error")

    def _auto_release_cs(self):
        self.log(f"Tempo limite {self.access_time_limit}s atingido. Liberando SC.", level="error")
        self.release_cs()

    def receive_request(self, peer_name, timestamp):
        self.bump_clock(remote_ts=timestamp)
        self.log(f"Recebeu REQUEST de {peer_name} (ts={timestamp})", level="request")

        must_defer = False
        with self.cs_lock:
            if self.in_cs:
                must_defer = True
            elif self.requesting:
                if (timestamp, peer_name) >= (self.request_timestamp, self.name):
                    must_defer = True

        if must_defer:
            self.log(f"Adiar REPLY para {peer_name}", level="error")
            self.deferred_replies.append(peer_name)

            if self.in_cs:
                uri = self.active_peers.get(peer_name)
                if uri:
                    try:
                        with Pyro5.api.Proxy(uri) as proxy:
                            proxy._pyroOneway.add("receive_in_cs_notification")
                            proxy.receive_in_cs_notification(self.name)
                    except Exception as e:
                        self.log(f"Falha ao notificar {peer_name}: {e}", level="error")

        else:
            last_hb = self.last_heartbeat.get(peer_name, 0)
            if time.time() - last_hb > self.hb_timeout:
                self.log(f"Ignorando REQUEST do peer inativo {peer_name}", level="error")
                return True
            
            uri = self.active_peers.get(peer_name)
            if uri:
                try:
                    with Pyro5.api.Proxy(uri) as proxy:
                        proxy.receive_reply(self.name)
                        self.log(f"Enviou REPLY imediato para {peer_name}", level="reply")
                except Exception as e:
                    self.log(f"Falha enviando REPLY para {peer_name}: {e}", level="error")
        return True

    def receive_reply(self, peer_name):
        self.bump_clock()
        self.log(f"Recebeu REPLY de {peer_name}", level="reply")
        with self.active_lock:
            self.replies_received.add(peer_name)
        return True
    
    def receive_in_cs_notification(self, holder_name):
        self.log(f"Acesso negado. {holder_name} está atualmente na Seção Crítica.", level="error")
        return True

    # ----------------------
    # Heartbeat
    # ----------------------
    def send_heartbeat(self):
        now = time.time()
        with self.active_lock:
            for peer_name, uri in list(self.active_peers.items()):
                last = self.last_heartbeat.get(peer_name, 0)
                if now - last > self.hb_timeout:
                    self.log(f"Peer {peer_name} não responde há {self.hb_timeout}s. Removendo da lista.", level="error")
                    self.active_peers.pop(peer_name, None)
                    self.last_heartbeat.pop(peer_name, None)
                else:
                    try:
                        with Pyro5.api.Proxy(uri) as proxy:
                            proxy.heartbeat(self.name)
                        # self.log(f"Enviou heartbeat para {peer_name}", level="hb")
                    except:
                        pass

    def heartbeat(self, from_peer):
        self.last_heartbeat[from_peer] = time.time()
        # self.log(f"Heartbeat recebido de {from_peer}", level="hb")
        return True

    # ----------------------
    # Threads auxiliares
    # ----------------------
    def _heartbeat_thread(self):
        while not self._stop:
            self.send_heartbeat()
            time.sleep(self.hb_interval)

    def _start_background_threads(self):
        t = threading.Thread(target=self._heartbeat_thread, daemon=True)
        t.start()
        self.threads.append(t)

    def shutdown(self):
        self._stop = True
        if self.cs_timer:
            self.cs_timer.cancel()
        self.log("Desligando peer.", level="error")
        return True

    def list_active_peers(self):
        with self.active_lock:
            return dict(self.active_peers)

    def info(self):
        with self.active_lock:
            return {
                "name": self.name,
                "clock": self.clock,
                "in_cs": self.in_cs,
                "active_peers": list(self.active_peers.keys())
            }