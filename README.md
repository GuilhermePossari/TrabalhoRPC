# Minibib.com — Livraria Remota com gRPC

Projeto de Sistemas Distribuídos — UEL  
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

Os servidores devem ser iniciados na seguinte ordem, pois cada um depende do anterior:

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

> **Atenção:** o script usa o item 739 com estoque inicial de 5 cópias para as requisições `buy`. Com muitas requisições, o estoque zera e as compras seguintes retornam erro imediatamente — tempos de falha são mais rápidos que os de sucesso, distorcendo a média. Reinicie o servidor de catálogo entre execuções do teste para restaurar o estoque.

---

## Teste em máquinas separadas

Para distribuir os componentes entre máquinas diferentes (ex.: durante apresentação com a dupla), basta substituir `localhost` pelo IP real de cada máquina. Certifique-se de que as portas escolhidas estejam liberadas no firewall.

### Exemplo de distribuição

| Componente            | Máquina       | Porta  |
|-----------------------|---------------|--------|
| Servidor de Catálogo  | `192.168.1.10` | 50051  |
| Servidor de Pedidos   | `192.168.1.11` | 50052  |
| Servidor Front-End    | `192.168.1.12` | 50050  |
| Cliente               | qualquer       | —      |

### Comandos correspondentes

```bash
# Máquina 192.168.1.10 — Catálogo
python3 servidorCatalogo.py 50051

# Máquina 192.168.1.11 — Pedidos (aponta para o catálogo na outra máquina)
python3 servidorPedidos.py 50052 192.168.1.10:50051

# Máquina 192.168.1.12 — Front-End
python3 servidorFront.py 50050 192.168.1.10:50051 192.168.1.11:50052

# Qualquer máquina — Cliente
python3 cliente.py 192.168.1.12:50050

# Qualquer máquina — Teste de desempenho
python3 teste_desempenho.py 192.168.1.12:50050 5 30
```

### Verificar conectividade antes de iniciar

```bash
# Testa se a porta do catálogo está acessível a partir da máquina de pedidos
nc -zv 192.168.1.10 50051

# Alternativa com curl (gRPC usa HTTP/2)
curl -v --http2 http://192.168.1.10:50051
```

### Diferenças esperadas de desempenho

Com componentes em máquinas separadas a latência cresce proporcionalmente ao número de saltos de rede reais. `buy` trafega pela rede três vezes (cliente→front, front→pedidos, pedidos→catálogo + volta), enquanto `search` trafega apenas uma vez (cliente→front→catálogo + volta). Os valores obtidos em loopback servem como baseline para comparar com o cenário distribuído real.

---

## 1. Decisões de Projeto

### Estrutura de dados do catálogo

O catálogo é mantido em memória como um dicionário Python (`dict`), indexado por uma chave interna sequencial. Cada valor é um dicionário com os campos `numero`, `nome`, `categoria` e `copias`.

Essa escolha é justificada pelo enunciado, que permite manter o catálogo em memória. O dicionário oferece acesso O(1) pela chave interna e iteração simples para busca por categoria. Não há persistência em disco — ao reiniciar o servidor de catálogo, o estoque volta ao estado inicial.

### Design de concorrência

**Servidor de Catálogo:** um único `threading.Lock` protege todas as operações de leitura e escrita sobre o dicionário de livros. Isso garante que atualizações de estoque sejam atômicas.

**Servidor de Pedidos:** o mesmo `threading.Lock` protege o ciclo completo de "consulta → decremento", impedindo que duas compras simultâneas da última cópia sejam ambas bem-sucedidas (race condition clássica de check-then-act).

**Servidor Front-End:** não possui estado compartilhado; apenas repassa chamadas para o catálogo e para pedidos, portanto não precisa de lock próprio.

**Thread pool:** todos os três servidores são criados com `futures.ThreadPoolExecutor(max_workers=10)`, permitindo até 10 requisições simultâneas por servidor.

### Comunicação entre servidores

Todo o transporte é feito via gRPC com canais inseguros (`insecure_channel`), adequado para ambiente acadêmico local. Os endereços dos servidores dependentes são passados como argumentos de linha de comando, permitindo que cada componente rode em máquinas diferentes.

### Separação de responsabilidades

