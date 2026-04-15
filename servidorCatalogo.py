import grpc
from concurrent import futures
import threading
import catalogo_pb2
import catalogo_pb2_grpc
import sys

# ESTOQUE INICIAL
catalogo_livros = {
    1: {"numero": 739, "nome": "Sistemas Distribuídos: Conceitos", "categoria": "computacao", "copias": 5},
    2: {"numero": 120, "nome": "Python Fluente",                   "categoria": "computacao", "copias": 10},
    3: {"numero": 456, "nome": "O Senhor dos Anéis",               "categoria": "ficcao",     "copias": 2},
    4: {"numero": 789, "nome": "Clean Code",                       "categoria": "computacao", "copias": 7},
    5: {"numero": 321, "nome": "1984",                             "categoria": "ficcao",     "copias": 15}
}

# pra não ocorrer condições de corrida quando vários clientes acessarem o catálogo ao mesmo tempo, aparece várias vezes no código
lock = threading.Lock() 

# FUNÇÃO AUXILIAR — busca livro pelo campo "numero"
# Percorre o dicionário procurando pelo campo 'numero'.
# Retorna os dados do livro ou None se não encontrar.
def buscar_por_numero(numero_item):
    
    for dados in catalogo_livros.values():
        if dados["numero"] == numero_item:
            return dados
    return None
 


# IMPLEMENTAÇÃO DO SERVIDOR DE CATÁLOGO

class ServidorCatalogo(catalogo_pb2_grpc.servidorCatalogoServicer): # tem que chamar catalogo_pb2_grpc.servidorCatalogoServicer pois essa é a 'função' vazia que estamos implementando e ela que vai ser chamada 

    def queryCategoria(self, request, context): # tem q ser sempre esses parâmetros
        resultado = catalogo_pb2.ListaLivros() # dentro do catalogo_pb2 tem um classe pra cada mensagem q a gnt defininu no .proto 

        with lock: 
            for dados in catalogo_livros.values():
                if dados["categoria"] == request.categoria:
                    livro = catalogo_pb2.LivroItem(
                        numeroItem=dados["numero"],
                        nome=dados["nome"]
                    )
                    resultado.livros.append(livro)

        return resultado

    def queryNumero(self, request, context):
        # O lock cobre toda a leitura dos campos: se liberarmos o lock após
        # buscar_por_numero e lermos dados["copias"] fora dele, uma thread
        # concorrente chamando update() pode modificar o valor entre os dois
        # acessos, produzindo uma leitura inconsistente (race condition).
        with lock:
            dados = buscar_por_numero(request.numeroItem)

            if dados is None:
                return catalogo_pb2.LivroInfo(error="Livro não encontrado")

            return catalogo_pb2.LivroInfo(
                numeroItem=dados["numero"],
                nome=dados["nome"],
                categoria=dados["categoria"],
                quantidade=dados["copias"],
                error=""
            )

    def update(self, request, context):
        with lock:
            dados = buscar_por_numero(request.numeroItem)

            if dados is None:
                return catalogo_pb2.UpdateResponse(success=False)

            dados["copias"] += request.qty

        return catalogo_pb2.UpdateResponse(success=True)



# INICIALIZAÇÃO DO SERVIDOR

def serve(porta):
    servidor = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    
    catalogo_pb2_grpc.add_servidorCatalogoServicer_to_server(
        ServidorCatalogo(), servidor
    )
    
    servidor.add_insecure_port(f"[::]:{porta}") # qualquer ip, um porta específica
    servidor.start()
    print(f"Servidor de Catálogo rodando na porta {porta}...")
    servidor.wait_for_termination()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Sintaxe correta: python servidorCatalogo.py <porta>")
        sys.exit(1)

    serve(sys.argv[1])