# Bot de documentação — infra_mini_cloud

Assistente de perguntas e respostas sobre a documentação da stack `infra_mini_cloud`.
Usa **RAG** (Retrieval-Augmented Generation): recupera os trechos relevantes dos
`.md` e o **DeepSeek** redige a resposta com base só neles.

---

## 1. Visão geral

```
pergunta
  └─ rag.buscar()                      # acha os trechos certos nos .md
       └─ chat.responder()             # monta o prompt (regras + trechos + histórico)
            └─ llm.chamar()            # DeepSeek redige a resposta
                 └─ resposta + fontes + custo
```

- **Não inventa**: responde apenas com base nos trechos recuperados; se não estiver
  nos docs, diz que não sabe.
- **Cita a fonte**: cada resposta informa de qual arquivo veio.
- **Local e barato**: a busca (embeddings + rerank) roda na máquina; só a redação
  final usa a API do DeepSeek.

---

## 2. Estrutura dos arquivos

| Arquivo | Papel |
|---|---|
| `config.py` | Configuração central (modelo, chave, parâmetros de busca, prompt) |
| `llm.py` | Cliente DeepSeek: retry, timeout e cálculo de custo/tokens |
| `rag.py` | Retrieval: chunking, embeddings (com cache), BM25, rerank e small-to-big |
| `chat.py` | Orquestra retrieval → LLM; devolve resposta + fontes + custo |
| `cli.py` | Chat no terminal (memória, log, custo da sessão) |
| `server.py` | Servidor web (FastAPI): API REST + página de chat |
| `evals.py` | Testes automáticos de qualidade |
| `eval_cases.json` | Casos de teste (pergunta + termos esperados/proibidos) |
| `requirements.txt` | Dependências Python |
| `.env` | Chave da API (`DEEPSEEK_API_KEY`) — **não versionar** |
| `.cache/` | Embeddings em cache (gerado, recria sozinho) |
| `historico.jsonl` | Log de todas as perguntas/respostas (gerado) |

**Base de conhecimento** (indexada): `README.md`, `STACK_DOCS.md`,
`jupyterhub_acl.md`, `redorando.md`, `re_index.md`.
Definida na allowlist `ARQUIVOS_DOCS` em `config.py` — outros `.md` (como este)
não são indexados.

---

## 3. Como o retrieval funciona

A busca tem três técnicas combinadas, todas em `rag.py`:

### 3.1 Busca híbrida (semântica + BM25)
- **Semântica** (embeddings, `all-MiniLM-L6-v2`): entende significado/sinônimos.
- **BM25** (palavra-chave): pega termos exatos (`s3cr3t`, `8090`, nomes de arquivo).
- Os dois scores são normalizados e somados com peso `PESO_SEMANTICO`.

### 3.2 Small-to-big
- Cada seção dos `.md` vira blocos **PAIS** (grandes, ~2000 chars) e cada pai vira
  **FILHOS** (pequenos, ~450 chars).
- A busca acontece nos **filhos** (precisão — acha o ponto exato).
- O que vai pro LLM é o **pai** correspondente (contexto — a resposta completa).

### 3.3 Rerank (cross-encoder)
- A busca híbrida traz `N_CANDIDATOS` filhos.
- Um **cross-encoder** multilíngue lê cada par `(pergunta, trecho)` junto e reordena
  por relevância real — bem mais preciso que comparar vetores separados.
- Ficam os `TOP_K` melhores (mapeados para pais únicos).

### 3.4 Cache de embeddings
- Os vetores são salvos em `.cache/vetores.npy`.
- Um hash do conteúdo decide se reusa o cache ou re-embeda (só quando os docs mudam).

---

## 4. Instalação

```bash
# 1. ambiente (conda neste setup)
conda activate env1

# 2. dependências
cd ~/Desktop/bot_architecture
pip install -r requirements.txt

# 3. chave da API no .env
echo 'DEEPSEEK_API_KEY=sk-sua-chave' > .env
```

> A 1ª execução baixa os modelos locais (embeddings ~80 MB e rerank ~130 MB). Uma vez só.

---

## 5. Como usar

### Terminal
```bash
python cli.py
```
Faça perguntas; digite `sair` para encerrar. Cada resposta mostra fontes, tokens,
custo e latência. Tudo é gravado em `historico.jsonl`.

### Navegador
```bash
uvicorn server:app --port 8000
# abra http://localhost:8000
```
Página de chat pronta. O índice é carregado uma vez no startup.

### API REST
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"pergunta": "Como o Spark conecta no Polaris?", "historico": []}'
```

---

## 6. Avaliação (evals)

```bash
python evals.py
```

Roda os casos de `eval_cases.json` e imprime `X/N passaram`. Cada caso checa:
- `espera`: termos que **devem** aparecer na resposta;
- `proibido` (opcional): termos que **não** podem aparecer (regressão de relevância).

**Fluxo recomendado:** mudou algo (parâmetro, prompt, chunking) → rode os evals →
confirme que o score não caiu. É o que evita "melhorar no escuro".

---

## 7. Ajustes (config.py)

| Parâmetro | O que faz | Quando mexer |
|---|---|---|
| `MODELO_LLM` | Modelo do DeepSeek | trocar custo/qualidade |
| `TEMPERATURE` | Criatividade (0 = factual) | manter baixo p/ docs |
| `TOP_K` | Quantos trechos enviar | resposta incompleta → aumentar |
| `LIMIAR_MIN` | Score mínimo p/ um trecho entrar | trazendo lixo → aumentar |
| `PESO_SEMANTICO` | Semântica vs. palavra-chave | termos exatos falhando → baixar |
| `TAMANHO_PAI` | Tamanho do bloco enviado | resposta cortada → aumentar |
| `TAMANHO_FILHO` | Tamanho do pedaço de busca | busca imprecisa → diminuir |
| `USAR_RERANK` | Liga/desliga o rerank | comparar qualidade nos evals |
| `N_CANDIDATOS` | Candidatos antes do rerank | lento → diminuir |

---

## 8. Custo

A redação final usa o DeepSeek (pago por token); a busca é local (grátis).
Cada resposta reporta o custo; a CLI soma o total da sessão. Os preços por 1M
tokens ficam em `PRECO_INPUT`/`PRECO_OUTPUT` no `config.py` — ajuste pela tabela
atual do DeepSeek.

---

## 9. Segurança

- A chave fica no `.env` (no `.gitignore`) — nunca no código.
- ⚠️ A base de conhecimento contém **credenciais reais** (tokens, senhas). Quem
  consultar o bot recebe esses segredos. Em uso real, redija os segredos antes de
  indexar ou restrinja o acesso ao bot ao mesmo nível de quem pode ver os segredos.

---

## 10. Possíveis evoluções

- **Reescrita de pergunta** com histórico (conserta perguntas encadeadas).
- **Streaming** da resposta (token a token).
- **LLM-as-judge** nos evals (avalia correção, não só palavra-chave).
- **Feedback 👍/👎** gravado em SQLite → vira caso de eval (melhoria contínua).
- **MCP server** expondo `buscar_docs` para clientes como Claude Desktop/Code.
