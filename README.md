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

### Contrato de `query` no catálogo: duas RPCs tipadas em vez de uma polimórfica

O enunciado especifica uma operação `query(arg)` que aceita tanto tópico quanto número de item. Optamos por expor duas RPCs distintas no `.proto` — `queryCategoria(CategoriaRequest)` e `queryNumero(numeroItemRequest)` — em vez de uma única operação com argumento polimórfico. Essa é a forma idiomática em gRPC: cada mensagem tem um tipo bem definido, o compilador valida os campos em tempo de geração de código, e não há necessidade de campos opcionais ou union types para distinguir os casos. O resultado é um contrato mais explícito e menos propenso a erros de uso.

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

### Resultados em rede real (Wi-Fi eduroam, duas máquinas físicas)

Os testes a seguir foram executados com os servidores rodando em uma máquina e o cliente em outra, ambas conectadas à rede Wi-Fi eduroam da UEL. O front-end estava em `191.52.89.180:50050`.

#### Teste manual — interação via cliente interativo

```
>> search computacao
  Livros no tópico 'computacao':
    [739] Sistemas Distribuídos: Conceitos
    [120] Python Fluente
    [789] Clean Code
  Tempo de resposta: 93.31 ms   ← primeira chamada (setup do canal gRPC)

>> lookup 739
  [739] Sistemas Distribuídos: Conceitos
  Categoria : computacao
  Em estoque: 5
  Tempo de resposta: 9.52 ms

>> buy 739
  Sucesso: Compra do livro 'Sistemas Distribuídos: Conceitos' realizada com sucesso!
  Tempo de resposta: 19.39 ms

>> search computacao          ← canal já aquecido
  Tempo de resposta: 16.84 ms

>> lookup 739                 ← estoque decrementou para 4
  Em estoque: 4
  Tempo de resposta: 10.49 ms
```

> A primeira chamada (`search`, 93 ms) inclui o handshake HTTP/2 de estabelecimento do canal gRPC. As chamadas subsequentes, com canal já aquecido, caem para a faixa de 10–20 ms, condizente com a latência Wi-Fi.

#### Teste com script — 5 execuções (`python3 teste_desempenho.py 191.52.89.180:50050 5 30`)

Resultados individuais de cada execução:

| Exec | Teste     | Operação | Média    | Mínimo  | Máximo   | Desvpad  | Throughput   |
|------|-----------|----------|----------|---------|----------|----------|--------------|
| 1    | único     | search   | 12.80 ms | 6.69 ms | 29.31 ms | 4.41 ms  | —            |
| 1    | único     | buy      | 10.96 ms | 7.96 ms | 22.64 ms | 2.84 ms  | —            |
| 1    | 5 cli.    | search   |  8.74 ms | 4.29 ms | 30.87 ms | 5.32 ms  | 560.2 req/s  |
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

**Teste 1 — Cliente único (30 requisições)**

| Operação | Média    | Mínimo  | Máximo   | Desvpad |
|----------|----------|---------|----------|---------|
| `search` | 12.20 ms | 6.41 ms | 48.58 ms | 5.46 ms |
| `buy`    | 12.24 ms | 7.22 ms | 28.68 ms | 3.20 ms |

**Teste 2 — 5 clientes simultâneos (30 requisições cada)**

| Operação | Média   | Mínimo  | Máximo   | Desvpad | Throughput  |
|----------|---------|---------|----------|---------|-------------|
| `search` | 8.76 ms | 3.51 ms | 32.96 ms | 4.65 ms | ~544 req/s  |
| `buy`    | 9.97 ms | 3.89 ms | 93.74 ms | 5.94 ms | ~497 req/s  |

**Comparação loopback vs. rede real**

| Cenário             | `search` médio | `buy` médio | `search` throughput | `buy` throughput |
|---------------------|----------------|-------------|---------------------|------------------|
| Loopback (1 cli.)   | 0.73 ms        | 0.98 ms     | —                   | —                |
| Wi-Fi (1 cli.)      | 12.20 ms       | 12.24 ms    | —                   | —                |
| Loopback (5 cli.)   | 1.60 ms        | 2.21 ms     | 3035 req/s          | 2220 req/s       |
| Wi-Fi (5 cli.)      | 8.76 ms        | 9.97 ms     | ~544 req/s          | ~497 req/s       |

