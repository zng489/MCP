---
name: agente-autonomo
description: Construir agentes autônomos em Python com o Claude Agent SDK / API da Anthropic. Use quando o usuário quiser criar um agente que decide sozinho, executa ferramentas em loop, usa memória entre sessões, ou roda tarefas de ponta a ponta sem supervisão. Cobre o loop agêntico (manual e via tool runner), definição de ferramentas, streaming, thinking adaptativo, memória e tratamento de erros.
---

# Construindo agentes autônomos em Python (Claude API / Agent SDK)

Esta skill orienta a escrever **agentes autônomos** — código que dá ao Claude um objetivo,
um conjunto de ferramentas, e o deixa decidir e agir em loop até concluir, sem um humano
aprovando cada passo.

> Instale o SDK: `pip install anthropic` (adicione `anthropic[mcp]` se for usar MCP).
> Credenciais resolvidas do ambiente: `ANTHROPIC_API_KEY` (não escreva a chave no código).

## Padrões obrigatórios (defaults da casa)

Use sempre, salvo pedido explícito do usuário em contrário:

- **Modelo:** `claude-opus-4-8` (o ID está completo — não acrescente sufixo de data).
- **Thinking:** `thinking={"type": "adaptive"}` para qualquer tarefa minimamente complexa.
  Não use `budget_tokens` — retorna 400 no Opus 4.7/4.8.
- **Effort:** `output_config={"effort": "high"}` para trabalho agêntico; `xhigh` para coding
  difícil; `low` para subagentes/tarefas simples.
- **Streaming:** use streaming sempre que a saída puder ser longa ou `max_tokens` for grande
  (> ~16000). Pegue a mensagem final com `stream.get_final_message()`.
- **`max_tokens`:** ~16000 (sem streaming) ou ~64000 (com streaming). Não economize — estourar
  o teto trunca a resposta no meio.

## Qual abordagem escolher

| Necessidade | Use |
|---|---|
| Agente autônomo simples, SDK cuida do loop | **Tool runner** (`@beta_tool` + `tool_runner`) |
| Controle fino: logging, aprovação humana, lógica condicional no loop | **Loop agêntico manual** |
| Anthropic roda o loop e hospeda o sandbox (bash/arquivos/código) | **Managed Agents** (`client.beta.agents` / `sessions`) |

Comece simples. Só vá para Managed Agents quando o usuário quiser que a Anthropic execute o
loop e hospede o container por sessão.

## 1. Tool runner — o caminho mais curto para autonomia

O `tool_runner` executa o ciclo agêntico inteiro: chama a API, detecta o pedido de ferramenta,
executa sua função, devolve o resultado e repete até o Claude parar. Os schemas das ferramentas
saem automaticamente da assinatura tipada da função.

```python
import anthropic
from anthropic import beta_tool

client = anthropic.Anthropic()

@beta_tool
def listar_arquivos(diretorio: str) -> str:
    """Lista os arquivos de um diretório.

    Args:
        diretorio: Caminho do diretório a inspecionar.
    """
    import os
    return "\n".join(os.listdir(diretorio))

@beta_tool
def ler_arquivo(caminho: str) -> str:
    """Lê o conteúdo de um arquivo de texto.

    Args:
        caminho: Caminho do arquivo a ler.
    """
    with open(caminho, encoding="utf-8") as f:
        return f.read()

runner = client.beta.messages.tool_runner(
    model="claude-opus-4-8",
    max_tokens=16000,
    thinking={"type": "adaptive"},
    output_config={"effort": "high"},
    tools=[listar_arquivos, ler_arquivo],
    messages=[{"role": "user", "content": "Resuma o que este projeto faz lendo os arquivos relevantes."}],
)

for message in runner:   # cada iteração é uma BetaMessage; para quando o Claude conclui
    for block in message.content:
        if block.type == "text":
            print(block.text)
```

Para funções assíncronas, use `@beta_async_tool` com `async def` e itere com `async for`.

## 2. Loop agêntico manual — quando precisa de controle

Use quando quiser aprovação humana, logging por passo ou execução condicional. **Regra de ouro
da autonomia:** continue até `stop_reason == "end_turn"`; sempre devolva `response.content`
inteiro (preserva os blocos `tool_use`); cada `tool_result` precisa do `tool_use_id` correto.

