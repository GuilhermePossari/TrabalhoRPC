# ./servidorCatalogo.py

import livro 

# catalogo exemplo
catalogo_livros = {
    1: {"numero": 739, "nome": "Sistemas Distribuídos: Conceitos", "categoria": "computacao", "copias": 5},
    2: {"numero": 120, "nome": "Python Fluente", "categoria": "computacao", "copias": 10},
    3: {"numero": 456, "nome": "O Senhor dos Anéis", "categoria": "ficcao", "copias": 2},
    4: {"numero": 789, "nome": "Clean Code", "categoria": "computacao", "copias": 7},
    5: {"numero": 321, "nome": "1984", "categoria": "ficcao", "copias": 15}
}

# consulta detalhes do inventário atual (por tópico ou por número do item).
def query(arg):
    
    if isinstance(arg, int):
        if arg in catalogo_livros:
            return {arg: catalogo_livros[arg]}
        else:
            return {"erro": "Livro não encontrado pelo ID."}
    
    elif isinstance(arg, str):
        resultados = {}
    
        for n, detalhes in catalogo_livros.items():
            if detalhes["categoria"].lower() == arg.lower():
                resultados[n] = detalhes
        
        if resultados:
            return resultados
        else:
            return {"erro": "Nenhum livro encontrado para este tópico."}
    
    return {"erro": "Argumento de busca inválido."}

# atualiza o inventário atual de um item adicionando a quantidade especificada (positiva ou negativa).
def update(item_number, qty):
    
    if item_number in catalogo_livros:
        estoque_atual = catalogo_livros[item_number]["copias"]
        novo_estoque = estoque_atual + qty
        
        if novo_estoque >= 0:
            catalogo_livros[item_number]["copias"] = novo_estoque
            return {"sucesso": True, "novo_estoque": novo_estoque}
        else:
            return {"sucesso": False, "erro": "Estoque insuficiente para subtrair essa quantidade."}
    else:
        return {"sucesso": False, "erro": "Item não existe no catálogo."}