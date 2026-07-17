# Documentação — Ingestão Incremental de PDFs no Qdrant

## Visão Geral

O sistema de ingestão incremental permite atualizar o banco de dados vetorial (Qdrant) apenas com os PDFs que são **novos** ou **modificados**, sem precisar reprocessar toda a base de documentos.

---

## Arquivos Envolvidos

| Arquivo | Função |
|---|---|
| `main_ingest.py` | Script principal que orquestra a ingestão incremental |
| `main_ingest.bat` | Script batch para executar o `main_ingest.py` com ambiente conda |
| `a_file_finder.py` | Localiza os PDFs no diretório `static/files/` |
| `b_pdf_text_extractor.py` | Extrai texto dos PDFs (nativo + OCR) |
| `c_text_chunker.py` | Divide o texto em chunks menores |
| `d_vector_store.py` | Gerencia operações no Qdrant (armazenar, deletar, buscar) |
| `e_metadata_tracker.py` | Rastreia quais PDFs já foram processados via `processed_pdfs.json` |

---

## Como Funciona

### 1. Detecção de PDFs Novos ou Modificados

O script `main_ingest.py` chama a função `get_new_or_modified_pdfs()` que:

- Lê todos os PDFs da pasta `static/files/`
- Compara com o arquivo `processed_pdfs.json`
- Calcula o **hash MD5** de cada PDF para detectar alterações
- Retorna duas listas:
  - `new_pdfs`: PDFs que não existiam no JSON (nunca processados)
  - `modified_pdfs`: PDFs que existem no JSON, mas cujo hash mudou (conteúdo alterado)

### 2. Fluxo de Processamento

```
Início
  │
  ▼
Existem PDFs novos ou modificados?
  │
  ├── Não → "Database is up to date" (encerra)
  │
  └── Sim → Carregar modelo de embeddings
              │
              ▼
            Conectar ao Qdrant
              │
              ▼
            Para cada PDF MODIFICADO:
              │
              ├── Deletar vetores antigos do Qdrant (delete_by_source)
              ├── Extrair texto (extrair_texto_do_pdf_com_easyocr)
              ├── Dividir em chunks (split_text_into_chunks)
              ├── Gerar embeddings (model.encode)
              ├── Armazenar no Qdrant (store_embeddings)
              └── Marcar como processado (mark_pdf_as_processed)
              │
              ▼
            Para cada PDF NOVO:
              │
              ├── Extrair texto
              ├── Dividir em chunks
              ├── Gerar embeddings
              ├── Armazenar no Qdrant
              └── Marcar como processado
              │
              ▼
            Fim
```

### 3. Arquivo de Metadados (`processed_pdfs.json`)

Este arquivo é criado automaticamente na pasta `scripts/rag/` e armazena:

```json
{
  "processed_pdfs": {
    "documento_exemplo.pdf": {
      "hash": "a1b2c3d4e5f6...",
      "chunks_count": 15,
      "path": "C:\\...\\static\\files\\documento_exemplo.pdf"
    }
  }
}
```

**Campos:**
- `hash`: Hash MD5 do arquivo no momento do processamento
- `chunks_count`: Quantidade de chunks gerados a partir do PDF
- `path`: Caminho completo do arquivo

### 4. Detecção de Alterações

A verificação funciona assim:

```
PDF no disco              PDF no JSON               Ação
─────────────────────────────────────────────────────────
Não existe no JSON    →   —                         Processar como NOVO
Existe no JSON        →   Hash igual                Pular (já processado)
Existe no JSON        →   Hash diferente            Re-indexar (MODIFICADO)
```

---

## Como Executar

### Opção 1 — Pelo terminal

```bash
python main_ingest.py
```

### Opção 2 — Pelo script batch

```bash
main_ingest.bat
```

O `.bat` ativa o ambiente conda automaticamente antes de executar o Python.

---

## Exemplos de Saída

### Nenhum PDF novo

```
No new or modified PDFs found. Database is up to date.
```

### PDFs novos encontrados

```
Found 2 new PDFs and 0 modified PDFs
Loading embedding model from: C:\...\model\bge-small-en-v1.5
Processing: relatorio_vendas.pdf
Split text into 12 chunks
Successfully stored 12 embeddings in Qdrant
Marked 'relatorio_vendas.pdf' as processed (12 chunks)
Processing: manual_sistema.pdf
Split text into 8 chunks
Successfully stored 8 embeddings in Qdrant
Marked 'manual_sistema.pdf' as processed (8 chunks)
Ingestion complete. Total chunks added: 20
```

### PDF modificado detectado

```
Found 0 new PDFs and 1 modified PDFs
Re-indexing modified PDF: relatorio_vendas.pdf
Deleted vectors from source: relatorio_vendas.pdf
Processing: relatorio_vendas.pdf
Split text into 14 chunks
Successfully stored 14 embeddings in Qdrant
Marked 'relatorio_vendas.pdf' as processed (14 chunks)
Ingestion complete. Total chunks added: 14
```

---

## Casos de Uso

| Cenário | O que acontece |
|---|---|
| Adicionei 3 PDFs novos na pasta | Os 3 são processados e indexados |
| Rodei o script novamente sem mudar nada | Nada é processado |
| Editei 1 PDF existente | O PDF antigo é deletado do Qdrant e re-indexado |
| Deletei 1 PDF da pasta | Nada acontece (os vetores antigos permanecem no Qdrant) |
| Renomeei 1 PDF | É tratado como 1 novo + 1 antigo permanece |

---

## Requisitos

- Modelo de embeddings em: `enterprise_project/model/bge-small-en-v1.5`
- PDFs em: `enterprise_project/static/files/`
- Banco Qdrant em: `enterprise_project/scripts/qdrant_db/`

---

## Limitações

1. **PDFs deletados da pasta**: Se você remover um PDF de `static/files/`, os vetores correspondentes não são automaticamente removidos do Qdrant. Para isso, use manualmente:

   ```python
   from d_vector_store import initialize_qdrant_client, delete_by_source
   client = initialize_qdrant_client()
   delete_by_source(client, "nome_do_arquivo.pdf")
   ```

2. **Primeira execução**: Na primeira vez que rodar o script, todos os PDFs serão processados, pois o `processed_pdfs.json` ainda não existe.

---

## Rebuild Completo

Se precisar reindexar tudo do zero:

1. Delete o arquivo `processed_pdfs.json`
2. Delete a pasta `qdrant_db/`
3. Execute `python main_ingest.py`

Isso recriará o banco e o metadados desde o início.
