"""
Script de testes de desempenho para a Minibib.com.

Uso:
    python teste_desempenho.py <host_front> [num_clientes] [num_requisicoes]

Exemplos:
    python teste_desempenho.py localhost:50050
    python teste_desempenho.py localhost:50050 5 20
"""

import grpc
import sys
import time
import threading
import statistics
import catalogo_pb2
import catalogo_pb2_grpc

NUM_CLIENTES_PADRAO = 5
NUM_REQUISICOES_PADRAO = 20

# Tópico e item usados nos testes
TOPICO_TESTE = "computacao"
ITEM_TESTE = 739


def criar_stub(host_front):
    canal = grpc.insecure_channel(host_front)
    return catalogo_pb2_grpc.servidorFrontStub(canal)


def medir_search(stub, topico=TOPICO_TESTE):
    inicio = time.time()
    stub.Search(catalogo_pb2.CategoriaRequest(categoria=topico))
    return time.time() - inicio


def medir_buy(stub, numero_item=ITEM_TESTE):
    inicio = time.time()
    stub.Buy(catalogo_pb2.numeroItemRequest(numeroItem=numero_item))
    return time.time() - inicio


# ── Teste 1: cliente único ────────────────────────────────────────────────────

def teste_cliente_unico(host_front, n=NUM_REQUISICOES_PADRAO):
    print(f"\n=== Teste 1: cliente único ({n} requisições cada) ===")
    stub = criar_stub(host_front)

    tempos_search = [medir_search(stub) for _ in range(n)]
    tempos_buy    = [medir_buy(stub)    for _ in range(n)]

    def stats(label, tempos):
        med  = statistics.mean(tempos) * 1000
        mn   = min(tempos) * 1000
        mx   = max(tempos) * 1000
        stdev = statistics.stdev(tempos) * 1000 if len(tempos) > 1 else 0
        print(f"  {label}: média={med:.2f}ms  min={mn:.2f}ms  max={mx:.2f}ms  desvpad={stdev:.2f}ms")
        return med, mn, mx, stdev

    s = stats("search", tempos_search)
    b = stats("buy",    tempos_buy)
    return s, b


# ── Teste 2: múltiplos clientes simultâneos ───────────────────────────────────

def _worker_search(host_front, n, resultados, idx):
    stub = criar_stub(host_front)
    tempos = [medir_search(stub) for _ in range(n)]
    resultados[idx] = tempos


def _worker_buy(host_front, n, resultados, idx):
    stub = criar_stub(host_front)
    tempos = [medir_buy(stub) for _ in range(n)]
    resultados[idx] = tempos


def teste_multicliente(host_front, num_clientes=NUM_CLIENTES_PADRAO, n=NUM_REQUISICOES_PADRAO):
    print(f"\n=== Teste 2: {num_clientes} clientes simultâneos ({n} requisições cada) ===")

    for operacao, worker in [("search", _worker_search), ("buy", _worker_buy)]:
        resultados = [None] * num_clientes
        threads = [
            threading.Thread(target=worker, args=(host_front, n, resultados, i))
            for i in range(num_clientes)
        ]

        inicio_global = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        tempo_total = time.time() - inicio_global

        todos = [t for lista in resultados for t in lista]
        med   = statistics.mean(todos) * 1000
        mn    = min(todos) * 1000
        mx    = max(todos) * 1000
        stdev = statistics.stdev(todos) * 1000 if len(todos) > 1 else 0
        total_req = num_clientes * n
        throughput = total_req / tempo_total

        print(f"  {operacao}: média={med:.2f}ms  min={mn:.2f}ms  max={mx:.2f}ms  "
              f"desvpad={stdev:.2f}ms  throughput={throughput:.1f} req/s")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    host_front    = sys.argv[1]
    num_clientes  = int(sys.argv[2]) if len(sys.argv) > 2 else NUM_CLIENTES_PADRAO
    num_requisicoes = int(sys.argv[3]) if len(sys.argv) > 3 else NUM_REQUISICOES_PADRAO

    teste_cliente_unico(host_front, num_requisicoes)
    teste_multicliente(host_front, num_clientes, num_requisicoes)
