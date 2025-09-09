# Install required library first: pip install diagrams

from diagrams import Diagram, Cluster, Edge
from diagrams.onprem.queue import Rabbitmq
from diagrams.generic.device import Mobile
from diagrams.onprem.compute import Server

with Diagram("Auction System Architecture", show=False, direction="LR"):

    # 1. Define Components
    client_app = Mobile("Cliente Application")

    with Cluster("Backend Services"):
        # Use the corrected class 'Server' instead of 'Service'
        ms_leilao = Server("MS Leilão\n(Scheduler)")
        ms_lance = Server("MS Lance\n(Validation Engine)")
        ms_notificacao = Server("MS Notificação\n(Router)")
        queue = Rabbitmq("Message Broker")

    # 2. Define Data Flows

    # Flow: Auction Lifecycle (MS Leilão -> MS Lance)
    ms_leilao >> Edge(label="leilao_iniciado / leilao_finalizado", color="blue") >> queue >> ms_lance

    # Flow: Bid Submission (Client -> MS Lance)
    client_app >> Edge(label="lance_realizado", color="red", style="bold") >> queue >> ms_lance

    # Flow: Notifications (MS Lance -> MS Notificação -> Client)
    ms_lance >> Edge(label="lance_validado / leilao_vencedor", color="green") >> queue >> ms_notificacao
    ms_notificacao >> Edge(label="leilao_{id} (Dynamic Routing)", color="green", style="dashed") >> client_app