# Minibib.com — Livraria Remota com gRPC

Projeto de Sistemas Distribuídos — Guilherme Possari e Rafael Lançoni Santos  
Implementação de uma livraria online em múltiplas camadas usando gRPC (RPC).

---

## Como executar

### Pré-requisitos

```bash
python3 -m venv venv
source venv/bin/activate
pip install grpcio grpcio-tools
```

### Ordem de inicialização

Os servidores precisam ser iniciados nessa ordem, porque cada um depende do anterior:

```bash
# 1. Servidor de Catálogo (não depende de nenhum outro)
python3 servidorCatalogo.py <porta>
# Exemplo:
python3 servidorCatalogo.py 50051

# 2. Servidor de Pedidos (depende do Catálogo)
python3 servidorPedidos.py <porta> <host_catalogo>
# Exemplo:
python3 servidorPedidos.py 50052 localhost:50051

# 3. Servidor Front-End (depende do Catálogo e dos Pedidos)
python3 servidorFront.py <porta> <host_catalogo> <host_pedidos>
# Exemplo:
python3 servidorFront.py 50050 localhost:50051 localhost:50052

# 4. Cliente
python3 cliente.py <host_front>
# Exemplo:
python3 cliente.py localhost:50050
```

### Testes de desempenho

```bash
python3 teste_desempenho.py <host_front> [num_clientes] [num_requisicoes]
# Exemplo:
python3 teste_desempenho.py localhost:50050 5 30
```

> **Importante:** o script usa o item 739 com estoque inicial de 5 cópias para as requisições `buy`. Com muitas requisições o estoque zera, e as compras seguintes retornam erro imediatamente, então, como essas respostas de erro chegam mais rápido do que as de sucesso, a média fica distorcida. Por isso é necessário reiniciar o servidor de catálogo entre execuções para restaurar o estoque.

---

## 1. Decisões de Projeto

### Estrutura de dados do catálogo

O catálogo é mantido em memória como um dicionário Python (`dict`), onde cada entrada tem os campos `numero`, `nome`, `categoria` e `copias`.

Achamos que essa escolha faz sentido porque o enunciado mandado pelo professor permite manter o catálogo em memória, então não precisamos de banco de dados nem de arquivo em disco. O dicionário é simples de usar e suficiente para o tamanho do problema. Vale mencionar que ao reiniciar o servidor de catálogo, o estoque volta ao estado inicial.

### Design de concorrência

**Servidor de Catálogo:** usamos um `threading.Lock` para proteger as operações de leitura e escrita no dicionário. Assim, se dois clientes tentarem acessar o catálogo ao mesmo tempo, um espera o outro terminar antes de continuar.

**Servidor de Pedidos:** o mesmo tipo de lock protege o ciclo inteiro de "verificar estoque → decrementar", impedindo que dois pedidos simultâneos da última cópia de um livro sejam ambos aprovados.

**Servidor Front-End:** como ele só repassa as chamadas para os outros servidores e não guarda nenhum estado próprio, não precisamos de lock aqui.

**Thread pool:** os três servidores foram configurados com `futures.ThreadPoolExecutor(max_workers=10)`, o que permite até 10 requisições rodando ao mesmo tempo em cada um.

### Comunicação entre servidores

Toda a comunicação é feita via gRPC com canais sem criptografia (`insecure_channel`) Os endereços de cada servidor são passados por linha de comando, então é fácil rodar cada componente em uma máquina diferente sem precisar alterar o código.

### Separação de responsabilidades

O servidor de pedidos não guarda nenhuma informação de estoque, tudo fica no catálogo. O que o servidor de pedidos faz é apenas coordenar a compra, ou seja, consulta o catálogo, verifica se tem estoque e pede a atualização. Dessa forma, o catálogo é sempre a fonte de verdade sobre o que tem ou não disponível.

### Por que duas RPCs no catálogo em vez de uma?

O enunciado descreve uma operação `query(arg)` que aceita tanto tópico quanto número de item. Em vez de implementar isso com um único procedimento que recebe um argumento genérico, optamos por duas RPCs separadas, `queryCategoria` e `queryNumero`, cada uma com sua própria mensagem tipada no `.proto`.

Isso é mais natural no gRPC, onde o recomendado é que cada operação tenha tipos bem definidos. O resultado é um código mais claro, já que fica explícito o que cada função espera receber, sem precisar de campos opcionais ou condicionais para distinguir os dois casos.

