import grpc
from concurrent import futures
import threading
import catalogo_pb2
import catalogo_pb2_grpc
import sys

# Lock para evitar que duas compras simultâneas passem ao mesmo tempo
lock = threading.Lock()


# ============================================================
# IMPLEMENTAÇÃO DO SERVIDOR DE PEDIDOS
# ============================================================
class ServidorPedidos(catalogo_pb2_grpc.servidorPedidosServicer):

    def __init__(self, host_catalogo): # Recebe o endereço do servidor de catálogo e cria um canal de comunicação com ele host_catalogo = IP:porta do servidor de catálogo.
        
        canal = grpc.insecure_channel(host_catalogo)
        self.catalogo_stub = catalogo_pb2_grpc.servidorCatalogoStub(canal)

    def Buy(self, request, context): # Tenta comprar um livro. Consulta o catálogo para ver se tem estoque e, se tiver, decrementa.
        
        with lock:
            
            # Consulta o catálogo pelo número do item
            info = self.catalogo_stub.queryNumero(catalogo_pb2.numeroItemRequest(numeroItem=request.numeroItem))

            if info.error:
                return catalogo_pb2.CompraResponse(
                    success=False,
                    message=f"Erro: {info.error}"
                )

            if info.quantidade <= 0:
                return catalogo_pb2.CompraResponse(
                    success=False,
                    message=f"Livro '{info.nome}' está fora de estoque!"
                )

            self.catalogo_stub.update(
                catalogo_pb2.UpdateRequest(
                    numeroItem=request.numeroItem,
                    qty=-1
                )
            )

            return catalogo_pb2.CompraResponse(
                success=True,
                message=f"Compra do livro '{info.nome}' realizada com sucesso!"
            )


# INICIALIZAÇÃO DO SERVIDOR

def serve(porta, host_catalogo):
    servidor = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    catalogo_pb2_grpc.add_servidorPedidosServicer_to_server(
        ServidorPedidos(host_catalogo), servidor
    )

    servidor.add_insecure_port(f"[::]:{porta}")
    servidor.start()
    print(f"Servidor de Pedidos rodando na porta {porta}...")
    print(f"Conectado ao Catálogo em: {host_catalogo}")
    servidor.wait_for_termination()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Sintaxe correta: python servidorPedidos.py <porta> <host_catalogo>")
        print("Exemplo: python servidorPedidos.py 50052 localhost:50051")
        sys.exit(1)

    porta = sys.argv[1]
    host_catalogo = sys.argv[2]
    serve(porta, host_catalogo)