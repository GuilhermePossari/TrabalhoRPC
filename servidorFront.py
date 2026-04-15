import grpc
from concurrent import futures
import catalogo_pb2
import catalogo_pb2_grpc
import sys


# IMPLEMENTAÇÃO DO SERVIDOR FRONT-END

class ServidorFront(catalogo_pb2_grpc.servidorFrontServicer):

    def __init__(self, host_catalogo, host_pedidos): # Recebe os endereços do catálogo e pedidos e cria stubs (controles remotos) para se comunicar com eles.

        # Stub para falar com o catálogo
        canal_catalogo = grpc.insecure_channel(host_catalogo)
        self.catalogo_stub = catalogo_pb2_grpc.servidorCatalogoStub(canal_catalogo)

        # Stub para falar com o servidor de pedidos
        canal_pedidos = grpc.insecure_channel(host_pedidos)
        self.pedidos_stub = catalogo_pb2_grpc.servidorPedidosStub(canal_pedidos)

    def Search(self, request, context):
        return self.catalogo_stub.queryCategoria(catalogo_pb2.CategoriaRequest(categoria=request.categoria))

    def Lookup(self, request, context):
        return self.catalogo_stub.queryNumero(catalogo_pb2.numeroItemRequest(numeroItem=request.numeroItem))

    def Buy(self, request, context):
        return self.pedidos_stub.Buy(catalogo_pb2.numeroItemRequest(numeroItem=request.numeroItem))


# INICIALIZAÇÃO DO SERVIDOR

def serve(porta, host_catalogo, host_pedidos):
    servidor = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    catalogo_pb2_grpc.add_servidorFrontServicer_to_server(
        ServidorFront(host_catalogo, host_pedidos), servidor
    )

    servidor.add_insecure_port(f"[::]:{porta}")
    servidor.start()
    print(f"Servidor Front-End rodando na porta {porta}...")
    print(f"Conectado ao Catálogo em: {host_catalogo}")
    print(f"Conectado aos Pedidos em: {host_pedidos}")
    servidor.wait_for_termination()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Sintaxe correta: python servidorFront.py <porta> <host_catalogo> <host_pedidos>")
        print("Exemplo: python servidorFront.py 50050 localhost:50051 localhost:50052")
        sys.exit(1)

    porta = sys.argv[1]
    host_catalogo = sys.argv[2]
    host_pedidos = sys.argv[3]
    serve(porta, host_catalogo, host_pedidos)