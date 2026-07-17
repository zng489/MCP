# OpenMetadata - Reindex do Elasticsearch

## Problema

O OpenMetadata usa Elasticsearch para busca de tabelas, tags, usuarios e outros assets.
Quando o stack sobe do zero ou apos um `down -v`, os indices do Elasticsearch podem
ficar dessincronizados ou com mapping incorreto, causando:

- Tabelas que aparecem ao **navegar** mas nao aparecem na **busca**
- Erro **500** com mensagem `tableType is disabled (fielddata)` ou `all shards failed`
- Busca retornando resultados vazios mesmo com dados no Postgres

O mapping errado acontece porque o OpenSearch 2.11 (usado em versoes anteriores) criava
campos como `tableType` e `columnNames` com tipo `text`, quando o correto para o
OM 1.6.6 e tipo `keyword`. Por isso o stack usa **Elasticsearch 8.11.4** com
`SEARCH_TYPE=elasticsearch`.

## Solucao

### 1. Reindex simples (indice existe mas esta dessincronizado)

```bash
docker exec openmetadata-server /opt/openmetadata/bootstrap/openmetadata-ops.sh reindex
```

### 2. Reindex completo (mapping errado ou erro 500)

Se o reindex simples nao resolver ou a busca retornar erro 500, delete os indices
e reinicie o server para recria-los com o mapping correto:

```bash
# deletar indices com mapping errado
curl -X DELETE "http://localhost:9201/table_search_index"
curl -X DELETE "http://localhost:9201/tag_search_index"

# reiniciar o server (recria os indices no boot)
cd ~/docker-apps/infra_mini_cloud_v5
docker compose restart openmetadata-server

# aguardar ficar healthy
docker compose ps openmetadata-server

# rodar o reindex
docker exec openmetadata-server /opt/openmetadata/bootstrap/openmetadata-ops.sh reindex
```

### 3. Verificar o resultado

O output do reindex mostra um resumo no final:

```
jobStatus: "success"
totalRecords: 29
failedRecords: 0
successRecords: 29
```

Se `failedRecords > 0`, verifique os logs do Elasticsearch:

```bash
docker logs om-elasticsearch --tail 50
```

## Quando rodar o reindex

- Apos subir o stack do zero (`docker compose up -d`)
- Apos restaurar volumes ou migrar dados
- Quando a busca no OpenMetadata nao retorna resultados esperados
- Apos rodar ingestion de um novo conector (ex: Polaris/Iceberg)

## Referencia

- Elasticsearch usado: `docker.elastic.co/elasticsearch/elasticsearch:8.11.4`
- Porta do Elasticsearch: `9201` (mapeada de `9200` interna)
- Variavel de ambiente: `SEARCH_TYPE=elasticsearch`
- Documentacao completa do stack: [README.md](README.md) - Secao 7
