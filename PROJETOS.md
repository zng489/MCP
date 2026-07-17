# MCP — Projetos de AI Engineering

Documentação consolidada dos projetos, metodologias, o que cada um ensina e o que ainda falta para um portfólio completo.

---

## Projetos

### 1. `bot_architecture` — RAG com busca híbrida e rerank

**Metodologia:** Bot de Q&A sobre a documentação da stack `infra_mini_cloud`. Combina busca local com LLM (DeepSeek) para responder apenas com base nos documentos indexados.

**Fluxo:**
```
pergunta → rag.buscar() → chat.responder() → llm.chamar() → resposta + fontes + custo
```

**Técnicas:**
- **Busca híbrida**: embeddings semânticos (`all-MiniLM-L6-v2`) + BM25 — cada um captura o que o outro perde
- **Small-to-big**: busca nos chunks pequenos (filhos), entrega ao LLM o chunk grande (pai) para contexto completo
- **Rerank**: cross-encoder multilíngue reordena os candidatos por relevância real, não por similaridade de vetor
- **Cache de embeddings**: vetores salvos em `.npy`, recalcula só quando os docs mudam
- **Evals automatizados**: `eval_cases.json` com termos esperados/proibidos para medir qualidade sem LLM

**Arquivos principais:**
| Arquivo | Papel |
|---|---|
| `rag.py` | Retrieval: chunking, embeddings, BM25, rerank, small-to-big |
| `chat.py` | Orquestra retrieval → LLM |
| `llm.py` | Cliente DeepSeek com retry, timeout e cálculo de custo |
| `server.py` | FastAPI: API REST + página de chat |
| `evals.py` | Testes automáticos de qualidade |
| `cli.py` | Chat no terminal com histórico e custo da sessão |

**Conceito-chave:** como construir RAG de qualidade — híbrido + small-to-big + rerank + evals.

---

### 2. `i_know_everything` — MCP Client + bot Discord

**Metodologia:** Bot Discord que age como **cliente MCP** — spawna um MCP server local (`kb_server.py`), usa as tools para buscar na knowledge base, e deixa o DeepSeek decidir quando e qual tool chamar.

**Fluxo:**
```
@menção no Discord → DeepSeek decide a tool → MCP server busca na KB → resposta no canal
```

**Técnicas:**
- **MCP protocol (stdio)**: o bot spawna o `kb_server.py` como subprocess e se comunica via `ClientSession`
- **Agentic tool-calling loop**: até 5 rodadas — o LLM chama tools quantas vezes quiser antes de responder
- **Fuzzy search**: `SequenceMatcher` encontra termos mesmo com typos ("kubernets" → "kubernetes")
- **Conversão automática**: tools MCP → formato OpenAI function calling

**Arquivos principais:**
| Arquivo | Papel |
|---|---|
| `discord_bot.py` | Cliente MCP + integração Discord |
| `kb_server.py` | MCP server com 3 tools: `list_sections`, `search_kb`, `read_section` |
| `KNOWLEDGE_BASE.md` | Base de conhecimento indexada (gerada de um USB drive de Data Engineering) |

**Conceito-chave:** como ser **cliente MCP** — conectar num server externo e deixar o LLM usar as tools autonomamente.

---

### 3. `project` — Agente autônomo com function calling loop

**Metodologia:** Agente que recebe uma pergunta em português, escreve o SQL sozinho via function calling do DeepSeek, executa no MotherDuck (DuckDB cloud), e itera até ter a resposta — sem o usuário tocar em SQL.

**Fluxo:**
```
pergunta → DeepSeek escreve SQL → consultar_rais(sql) → resultado → DeepSeek analisa → repete ou responde
```

**Técnicas:**
- **Loop agêntico manual**: `for` com até 25 iterações — sem framework, só Python puro
- **Function calling nativo**: uma tool `consultar_rais` definida como JSON schema no formato OpenAI/DeepSeek
- **Guardrails básicos**: bloqueia INSERT/UPDATE/DELETE/DROP, trunca resultado a 20k chars, limite de 25 passos
- **Exploração autônoma do schema**: o agente começa com `DESCRIBE` ou `LIMIT 5` se não conhece as colunas

**Arquivos principais:**
| Arquivo | Papel |
|---|---|
| `agente_rais.py` | Loop agêntico — o "cérebro" (DeepSeek) |
| `rais_2024.py` | Tool — a "mão" que executa SQL no MotherDuck |
| `CLAUDE.md` | Instrui o Claude Code a sempre delegar perguntas sobre RAIS ao agente |

