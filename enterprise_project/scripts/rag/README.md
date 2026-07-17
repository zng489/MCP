# Sistema RAG: Processamento de Múltiplos Documentos

Este documento explica como o sistema RAG (Retrieval-Augmented Generation) processa e armazena múltiplos documentos PDF no banco de dados vetorial Qdrant.

## Arquitetura do Sistema

O sistema RAG é composto por vários módulos que trabalham juntos para processar documentos e permitir consultas semânticas:

- `file_finder.py`: Localiza arquivos PDF na pasta `static/files`
- `pdf_text_extractor.py`: Extrai texto dos PDFs usando PyMuPDF e EasyOCR
- `text_chunker.py`: Divide o texto em chunks semânticos
- `vector_store.py`: Gerencia o armazenamento e recuperação de embeddings no Qdrant
- `main_rag.py`: Orquestra o fluxo completo do pipeline

## Fluxo de Processamento de Múltiplos PDFs

![RAG Pipeline](https://mermaid.ink/img/pako:eNp1kU1PwzAMhv9KlBOIbdI-tKnrBBJiB8QBceCyQ5S6XaPmQ0lSoKr633FSVm3AXOLn9WvHdnrQxhLk2jbkHLwjbwfyFp6wbcnBK3ZgLTkMUEGDDXlVQY0dVdDYGp3vwVXwjJ3FV3gzrZnQBXgxDVXQGtVTBZ_GdlRBZ1_QVfCCvfeBKvAm-Gj8QBU8YRcwwKtpg_cBXk3jqILGNGhHqmDEzg_Yjei8hRfTWnKQm9Y5qmDPbRhxwM6hg9y0vbOBcjNiZ9BBbgbTOQe5GbHr0UFu3k3v0UFuRtMEBzlWJqCD3IzYDOggN6NpRwe5-TBdQAe5GbEJ6CA3o-lG_M9NXKZJnKbxKk7TxSrO0iSJl1mSZtGCxXGWZYs0XrI0XqbRKmLRnC3YnM1YxKZzFrHFnEVsOWcRW81ZxLI5i1g-ZxFbzVnE8ux7_QUDxcFg?type=png)

1. **Localização de PDFs**:
   - O sistema busca todos os arquivos PDF na pasta `static/files`
   - Cada arquivo encontrado é processado individualmente

2. **Para cada PDF**:
   - **Extração de Texto**: O texto é extraído usando uma combinação de extração nativa e OCR
   - **Chunking**: O texto é dividido em pedaços menores (chunks) com sobreposição
   - **Geração de Embeddings**: Cada chunk é convertido em um vetor de embedding
   - **Armazenamento**: Os chunks e seus embeddings são armazenados no Qdrant

3. **Metadados**:
   - Cada chunk armazenado contém:
     - O texto do chunk
     - O nome do arquivo de origem (`source`)
     - O índice do chunk no documento original (`chunk_index`)

## Estrutura de Armazenamento no Qdrant

O Qdrant armazena todos os chunks de todos os PDFs em uma única coleção chamada `knowledge_base_pdfs`. Cada ponto no Qdrant representa um chunk e contém:

```json
{
  "id": "uuid-gerado-automaticamente",
  "vector": [0.1, 0.2, ..., 0.5],  // Embedding do chunk
  "payload": {
    "text": "Conteúdo do chunk...",
    "source": "documento1.pdf",
    "chunk_index": 0
  }
}
```

### Vantagens desta Abordagem

- **Busca Unificada**: Consultas buscam em todos os documentos simultaneamente
- **Rastreabilidade**: Cada resultado pode ser rastreado até seu documento de origem
- **Escalabilidade**: Novos documentos podem ser adicionados a qualquer momento
- **Eficiência**: A busca por similaridade é otimizada pelo Qdrant

## Processo de Consulta

Quando uma consulta é feita:

1. O texto da consulta é convertido em um embedding
2. O Qdrant busca os chunks mais similares em toda a coleção
3. Os resultados incluem o texto do chunk, o documento de origem e a pontuação de similaridade

## Considerações para Grandes Volumes

Para sistemas com muitos documentos (centenas ou milhares), considere:

- **Processamento em Lotes**: Processar PDFs em grupos para gerenciar memória
- **Indexação Incremental**: Rastrear quais PDFs já foram processados
- **Filtragem Avançada**: Adicionar metadados como data, categoria, autor, etc.
- **Particionamento**: Dividir a coleção em subcoleções por tema ou departamento

## Exemplo de Uso

```python
# Iniciar o pipeline RAG
from main_rag import main_rag

# Processar todos os PDFs e executar uma consulta de exemplo
results = main_rag()

# Os resultados contêm os chunks mais relevantes com seus metadados
for result in results:
    print(f"Texto: {result['text']}")
    print(f"Fonte: {result['source']}")
    print(f"Similaridade: {result['score']}")
```

## Manutenção do Banco de Dados

O Qdrant mantém os dados persistentes no diretório `qdrant_db` na raiz do projeto. Este banco de dados não precisa ser reiniciado a cada execução - ele mantém todos os dados entre execuções do sistema.

Para reconstruir o banco de dados do zero, basta excluir o diretório `qdrant_db` e executar o pipeline novamente.