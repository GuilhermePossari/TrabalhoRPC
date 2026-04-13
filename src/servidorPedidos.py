# ./servidorPedidos.py "ip do servidorCatalogo"

import livro

# verifica se o item está em estoque consultando o servidor de catálogo e, em seguida, decrementa o número de itens em estoque em um. 
# O pedido pode falhar se o item estiver fora de estoque.
def buy(item_number): 