**Conceito-chave:** loop agêntico manual com function calling — sem LangChain, sem CrewAI, só Python.

---

### 4. `mcp_api` — MCP Server com tools e resources (PokéAPI)

**Metodologia:** MCP server que expõe a PokéAPI como tools e resources para clientes como Claude Desktop/Code. O LLM decide quando e como usar as tools — o server só executa.

**Fluxo:**
```
Claude Desktop → chama tool get_pokemon("pikachu") → server faz request à PokéAPI → retorna dados formatados
```

**Técnicas:**
- **FastMCP framework**: decoradores `@mcp.tool()` e `@mcp.resource()` para exposição automática
- **Tools vs Resources**: tools são chamadas ativas pelo LLM; resources são dados carregados no contexto
- **Transporte stdio**: integra direto com Claude Desktop via `claude_desktop_config.json`

**Tools expostas:**
| Tool | O que faz |
|---|---|
| `get_pokemon(name)` | Detalhes de um Pokémon (tipos, habilidades, stats, sprite) |
| `get_type(name)` | Relações de dano de um tipo (forte contra, fraco contra, sem efeito) |
| `list_pokemon(limit, offset)` | Lista Pokémon com paginação |

**Conceito-chave:** como ser **servidor MCP** — expor APIs externas como tools + resources para qualquer cliente MCP.

---

### 5. `mcp_motherduck` — MCP Server de dados SQL

**Metodologia:** MCP server mínimo que expõe uma única tool `query_rais` para consultar a tabela RAIS 2024 no MotherDuck diretamente de dentro do Claude Desktop.

**Fluxo:**
```
Claude Desktop → chama tool query_rais("SELECT ...") → DuckDB conecta no MotherDuck → retorna DataFrame como texto
```

**Técnicas:**
- **MCP server mínimo**: uma tool só, sem resources — o mínimo viável para expor dados via MCP
- **DuckDB + MotherDuck**: conexão direta ao data warehouse cloud via token JWT
- **Configuração conda**: roda via `conda run -n wh` no `claude_desktop_config.json`

**Conceito-chave:** MCP server de dados — o Claude escreve e executa SQL em dados reais sem sair do chat.

> ⚠️ **Problema conhecido:** token JWT hardcoded na linha 26. Deveria vir de `os.environ["MOTHERDUCK_TOKEN"]`.

---

### 6. `enterprise_project` — RAG empresarial com Qdrant + ingestão incremental + OCR

**Metodologia:** Pipeline RAG completo e produtivo — ingestão incremental de PDFs com rastreamento de mudanças por hash, banco vetorial persistente (Qdrant), OCR para PDFs escaneados, e MCP server separado apenas para busca.

**Fluxo:**
```
static/files/*.pdf
    ↓
[a] file_finder.py        → localiza PDFs
[b] pdf_text_extractor.py → extrai texto via PyMuPDF + EasyOCR
[c] text_chunker.py       → divide em chunks com sobreposição
[d] vector_store.py       → embeddings (bge-small-en-v1.5) + armazena no Qdrant
[e] metadata_tracker.py   → hash MD5 por PDF (detecta novos e modificados)
    ↓
  Qdrant (persistido em qdrant_db/)
    ↓
mcp_qdrant_server.py      → MCP server: tool buscar_runbook(pergunta) → top-5 trechos
```

**Técnicas:**
- **Ingestão incremental**: só processa PDFs novos ou modificados (hash MD5) — evita duplicatas
- **Re-indexação limpa**: PDFs modificados têm chunks antigos apagados do Qdrant antes de re-indexar
- **OCR**: EasyOCR para PDFs escaneados que não têm texto nativo
- **Modelo local**: `bge-small-en-v1.5` — carregado do disco, sem download na inicialização
- **Separação clara**: ingestão (`main_ingest.py`) é independente do servidor MCP (`mcp_qdrant_server.py`)

**Diferença em relação ao `bot_architecture`:**
| | `bot_architecture` | `enterprise_project` |
|---|---|---|
| Banco vetorial | Cache `.npy` em memória | Qdrant (persistido em disco) |
| Ingestão | Re-indexa tudo | Incremental por hash MD5 |
| OCR | Não tem | EasyOCR |
| Rerank | Cross-encoder | Não tem |
| Interface | CLI + FastAPI | MCP server |