```python
import anthropic

client = anthropic.Anthropic()
tools = [...]  # definições JSON das ferramentas
messages = [{"role": "user", "content": objetivo}]

MAX_PASSOS = 50  # trava de segurança contra loop infinito
for _ in range(MAX_PASSOS):
    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=16000,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        tools=tools,
        messages=messages,
    )

    if response.stop_reason == "end_turn":
        break
    if response.stop_reason == "pause_turn":      # ferramenta server-side pausou; reenvie p/ continuar
        messages.append({"role": "assistant", "content": response.content})
        continue
    if response.stop_reason == "refusal":         # recusa de segurança — não retente igual
        print("Recusado:", response.stop_details)
        break

    messages.append({"role": "assistant", "content": response.content})

    resultados = []
    for bloco in response.content:
        if bloco.type == "tool_use":
            try:
                saida = executar_ferramenta(bloco.name, bloco.input)  # sua implementação
                resultados.append({"type": "tool_result", "tool_use_id": bloco.id, "content": saida})
            except Exception as e:
                resultados.append({"type": "tool_result", "tool_use_id": bloco.id,
                                   "content": f"Erro: {e}", "is_error": True})
    messages.append({"role": "user", "content": resultados})
```

Sempre faça `json.loads()` em inputs de ferramenta se precisar processá-los como JSON — nunca
case string crua no input serializado (o escaping pode variar).

## 3. Memória entre sessões (autonomia de longo prazo)

Para o agente reter aprendizados, dê a ele a ferramenta de memória. Subclasse de
`BetaAbstractMemoryTool` e passe ao tool runner:

```python
from anthropic.lib.tools import BetaAbstractMemoryTool

class MinhaMemoria(BetaAbstractMemoryTool):
    def view(self, command): ...
    def create(self, command): ...
    def str_replace(self, command): ...
    def insert(self, command): ...
    def delete(self, command): ...
    def rename(self, command): ...

runner = client.beta.messages.tool_runner(
    model="claude-opus-4-8", max_tokens=16000,
    tools=[MinhaMemoria(), *outras_ferramentas],
    messages=[{"role": "user", "content": "Lembre minhas preferências e use nas próximas tarefas."}],
)
```

Para tarefas muito longas, considere também **compaction** (resume o histórico quando se
aproxima do limite de contexto): `client.beta.messages.create(betas=["compact-2026-01-12"], ...,
context_management={"edits": [{"type": "compact_20260112"}]})`. Anexe sempre `response.content`
inteiro de volta — os blocos de compaction precisam ser preservados.

## 4. Prompt de sistema para autonomia

Um agente autônomo precisa de instruções que evitem que ele pare e pergunte. Inclua no
`system`:

> Você opera de forma autônoma. O usuário não está acompanhando em tempo real e não pode
> responder perguntas no meio da tarefa. Para ações reversíveis que decorrem do pedido
> original, prossiga sem perguntar. Para ações destrutivas ou mudanças de escopo, pare e
> reporte. Antes de encerrar o turno, verifique seu último parágrafo: se for um plano, uma
> pergunta ou uma promessa de trabalho não feito ("vou...", "em seguida..."), execute esse
> trabalho agora com chamadas de ferramenta. Só encerre quando a tarefa estiver concluída ou
> você estiver bloqueado por algo que só o usuário pode fornecer.

## Design das ferramentas

- **Comece com `bash`** para amplitude; promova para ferramenta dedicada quando precisar
  controlar (gate de segurança), renderizar, auditar ou paralelizar a ação.
- Descrições **prescritivas**: diga *quando* chamar, não só o que faz ("Use quando o usuário
  perguntar sobre preços atuais"). O Opus 4.8 puxa ferramentas com mais parcimônia — gatilhos
  explícitos aumentam a taxa de uso correto.
- Para ações com efeito colateral (enviar e-mail, apagar dados), valide o input dentro da
  função e, em autonomia total, registre/limite o alcance.

## Erros e segurança

- Use as exceções tipadas do SDK: `anthropic.RateLimitError`, `anthropic.APIStatusError`, etc.
  O SDK já faz retry com backoff em 429/5xx (`max_retries`, default 2).
- Sempre cheque `response.stop_reason` antes de ler `response.content` (refusal vem com
  `content` vazio).
- Coloque uma trava de iterações (`MAX_PASSOS`) em qualquer loop manual.

## Quando precisar de detalhes

Para Managed Agents, MCP, batches, files, caching e migração de modelo, invoque a skill
`claude-api` (`/claude-api`) — é a referência viva e versionada da API/SDK. **Não invente**
nomes de método ou parâmetros; confirme nos docs antes de escrever.

Um exemplo completo e executável está em `exemplo_agente.py` nesta pasta.