A latência Wi-Fi é ~15–17× maior que em loopback no cliente único. Com 5 clientes simultâneos a diferença cai para ~5–6× na latência, mas o throughput é ~5–6× menor. O pico de 93.74 ms e o desvpad elevado (15.78 ms) na execução 1 do `buy` indicam que o estoque zerou cedo naquela rodada, fazendo chamadas de falha imediata distorcerem a distribuição (conforme o bug conhecido de distorção de média).

---

## 3. Análise e Conclusões

### Impacto da topologia na latência por operação

A arquitetura em três camadas faz com que cada tipo de operação percorra um número diferente de saltos internos:

- **`search` / `lookup`:** cliente → front-end → catálogo → front-end → cliente (1 salto interno).
- **`buy`:** cliente → front-end → pedidos → catálogo (consulta) → pedidos → catálogo (atualização) → pedidos → front-end → cliente (3 saltos internos).

Em loopback, essa diferença é visível: `buy` (0.98 ms) é ~34 % mais lento que `search` (0.73 ms), e os ~0.25 ms de diferença refletem exatamente os dois RPC internos extras que o servidor de pedidos faz ao catálogo. Em Wi-Fi, os servidores ficavam na mesma máquina, então esses saltos internos continuavam sendo loopback — e o resultado confirma: `buy` (12.24 ms) e `search` (12.20 ms) ficaram praticamente idênticos. A latência de rede (RTT Wi-Fi ≈ 10–12 ms) dominou completamente o custo de processamento.

### Rede como gargalo dominante

A comparação direta entre os dois cenários deixa claro onde o tempo vai:

| Cenário           | `search` (1 cli.) | Fator vs. loopback |
|-------------------|-------------------|--------------------|
| Loopback          | 0.73 ms           | 1×                 |
| Wi-Fi eduroam     | 12.20 ms          | ~17×               |

Toda a lógica de aplicação (dicionário em memória, lock, serialização protobuf) cabe em menos de 1 ms. O custo do sistema operacional e do gRPC locais é residual. Em produção, portanto, otimizar a lógica interna dos servidores teria retorno marginal; a alavanca real seria reduzir o número de RTTs visíveis pelo cliente — por exemplo, com caching no front-end para `search`.

### Inversão de latência no modo concorrente em Wi-Fi

Um resultado contraintuitivo: em loopback a latência média *aumenta* ao passar para 5 clientes simultâneos (search: 0.73 → 1.60 ms, +2.2×), mas em Wi-Fi ela *cai* (search: 12.20 → 8.76 ms, −28 %).

O loopback segue o esperado — com canal já aquecido e sem custo de rede, a contenção no lock do catálogo é o fator dominante e penaliza o modo concorrente. Em Wi-Fi o efeito oposto ocorre por dois motivos combinados. Primeiro, o gRPC usa HTTP/2, que multiplexa várias requisições sobre uma única conexão TCP; com múltiplos clientes em paralelo, os frames de requisição saem em rajada e os de resposta chegam intercalados, amortizando o overhead de estabelecimento por requisição. Segundo, no modo de cliente único as requisições são estritamente sequenciais: cada uma espera o ACK da anterior antes de sair, o que equivale a pagar o RTT inteiro de forma serial. No modo concorrente esse tempo de espera é sobreposto entre clientes, reduzindo a latência média observada.

### Serialização pelo lock e seu peso relativo

Em loopback o `buy` perdeu ~27 % de throughput em relação ao `search` (2.220 vs 3.035 req/s), evidência direta de que o lock do servidor de pedidos serializa compras concorrentes. Em Wi-Fi essa penalidade caiu para ~8 % (497 vs 544 req/s): o tempo de aquisição do lock (microssegundos) é desprezível frente ao RTT de rede (~10 ms), então o gargalo deixou de ser o lock e passou a ser a banda/latência Wi-Fi.

Isso valida a decisão de usar um lock simples para a correção — ele é eficaz e não representa um gargalo prático na escala testada. Caso o sistema precisasse escalar para centenas de clientes simultâneos em rede local rápida, seria interessante substituir o `threading.Lock` por um `threading.RLock` diferenciado para leitura/escrita (`rwlock`): operações `search` e `lookup` são somente-leitura e poderiam rodar em verdadeiro paralelo, enquanto `buy` continuaria com acesso exclusivo.

### Throughput: paralelismo amortiza a latência

