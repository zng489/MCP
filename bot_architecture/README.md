# Infra Mini Cloud v5

Stack local de engenharia de dados com Docker Compose:
**Spark 4.1.2 + Jupyter + RustFS (storage S3) + Apache Polaris (catálogo Iceberg,
persistido em Postgres) + Airflow + OpenMetadata**.

Tudo numa única rede bridge `infra-net`, com configuração inicial automática
(buckets, catálogos, schema do Polaris, DAGs) via containers one-shot.

---

## 1. Visão geral

```
                       ┌──────────────────────────────────────────┐
                       │              rede: infra-net               │
                       │                                            │
  Jupyter / Spark ─────┼──► Polaris (catálogo) ──► RustFS (S3) ◄────┤
   (escreve Iceberg)   │     8181  └─ Postgres        9000          │
                       │           (persistência)                   │
  Airflow (orquestra)  │   OpenMetadata (governança — opcional)     │
                       └──────────────────────────────────────────┘
```

- **Spark/Jupyter** processam e escrevem tabelas Iceberg.
- **Polaris** guarda os metadados do catálogo (tabelas/namespaces), **persistidos
  em Postgres** (`polaris-postgres`) — sobrevivem a restart.
- **RustFS** armazena os arquivos (Parquet + metadados Iceberg) em `s3://<bucket>/`.
- **Airflow** orquestra DAGs e submete os jobs ao **cluster Spark**.
- **OpenMetadata** catalogação/governança (sob profile `governanca`, não sobe por
  padrão).

---

## 2. Serviços, portas e acessos

| Serviço | URL / Porta | Credenciais | Para quê |
|---------|-------------|-------------|----------|
| **Jupyter Lab** | http://localhost:8888 | token: `spark123` | notebooks / Spark |
| **Spark Master UI** | http://localhost:8088 | — | monitorar cluster |
| Spark Worker 1 | http://localhost:8081 | — | worker |
| Spark Worker 2 | http://localhost:8082 | — | worker |
| Spark cluster | `spark://spark-master:7077` | — | submit de jobs |
| **RustFS (S3 API)** | http://localhost:9000 | `rustfs` / `rustfs123` | storage S3 |
| RustFS Console | http://localhost:9001 | `rustfs` / `rustfs123` | UI do storage |
| **Polaris (API)** | http://localhost:8181 | `root` / `s3cr3t` | catálogo Iceberg REST |
| Polaris (health) | http://localhost:8182/q/health | — | healthcheck |
| **Airflow UI** | http://localhost:8090 | `airflow` / `airflow` | orquestração |
| **OpenMetadata** | http://localhost:8585 | admin padrão OM | governança (profile) |

> Todas as credenciais vêm do `.env` na raiz (não versionado — está no `.gitignore`).

---

## 3. Pré-requisitos

- Docker + Docker Compose v2
- `.env` na raiz (com as credenciais; gere Fernet keys com
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)
- ~8 GB de RAM livres se for subir o OpenMetadata (ES + server são pesados)

---

## 4. Subir tudo

```bash
cd ~/Desktop/infra_mini_cloud_v4

# build das imagens custom (spark, jupyter, airflow)
docker compose build

# subir o stack (sem OpenMetadata)
docker compose up -d

# acompanhar até ficar tudo "healthy"
docker compose ps

# (opcional) incluir o OpenMetadata/governança
docker compose --profile governanca up -d
```

O `up` já faz a configuração inicial sozinho, via containers one-shot que rodam na
ordem certa (`depends_on` + `condition`):

| Container | O que faz | Quando |
|-----------|-----------|--------|
| `rustfs-init` | cria os buckets `bronze`, `silver`, `gold`, `poc` | RustFS healthy |
| `polaris-bootstrap` | cria o schema do Polaris no Postgres + principal `root` | antes do servidor Polaris |
| `polaris-init` | cria os catálogos `poc_catalog`, `bronze`, `silver`, `gold` + namespaces | Polaris healthy |
| `airflow-init` | migra o banco do Airflow | postgres+redis healthy |

As DAGs do Airflow sobem **despausadas** (`DAGS_ARE_PAUSED_AT_CREATION=false`).