---

## 2. Resultados Experimentais

### Métricas escolhidas e por que cada uma importa

Optamos por medir três coisas em cada teste:

**Tempo de resposta (latência)** : é o tempo que passa desde o momento em que o cliente envia a requisição até receber a resposta. Essa é a métrica mais direta para avaliar se o sistema é rápido ou lento do ponto de vista de quem está usando. Junto com a média, registramos também o mínimo, o máximo e o desvio padrão para entender se os tempos são consistentes ou se variam muito entre uma requisição e outra.

**Desvio padrão** : mede o quanto os tempos individuais se afastam da média. Um desvio padrão baixo significa que o sistema se comporta de forma previsível, ou seja, quase todas as requisições demoram parecido. Um desvio padrão alto indica instabilidade, ou seja, algumas requisições são muito mais lentas que outras. Isso é importante especialmente no Wi-Fi, onde a rede pode introduzir variações.

**Throughput** :vmede quantas requisições o sistema consegue processar por segundo quando há vários clientes ao mesmo tempo. Enquanto a latência mostra o tempo de uma requisição individual, o throughput mostra a capacidade total do sistema sob carga. Medimos isso apenas no teste com múltiplos clientes, porque com um cliente só não há concorrência para testar.

Para os testes usamos **30 requisições por cliente** e **5 clientes simultâneos**. Escolhemos 30 requisições porque é um número grande o suficiente para a média ser representativa e pequeno o suficiente para terminar rápido. Já os 5 clientes simultâneos foram escolhidos para observar o comportamento sob concorrência real sem exigir uma máquina muito potente.

Os testes de cliente único servem como referência, já que eles mostram o tempo sem concorrência. Os testes com 5 clientes mostram o que acontece quando várias pessoas usam o sistema ao mesmo tempo.

### Especificações das máquinas

**Máquina A (servidores)**
- Modelo: Lenovo IdeaPad 3 15ITL6
- Processador: Intel Core i7-1165G7 (11ª geração, 8 núcleos)
- Memória: 12 GB RAM
- Sistema: Ubuntu 24.04.4 LTS

**Máquina B (cliente)**
- Modelo: Dell
- Processador: Intel Core i7-8565U @ 1.80 GHz
- Memória: 8 GB RAM
- Sistema: Windows 11 com WSL2

Os testes entre máquinas foram feitos via rede Wi-Fi da universidade (eduroam), de dentro do Departamento de Computação, com os servidores todos na Máquina A e o cliente na Máquina B.

---

### Testes na mesma máquina (loopback)

Todos os servidores e o cliente rodando no mesmo computador, sem tráfego de rede real.

**Cliente único — 30 requisições**

| Operação | Média   | Mínimo  | Máximo  | Desvio padrão |
|----------|---------|---------|---------|---------------|
| `search` | 0.73 ms | 0.58 ms | 2.76 ms | 0.39 ms       |
| `buy`    | 0.98 ms | 0.79 ms | 2.95 ms | 0.40 ms       |

O `buy` é um pouco mais lento que o `search` porque envolve mais passos internos: o front-end chama o servidor de pedidos, que por sua vez faz duas chamadas ao catálogo (uma para verificar o estoque e outra para decrementar). Já o `search` vai direto do front-end ao catálogo e volta.

**5 clientes simultâneos — 30 requisições cada (150 no total)**

| Operação | Média   | Mínimo  | Máximo  | Desvio padrão | Throughput   |
|----------|---------|---------|---------|---------------|--------------|
| `search` | 1.60 ms | 1.09 ms | 2.57 ms | 0.24 ms       | 3035 req/s   |
| `buy`    | 2.21 ms | 1.81 ms | 4.37 ms | 0.48 ms       | 2220 req/s   |

Com 5 clientes ao mesmo tempo a latência média aumentou cerca de 2×, o que faz sentido, visto que os clientes competem pelo lock do catálogo e do servidor de pedidos, então às vezes um precisa esperar o outro terminar.

---

### Testes entre máquinas (Wi-Fi)

Os testes foram repetidos 5 vezes para ter resultados mais confiáveis. Abaixo os dados de cada execução:

