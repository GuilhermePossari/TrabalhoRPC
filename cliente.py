import grpc
import sys
import time
import catalogo_pb2
import catalogo_pb2_grpc


def conectar(host_front):
    canal = grpc.insecure_channel(host_front)
    stub = catalogo_pb2_grpc.servidorFrontStub(canal)
    return stub


def search(stub, topico):
    inicio = time.time()
    resposta = stub.Search(catalogo_pb2.CategoriaRequest(categoria=topico))
    elapsed = time.time() - inicio

    if not resposta.livros:
        print(f"  Nenhum livro encontrado para o tópico '{topico}'.")
    else:
        print(f"  Livros no tópico '{topico}':")
        for livro in resposta.livros:
            print(f"    [{livro.numeroItem}] {livro.nome}")
    print(f"  Tempo de resposta: {elapsed*1000:.2f} ms")
    return elapsed


def lookup(stub, numero_item):
    inicio = time.time()
    resposta = stub.Lookup(catalogo_pb2.numeroItemRequest(numeroItem=numero_item))
    elapsed = time.time() - inicio

    if resposta.error:
        print(f"  Erro: {resposta.error}")
    else:
        print(f"  [{resposta.numeroItem}] {resposta.nome}")
        print(f"  Categoria : {resposta.categoria}")
        print(f"  Em estoque: {resposta.quantidade}")
    print(f"  Tempo de resposta: {elapsed*1000:.2f} ms")
    return elapsed


def buy(stub, numero_item):
    inicio = time.time()
    resposta = stub.Buy(catalogo_pb2.numeroItemRequest(numeroItem=numero_item))
    elapsed = time.time() - inicio

    if resposta.success:
        print(f"  Sucesso: {resposta.message}")
    else:
        print(f"  Falha: {resposta.message}")
    print(f"  Tempo de resposta: {elapsed*1000:.2f} ms")
    return elapsed


def menu(stub):
    opcoes = (
        "\nOperações disponíveis:\n"
        "  1 - search <topico>\n"
        "  2 - lookup <numero_item>\n"
        "  3 - buy    <numero_item>\n"
        "  0 - sair\n"
    )
    print(opcoes)

    while True:
        entrada = input(">> ").strip()
        if not entrada:
            continue

        partes = entrada.split(maxsplit=1)
        cmd = partes[0].lower()

        if cmd in ("0", "sair", "exit", "quit"):
            print("Encerrando cliente.")
            break

        elif cmd in ("1", "search"):
            if len(partes) < 2:
                print("  Uso: search <topico>")
                continue
            search(stub, partes[1])

        elif cmd in ("2", "lookup"):
            if len(partes) < 2:
                print("  Uso: lookup <numero_item>")
                continue
            try:
                lookup(stub, int(partes[1]))
            except ValueError:
                print("  numero_item deve ser um inteiro.")

        elif cmd in ("3", "buy"):
            if len(partes) < 2:
                print("  Uso: buy <numero_item>")
                continue
            try:
                buy(stub, int(partes[1]))
            except ValueError:
                print("  numero_item deve ser um inteiro.")

        else:
            print(f"  Comando desconhecido: '{cmd}'")
            print(opcoes)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python cliente.py <host_front>")
        print("Exemplo: python cliente.py localhost:50050")
        sys.exit(1)

    host_front = sys.argv[1]
    stub = conectar(host_front)
    print(f"Cliente conectado ao servidor front-end em {host_front}")
    menu(stub)