Abra o Jupyter (http://localhost:8888, token `spark123`) e rode os notebooks.

### Ordem de carga (resumo)

```
1. rede infra-net criada
2. base sobe em paralelo: rustfs, polaris-postgres, spark-master→workers,
   airflow-postgres/redis
3. one-shot na ordem:
   rustfs healthy ─► rustfs-init (buckets)
   polaris-postgres healthy ─► polaris-bootstrap (schema) ─► polaris sobe
   polaris healthy + rustfs-init ok ─► polaris-init (catálogos)
   postgres+redis ─► airflow-init (migra BD)
4. apps sobem: jupyter, airflow (DAGs ativas)
```

---

## 5. Pipeline Iceberg / Polaris (no Spark/Jupyter)

A sessão Spark já carrega o `spark-defaults.conf` com os catálogos `polaris`,
`bronze`, `silver` e `gold` configurados:

```python
from pyspark.sql import SparkSession
spark = (SparkSession.builder
    .appName("Iceberg Polaris RustFS")
    .config("spark.sql.catalog.polaris.warehouse", "poc_catalog")
    .getOrCreate())
```

**Escrever** (use sempre `writeTo().createOrReplace()` — é idempotente):

```python
df = spark.createDataFrame([(1,"alpha"),(2,"beta")], ["id","nome"])
df.writeTo("polaris.equipe_dados.table_1").createOrReplace()
```

**Ler / inspecionar:**

```python
spark.table("polaris.equipe_dados.table_1").show()
spark.sql("SHOW NAMESPACES IN polaris").show()
```

### Arquitetura medallion (bronze / silver / gold)

Há **um catálogo Polaris por camada**, cada um no seu bucket: `bronze` →
`s3://bronze/`, `silver` → `s3://silver/`, `gold` → `s3://gold/` (namespace de
exemplo `vendas`). Cada camada lê da anterior e grava no próprio bucket:

```python
from pyspark.sql import functions as F

spark.table("bronze.vendas.pedidos") \
    .withColumn("cliente", F.initcap(F.trim("cliente"))) \
    .withColumn("valor", F.trim("valor").cast("double")) \
    .writeTo("silver.vendas.pedidos").createOrReplace()
```

> ⚠️ Não use `saveAsTable()` (quebra em re-execução com TABLE_ALREADY_EXISTS) nem
> escrita direta via `s3a://` (incompatível com o `iceberg-aws-bundle`).

---

## 6. Airflow → Spark → Polaris → RustFS

As DAGs `polaris_write` (escreve em `poc_catalog`) e `medallion_etl`
(bronze→silver→gold) submetem ao **cluster Spark** via
`spark-submit --master ${SPARK_MASTER}` (default `spark://spark-master:7077`).

- O **driver** roda no worker do Airflow (client mode); os **executors** rodam nos
  `spark-worker-1`/`spark-worker-2`.
- Os scripts (`services/airflow/airflow/dags/scripts/*.py`) definem toda a config do
  catálogo Polaris no código (o worker do Airflow não tem o `spark-defaults.conf`).
- **Fallback sem cluster:** `SPARK_MASTER=local[*]` faz o job rodar dentro do
  próprio worker do Airflow.

**Por que o stack inteiro está em Spark 4.1.2:** no modo standalone, o cliente
(`spark-submit`), o master e os workers precisam ser a **mesma versão** do Spark —
o protocolo RPC interno não é compatível entre versões. Por isso cluster, Jupyter
e worker do Airflow estão todos em **4.1.2 / Scala 2.13**, com Iceberg
`4.1_2.13:1.11.0` + `iceberg-aws-bundle:1.11.0` no classpath.

Disparar manualmente:

```bash
docker exec infra_mini_cloud_v4-airflow-scheduler-1 airflow dags trigger polaris_write
docker exec infra_mini_cloud_v4-airflow-scheduler-1 airflow dags list-runs polaris_write -o plain
```

---

## 7. OpenMetadata ↔ Polaris (governança + busca)

O OpenMetadata cataloga os metadados do Polaris via **conector Iceberg** (pyiceberg
REST). Sobe só com o profile: `docker compose --profile governanca up -d`.

> **Busca usa Elasticsearch 8.11.4, não OpenSearch.** O OM 1.6.6 com OpenSearch 2.11
> quebrava a busca de tabelas (`tableType`/`columnNames` mapeados como `text` →
> `500 all shards failed` no `table_search_index`). Trocamos o motor para
> `docker.elastic.co/elasticsearch/elasticsearch:8.11.4` + `SEARCH_TYPE=elasticsearch`
> (versão testada com o OM 1.6.6), que cria o mapping correto (`tableType` = `keyword`).

### Rodar a ingestion Polaris → OpenMetadata (automático)

Use o **`services/openmetadata/auto_ingest.sh`** — ele faz tudo sozinho, sem
copiar/colar token nenhum:

```bash
cd services/openmetadata && ./auto_ingest.sh
```

O script encadeia 4 passos:
1. pega o **JWT do ingestion-bot** via API do OM (login admin → `/bots/name/ingestion-bot`
   → `/users/token/{id}`) e grava no `iceberg-polaris.yaml` — esse JWT tem `exp: null`
   (não expira), por isso buscá-lo por API é confiável;
2. renova o **token do Polaris** (chama o `refresh_token.sh`) — esse expira em ~1h;
3. roda a **ingestion** (container `openmetadata/ingestion:1.6.6`);
4. faz o **reindex** da busca.

A tabela aparece em **Explore → Tables** (ex.: `Iceberg.default.equipe_dados.airflow_table`).

> O **`services/openmetadata/start.sh`** já faz isto no fim do boot: sobe o OM, reseta
> a senha do admin, **reindexa** e, se o Polaris estiver no ar, chama o `auto_ingest.sh`
> automaticamente (se o Polaris estiver fora, pula sem quebrar e avisa).

> Pré-requisitos: Polaris no ar (`http://localhost:8182/q/health` = 200) e **já com
> tabela** no catálogo (rode a DAG `polaris_write`/`medallion_etl` ou um notebook antes).
> Se o catálogo estiver vazio, a ingestion roda mas não traz nada.

### Quando preciso re-ingerir?

O OM cataloga **metadados** (estrutura), não o conteúdo das linhas:

| Situação | O que rodar |
|----------|-------------|
| Novas **linhas** numa tabela que já existe | nada — o metadado não mudou |
| **Tabela / coluna / namespace novo** ou mudança de schema | `./auto_ingest.sh` (já reindexa no fim) |
| Busca quebrada após `down -v` (índice zerado) | `reindex` — ou já vem no `auto_ingest.sh` |

### Manual (fallback, se o `auto_ingest.sh` falhar)

```bash
cd services/openmetadata
./refresh_token.sh           # renova só o token do Polaris no iceberg-polaris.yaml
# (cole o JWT do ingestion-bot — Settings → Bots → ingestion-bot na UI — no campo jwtToken)
docker run --rm --network infra-net \
  -v "$(pwd)/iceberg-polaris.yaml":/tmp/iceberg-polaris.yaml:ro \
  --entrypoint metadata openmetadata/ingestion:1.6.6 ingest -c /tmp/iceberg-polaris.yaml
```

### Se a busca falhar / a tabela não aparecer na busca (reindex)

A ingestion grava no Postgres do OM; a busca usa o Elasticsearch. Se a tabela existe
ao **navegar** mas não na **busca**, o índice está dessincronizado — reindexe:

```bash
docker exec openmetadata-server /opt/openmetadata/bootstrap/openmetadata-ops.sh reindex
```

Se a busca der **500** com `tableType is disabled (fielddata)`, o índice nasceu com
mapping errado. Apague-o por nome exato e reinicie o server (recria com o mapping
correto), depois reindexe:

```bash
curl -X DELETE "http://localhost:9201/table_search_index"
curl -X DELETE "http://localhost:9201/tag_search_index"
docker compose restart openmetadata-server     # recria os índices no boot
docker exec openmetadata-server /opt/openmetadata/bootstrap/openmetadata-ops.sh reindex
```

---

## 8. Polaris + RustFS — o que faz funcionar (troubleshooting)

1. **O catálogo precisa de 3 campos não-default** no `storageConfigInfo` (o
   `setup_polaris.sh` já faz):
   - `stsUnavailable: true` — impede o Polaris de chamar a AWS STS (RustFS não é
     AWS; STS daria 403).
   - `pathStyleAccess: true` — obrigatório para RustFS/MinIO (senão dá 301).
   - `endpoint: "http://rustfs:9000"` — endpoint S3 interno.
2. **Persistência em Postgres** (`polaris-postgres`, backend `relational-jdbc`):
   `POLARIS_PERSISTENCE_TYPE=relational-jdbc` + `QUARKUS_DATASOURCE_*`. O schema é
   criado uma vez pelo `polaris-bootstrap` (`apache/polaris-admin-tool`).
3. **No Spark, sempre `df.writeTo("cat.ns.tabela").createOrReplace()`**.

### Erros clássicos
- **STS 403 (`Failed to get subscoped credentials`)** → falta `stsUnavailable:true`
  no catálogo. A env `SKIP_CREDENTIAL_SUBSCOPING_INDIRECTION` sozinha **não** resolve.
- **S3 301 (redirect)** → falta `pathStyleAccess:true`.
- **`NoSuchMethodError ParserInterface.$init$`** → versão do Iceberg/Spark
  incompatível. Mantenha Spark 4.1 ↔ iceberg-spark-runtime-4.1_2.13.

---

## 9. Operações do dia a dia

```bash
docker compose ps                       # status
docker compose logs -f polaris          # logs de um serviço
docker compose restart polaris          # catálogo NÃO se perde (persiste no Postgres)
docker compose stop                     # parar (mantém dados)
docker compose up -d                    # subir de novo

# rodar o setup de catálogos na mão (idempotente)
docker compose up polaris-init
# ou, do host:
cd services/polaris && ./setup_polaris.sh && cd ../..
```

### Conferir que subiu

```bash
docker compose ps -a                    # one-shot devem estar "Exited (0)"
docker logs polaris-bootstrap           # "Realm 'POLARIS' successfully bootstrapped."
docker logs polaris-init                # HTTP 201/200 da criação dos catálogos
```

---

## 10. Teardown

```bash
# inclua --profile governanca se subiu o OpenMetadata
docker compose --profile governanca down -v --remove-orphans
```

Remove containers, rede e **todos os volumes** (`rustfs-data`,
`airflow-postgres-data`, `polaris-postgres-data`, `openmetadata_*`) → **perde os
dados**, inclusive o catálogo do Polaris. Para subir de novo, repita a Seção 4 — o
`up` refaz bootstrap, buckets e catálogos sozinho.

---

## 11. Pontos de atenção

- **Polaris persiste em Postgres** — catálogos sobrevivem ao restart (volume
  `polaris-postgres-data`; some só com `down -v`).
- **Spark roda no cluster** — versões alinhadas em 4.1.2 (ver Seção 6). Fallback:
  `SPARK_MASTER=local[*]`.
- **OpenMetadata** sob profile `governanca` — não sobe no `up` padrão. Usa
  **Elasticsearch 8.11.4** para a busca (não OpenSearch — ver Seção 7). Conexão com
  o Polaris pelo conector Iceberg; tokens expiram (renovar antes de reingerir).
- **Segredos** no `.env` (gitignored). Exceção conhecida:
  `spark-defaults.conf` e os scripts das DAGs ainda inlinam as credenciais locais
  do RustFS/Polaris (aceitável para uso local).

---

## 12. Estrutura do projeto

```
infra_mini_cloud_v4/
├── docker-compose.yml          # orquestra tudo via "extends" + profiles
├── .env                        # credenciais (gitignored)
├── .gitignore
├── README.md                   # este arquivo
└── services/
    ├── spark/                  # dockerfile (Spark 4.1.2) + spark-defaults.conf
    ├── jupyter/                # dockerfile + work/ (notebooks)
    ├── rustfs/                 # storage S3 (+ rustfs-init: buckets)
    ├── polaris/                # catálogo Iceberg + Postgres + bootstrap + setup_polaris.sh
    ├── airflow/                # orquestração (CeleryExecutor) + DAGs
    └── openmetadata/           # governança (profile governanca)


URL:    http://localhost:8585
Email:  admin@open-metadata.org
Senha:  admin
```