Apesar da latência Wi-Fi ser ~17× maior que loopback, o throughput caiu apenas ~5–6× (search: 3.035 → 544 req/s). Isso acontece porque os 5 clientes simultâneos fazem com que requisições se sobreponham no tempo — o throughput agrega trabalho de todas as threads, não depende do RTT individual da mesma forma que a latência. O corolário prático: para maximizar vazão em redes de alta latência, o caminho é aumentar o paralelismo de clientes, não tentar reduzir o tempo de cada operação unitária.

### Variabilidade e estabilidade

Em loopback o desvio padrão foi muito baixo (< 0.5 ms), indicando comportamento determinístico. Em Wi-Fi o desvpad subiu para 4–6 ms, reflexo de jitter Wi-Fi e eventuais retransmissões. O pico de 93.74 ms na primeira execução do `buy` concorrente combina dois fatores: o canal gRPC ainda não estava aquecido em alguns clientes e o estoque de 5 cópias foi consumido rapidamente, fazendo que chamadas subsequentes retornassem erro imediato — cujos tempos muito baixos distorcem a média em sentido contrário ao esperado (ver bug de distorção de média na seção 4).

### Decisões de projeto validadas pelos experimentos

| Decisão                                  | Evidência nos dados                                                                 |
|------------------------------------------|-------------------------------------------------------------------------------------|
| Front-end stateless                      | Latência de `search` não aumenta com paralelismo em Wi-Fi; sem contenção no front  |
| Catálogo como fonte única de verdade     | Estoque decrementou corretamente em todas as execuções; sem dupla venda observada   |
| Lock no servidor de pedidos              | Nenhum estoque negativo registrado; custo de serialização visível mas tolerável     |
| `ThreadPoolExecutor(max_workers=10)`     | Suficiente para 5 clientes simultâneos; gargalo foi rede, não pool de threads       |
| Passagem de endereços por argumento      | Permitiu testar distribuído em Wi-Fi sem alterar código                             |

### Limitações e próximos passos

O ponto mais frágil da arquitetura atual é a ausência de persistência: qualquer reinício do catálogo repõe o estoque inicial, tornando o sistema impróprio para uso real. A segunda limitação é a falta de reconexão automática — se um servidor cair, os que dependem dele precisam ser reiniciados manualmente. Para um contexto além do acadêmico, as evoluções naturais seriam: persistência em banco de dados (com transações para o ciclo check-then-act), health-checks e reconexão com backoff exponencial nos canais gRPC, e um read-write lock no catálogo para maior paralelismo em cargas de leitura intensiva.

---

## 4. Bugs Conhecidos

- **Race condition em `queryNumero` (corrigida):** na versão original, o `with lock:` protegia apenas a chamada a `buscar_por_numero`, soltando o lock antes de ler os campos `dados["copias"]`, `dados["nome"]` etc. Uma thread concorrente executando `update()` poderia modificar `dados["copias"]` entre a consulta e a leitura, resultando em valor desatualizado ou leitura parcialmente inconsistente. Corrigido movendo toda a leitura dos campos para dentro do bloco `with lock:`.

- **Estoque vai a negativo se o lock do servidor de pedidos for removido:** a proteção do ciclo check-then-act no servidor de pedidos é feita por um lock global. Se removido, duas threads poderiam ler `quantidade > 0` ao mesmo tempo e ambas decrementariam, levando o estoque a -1.

- **Distorção de média no `teste_desempenho.py` com muitas requisições `buy`:** o script usa o item 739 (estoque inicial: 5 cópias) fixo para todas as compras. Após o estoque zerar, as chamadas retornam erro imediatamente, sem os saltos internos de rede, produzindo tempos muito mais baixos que os de sucesso e distorcendo a média calculada. Para medições confiáveis, reinicie o servidor de catálogo entre execuções ou use um item com estoque alto o suficiente para o número de requisições planejado.

- **Sem persistência:** o estoque não é salvo em disco. Reiniciar o servidor de catálogo repõe todos os livros ao estado inicial, perdendo qualquer histórico de compras.

- **Sem reconexão automática:** se um servidor de back-end cair e reiniciar, o front-end (e o servidor de pedidos) precisam ser reiniciados também, pois os canais gRPC não reconectam de forma transparente em todos os cenários de falha.

- **Item com `copias = 0` permanece no catálogo:** após todas as cópias serem vendidas, o livro continua aparecendo em `search` e `lookup` com quantidade 0 em vez de ser removido da listagem.