O servidor de pedidos não mantém estado próprio; toda informação de estoque vive exclusivamente no catálogo. O servidor de pedidos apenas orquestra a transação: consulta o catálogo, valida o estoque e aciona a atualização. Isso mantém o catálogo como fonte única de verdade.

---

## 2. Resultados Experimentais

Todos os testes foram executados na mesma máquina (loopback), com os três servidores rodando localmente. Os tempos medem a latência de ponta a ponta vista pelo cliente (desde o envio da requisição até o recebimento da resposta). A medição usa `time.time()` em torno de cada chamada gRPC no script `teste_desempenho.py`.

### Teste 1 — Cliente único (30 requisições)

| Operação | Média   | Mínimo  | Máximo  | Desvio padrão |
|----------|---------|---------|---------|---------------|
| `search` | 0.73 ms | 0.58 ms | 2.76 ms | 0.39 ms       |
| `buy`    | 0.98 ms | 0.79 ms | 2.95 ms | 0.40 ms       |

`buy` é ligeiramente mais lento que `search` porque envolve dois saltos de rede internos: o front-end chama o servidor de pedidos, que por sua vez chama o catálogo duas vezes (query + update). `search` faz apenas um salto (front-end → catálogo).

### Teste 2 — 5 clientes simultâneos (30 requisições cada, 150 no total)

| Operação | Média   | Mínimo  | Máximo  | Desvio padrão | Throughput   |
|----------|---------|---------|---------|---------------|--------------|
| `search` | 1.60 ms | 1.09 ms | 2.57 ms | 0.24 ms       | 3035 req/s   |
| `buy`    | 2.21 ms | 1.81 ms | 4.37 ms | 0.48 ms       | 2220 req/s   |

Com 5 clientes simultâneos, a latência média aumenta ~2× em relação ao cliente único, o que é esperado dado o lock de exclusão mútua no servidor de pedidos e a contenção no catálogo. O desvio padrão se mantém baixo, indicando comportamento estável sob carga moderada.

**Como os tempos foram obtidos:** o script `teste_desempenho.py` cria uma thread por cliente simulado, cada uma com seu próprio canal gRPC. Todas as threads são iniciadas antes de qualquer uma começar a enviar requisições (sincronização implícita por `thread.start()` em sequência imediata), e os tempos individuais de cada requisição são coletados com `time.time()`. Ao final, são calculadas média, mínimo, máximo e desvio padrão sobre todos os tempos agregados de todos os clientes.

---

## 3. Bugs Conhecidos

- **Race condition em `queryNumero` (corrigida):** na versão original, o `with lock:` protegia apenas a chamada a `buscar_por_numero`, soltando o lock antes de ler os campos `dados["copias"]`, `dados["nome"]` etc. Uma thread concorrente executando `update()` poderia modificar `dados["copias"]` entre a consulta e a leitura, resultando em valor desatualizado ou leitura parcialmente inconsistente. Corrigido movendo toda a leitura dos campos para dentro do bloco `with lock:`.

- **Estoque vai a negativo se o lock do servidor de pedidos for removido:** a proteção do ciclo check-then-act no servidor de pedidos é feita por um lock global. Se removido, duas threads poderiam ler `quantidade > 0` ao mesmo tempo e ambas decrementariam, levando o estoque a -1.

- **Distorção de média no `teste_desempenho.py` com muitas requisições `buy`:** o script usa o item 739 (estoque inicial: 5 cópias) fixo para todas as compras. Após o estoque zerar, as chamadas retornam erro imediatamente, sem os saltos internos de rede, produzindo tempos muito mais baixos que os de sucesso e distorcendo a média calculada. Para medições confiáveis, reinicie o servidor de catálogo entre execuções ou use um item com estoque alto o suficiente para o número de requisições planejado.

- **Sem persistência:** o estoque não é salvo em disco. Reiniciar o servidor de catálogo repõe todos os livros ao estado inicial, perdendo qualquer histórico de compras.

- **Sem reconexão automática:** se um servidor de back-end cair e reiniciar, o front-end (e o servidor de pedidos) precisam ser reiniciados também, pois os canais gRPC não reconectam de forma transparente em todos os cenários de falha.

- **Item com `copias = 0` permanece no catálogo:** após todas as cópias serem vendidas, o livro continua aparecendo em `search` e `lookup` com quantidade 0 em vez de ser removido da listagem.