| Exec | Clientes  | Operação | Média    | Mínimo  | Máximo   | Desvpad  | Throughput   |
|------|-----------|----------|----------|---------|----------|----------|--------------|
| 1    | único     | search   | 15.73 ms | 9.03 ms | 48.58 ms | 8.71 ms  | —            |
| 1    | único     | buy      | 13.57 ms | 9.55 ms | 20.93 ms | 2.72 ms  | —            |
| 1    | 5 cli.    | search   | 10.74 ms | 5.58 ms | 22.83 ms | 3.55 ms  | 430.5 req/s  |
| 1    | 5 cli.    | buy      | 14.60 ms | 4.44 ms | 93.74 ms | 15.78 ms | 307.4 req/s  |
| 2    | único     | search   | 12.20 ms | 7.26 ms | 48.58 ms | 7.72 ms  | —            |
| 2    | único     | buy      | 12.49 ms | 9.55 ms | 20.93 ms | 2.44 ms  | —            |
| 2    | 5 cli.    | search   |  8.20 ms | 4.54 ms | 22.73 ms | 3.38 ms  | 563.7 req/s  |
| 2    | 5 cli.    | buy      |  8.61 ms | 4.67 ms | 21.71 ms | 2.85 ms  | 561.1 req/s  |
| 3    | único     | search   | 11.45 ms | 6.83 ms | 20.53 ms | 2.96 ms  | —            |
| 3    | único     | buy      | 12.09 ms | 7.54 ms | 18.51 ms | 3.17 ms  | —            |
| 3    | 5 cli.    | search   |  9.65 ms | 4.82 ms | 27.82 ms | 5.14 ms  | 493.6 req/s  |
| 3    | 5 cli.    | buy      |  8.19 ms | 4.37 ms | 24.39 ms | 3.48 ms  | 573.6 req/s  |
| 4    | único     | search   | 13.93 ms | 7.12 ms | 35.12 ms | 6.72 ms  | —            |
| 4    | único     | buy      | 14.59 ms | 8.53 ms | 28.68 ms | 4.62 ms  | —            |
| 4    | 5 cli.    | search   |  9.14 ms | 3.51 ms | 32.96 ms | 5.30 ms  | 532.4 req/s  |
| 4    | 5 cli.    | buy      |  9.66 ms | 3.99 ms | 32.76 ms | 4.31 ms  | 498.1 req/s  |
| 5    | único     | search   | 10.63 ms | 6.41 ms | 31.75 ms | 5.47 ms  | —            |
| 5    | único     | buy      | 11.09 ms | 7.22 ms | 19.77 ms | 2.94 ms  | —            |
| 5    | 5 cli.    | search   |  8.05 ms | 3.75 ms | 32.04 ms | 4.11 ms  | 572.5 req/s  |
| 5    | 5 cli.    | buy      |  8.80 ms | 3.89 ms | 20.50 ms | 3.26 ms  | 546.3 req/s  |

Médias consolidadas das 5 execuções:

**Cliente único — 30 requisições**

| Operação | Média    | Mínimo  | Máximo   | Desvpad |
|----------|----------|---------|----------|---------|
| `search` | 12.20 ms | 6.41 ms | 48.58 ms | 5.46 ms |
| `buy`    | 12.24 ms | 7.22 ms | 28.68 ms | 3.20 ms |

**5 clientes simultâneos — 30 requisições cada**

| Operação | Média   | Mínimo  | Máximo   | Desvpad | Throughput  |
|----------|---------|---------|----------|---------|-------------|
| `search` | 8.76 ms | 3.51 ms | 32.96 ms | 4.65 ms | ~544 req/s  |
| `buy`    | 9.97 ms | 3.89 ms | 93.74 ms | 5.94 ms | ~497 req/s  |

**Comparação loopback vs. Wi-Fi**

| Cenário             | `search` médio | `buy` médio | `search` throughput | `buy` throughput |
|---------------------|----------------|-------------|---------------------|------------------|
| Loopback (1 cli.)   | 0.73 ms        | 0.98 ms     | —                   | —                |
| Wi-Fi (1 cli.)      | 12.20 ms       | 12.24 ms    | —                   | —                |
| Loopback (5 cli.)   | 1.60 ms        | 2.21 ms     | 3035 req/s          | 2220 req/s       |
| Wi-Fi (5 cli.)      | 8.76 ms        | 9.97 ms     | ~544 req/s          | ~497 req/s       |