**Conceito-chave:** RAG pronto para produção — incremental, persistido, rastreável, com OCR e MCP.

---

## Resumo comparativo

| Projeto | Metodologia | LLM | Busca/Storage | Interface |
|---|---|---|---|---|
| `bot_architecture` | RAG híbrido + rerank + evals | DeepSeek | Local `.npy` + cross-encoder | CLI + FastAPI |
| `i_know_everything` | MCP Client + agentic loop | DeepSeek | Fuzzy search em `.md` (MCP tools) | Discord bot |
| `project` | Agente autônomo (function calling loop) | DeepSeek | SQL no MotherDuck (DuckDB cloud) | CLI |
| `mcp_api` | MCP Server (tools + resources) | — | PokéAPI REST | Claude Desktop/Code |
| `mcp_motherduck` | MCP Server (SQL tool) | — | DuckDB / MotherDuck | Claude Desktop/Code |
| `enterprise_project` | RAG empresarial + ingestão incremental | — | Qdrant local + bge-small + OCR | MCP server |

### O que cada projeto ensina

| Projeto | Conceito-chave |
|---|---|
| `bot_architecture` | RAG de qualidade: híbrido + small-to-big + rerank + evals por palavra-chave |
| `i_know_everything` | Ser cliente MCP: spawnar server, tool-calling loop, integrar com Discord |
| `project` | Loop agêntico manual: function calling sem framework, guardrails básicos |
| `mcp_api` | Ser servidor MCP: expor API externa como tools + resources |
| `mcp_motherduck` | MCP server mínimo: uma tool, dados reais, integração Claude Desktop |
| `enterprise_project` | RAG produção: ingestão incremental, Qdrant persistido, OCR, MCP separado |

---

## O que ainda falta

Metodologias relevantes de AI Engineering não cobertas por nenhum dos projetos atuais:

| O que falta | Por que importa |
|---|---|
| **Multi-agent** | Múltiplos agentes com papéis distintos (pesquisador, executor, revisor) coordenados — nenhum projeto tem mais de 1 agente |
| **Memória persistente** | Nenhum projeto lembra conversas anteriores entre sessões (episodic memory, long-term memory) |
| **LLM-as-judge** | `bot_architecture` avalia por palavra-chave; avaliação com outro LLM é muito mais robusta e escalável |
| **Observabilidade / tracing** | Nenhum projeto rastreia latência, tokens, erros por chamada (Langfuse, LangSmith) |
| **Streaming** | Todos retornam resposta completa — streaming token-a-token não está em nenhum projeto |
| **Guardrails robustos** | Só o bloqueio de INSERT/DELETE no agente SQL — nada de validação de output, detecção de prompt injection |
| **Fine-tuning** | Todos usam modelos prontos — nenhum projeto adapta um modelo a um domínio específico |
| **GraphRAG** | RAG baseado em grafo de conhecimento (relações entre entidades), mais poderoso que chunking linear |

### Prioridade de implementação

1. **Observabilidade** — valor imediato em qualquer projeto existente, só adiciona instrumentação (Langfuse é open source)
2. **LLM-as-judge** — melhora direto os evals do `bot_architecture` e do `enterprise_project`
3. **Multi-agent** — passo natural após ter agente autônomo (`project`) funcionando
4. **Memória persistente** — completa o `i_know_everything` ou o `project` com contexto entre sessões

---

## Visão de um projeto que une tudo

Um **assistente de dados empresarial** que combine todas as metodologias:

```
PDFs / docs
    ↓
[enterprise_project]  ingestão incremental → Qdrant
    ↓
[bot_architecture]    RAG híbrido + rerank sobre o Qdrant
    ↓
[mcp_api / mcp_motherduck]  MCP servers: docs + SQL (RAIS/MotherDuck)
    ↓
[project]             agente autônomo: decide se busca docs ou roda SQL
    ↓
[i_know_everything]   bot Discord como cliente MCP
```

O agente central recebe uma pergunta e decide:
- *"está nos documentos?"* → chama a tool de RAG
- *"é dado numérico?"* → chama a tool SQL

O que ainda precisaria adicionar para ser completo: memória entre sessões, observabilidade (Langfuse), LLM-as-judge nos evals e múltiplos agentes especializados.