---

## 3. Análise dos Resultados

### search e buy ficaram quase iguais no Wi-Fi

No loopback, o `buy` (0.98 ms) é cerca de 34% mais lento que o `search` (0.73 ms). Isso faz sentido, pois o `buy` precisa passar pelo servidor de pedidos, que ainda faz duas chamadas extras ao catálogo, então tem mais passos para completar.

No Wi-Fi, porém, os dois ficaram praticamente iguais: `search` com 12.20 ms e `buy` com 12.24 ms. Isso acontece porque no nosso teste os três servidores estavam na mesma máquina, então as chamadas internas entre eles continuavam sendo loopback mesmo com o cliente em outro computador. O tempo que dominou foi o tempo de ida e volta pela rede Wi-Fi, que é muito maior que os milissegundos extras do `buy`. Em outras palavras, a rede "engoliu" a diferença entre as duas operações.

### Por que o Wi-Fi foi tão mais lento?

Em loopback, um `search` levou 0.73 ms. No Wi-Fi, o mesmo `search` levou 12.20 ms, quase 17 vezes mais. Toda a lógica do servidor (buscar no dicionário, travar o lock, montar a resposta) cabe em menos de 1 ms. O que consumiu os 12 ms foi o tempo de rede: o pacote precisou sair da máquina B, chegar ao roteador da eduroam, ser encaminhado até a máquina A, e a resposta percorrer o caminho de volta.

Isso mostra que melhorar o código interno dos servidores praticamente não ajudaria no cenário de rede real, visto que o gargalo é a própria rede.


### O lock do servidor de pedidos afetou o desempenho?

Em loopback o `buy` teve um throughput cerca de 27% menor que o `search` (2220 vs 3035 req/s). Isso é o lock em ação: como as compras precisam ser serializadas para evitar vender a mesma cópia duas vezes, uma requisição espera a outra terminar.

No Wi-Fi essa diferença caiu para cerca de 8% (497 vs 544 req/s). Isso faz sentido porque o lock é liberado em microssegundos, enquanto a rede leva milissegundos. Então no cenário de rede real o lock deixou de ser o gargalo.

### Como os tempos foram medidos

O script `teste_desempenho.py` cria uma thread por cliente simulado, cada uma com seu próprio canal gRPC. Cada thread envia as requisições em sequência e registra o tempo de cada uma com `time.time()` antes e depois da chamada. Ao final, os tempos de todos os clientes são juntados e calculamos média, mínimo, máximo e desvio padrão. O throughput é calculado dividindo o total de requisições pelo tempo total que as threads levaram para terminar.

---

## 4. Bugs Conhecidos

- **Race condition em `queryNumero` (corrigida):** na versão original, o lock protegia apenas a busca do livro no dicionário, mas os campos como `copias` e `nome` eram lidos depois que o lock já havia sido liberado. Isso significa que outra thread poderia modificar esses campos nesse intervalo. O bug foi corrigido movendo toda a leitura dos campos para dentro do bloco `with lock:`.

- **Estoque vai a negativo se o lock do servidor de pedidos for removido:** sem o lock, duas threads poderiam verificar o estoque ao mesmo tempo, ambas verem que ainda tem cópia disponível, e ambas decrementarem, levando o estoque a -1.

- **Distorção de média no teste de desempenho com muitas requisições `buy`:** o script usa o item 739, que começa com apenas 5 cópias em estoque. Quando o estoque zera, as compras seguintes retornam erro imediatamente, sem fazer as chamadas internas ao catálogo, e por isso chegam mais rápido. Isso puxa a média para baixo e distorce os resultados. Para medir corretamente, é preciso reiniciar o servidor de catálogo antes de cada rodada.

- **Sem persistência:** o estoque só existe em memória. Reiniciar o servidor de catálogo repõe tudo ao estado inicial, perdendo o histórico de compras.

- **Sem reconexão automática:** se um servidor cair e reiniciar, os servidores que dependem dele precisam ser reiniciados também, porque os canais gRPC não se reconectam automaticamente em todos os cenários.

- **Item com estoque zero permanece no catálogo:** quando todas as cópias de um livro são vendidas, ele continua aparecendo nos resultados de `search` e `lookup` com quantidade 0, em vez de ser removido da listagem.