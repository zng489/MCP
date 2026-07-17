# infra_mini_cloud_v5 — Documentação da Stack

Documentação consolidada da arquitetura, ordem de inicialização e runbooks operacionais.

---

## 1. Visão Geral

A stack é orquestrada por um `docker-compose.yml` raiz que sobe 7 serviços principais, cada um com seu próprio compose file em `services/<nome>/`:

| Serviço | Função |
|---|---|
| `polaris` | Catálogo Iceberg (REST Catalog) |
| `openmetadata` | Catálogo de metadados / descoberta de dados |
| `rustfs` | Object storage S3-compatível |
| `spark` | Processamento distribuído (master + workers) |
| `jupyter` | Notebook para exploração/ingestão de dados |
| `airflow` | Orquestração de pipelines |
| (rede) `infra-net` | Rede Docker compartilhada entre todos os serviços |

Todos os serviços ficam na mesma rede `infra-net`, então **dentro dos containers** o nome do serviço funciona como hostname (ex: `polaris`, `rustfs`, `openmetadata-server`). **No host**, usa-se `localhost` com a porta exposta.

---

## 2. Ordem de Inicialização (`docker compose up -d`)

O Compose resolve `depends_on` + healthchecks e sobe em camadas:

### Camada 1 — Sem dependências (sobem em paralelo)

- `openmetadata-postgres`
- `om-elasticsearch`
- `spark-master`, `spark-worker-1`, `spark-worker-2`
- `jupyter`
- `airflow-postgres`, `airflow-redis`
- `polaris-postgres`
- `rustfs`

### Camada 2 — Esperam healthcheck da Camada 1

| Serviço | Espera por | Faz |
|---|---|---|
| `openmetadata-migrate` | `openmetadata-postgres` healthy | Migra o schema (`openmetadata-ops.sh migrate`) |
| `polaris-bootstrap` | `polaris-postgres` healthy | Cria schema + root principal (`bootstrap --realm=POLARIS`) |
| `rustfs-init` | `rustfs` healthy | Cria buckets `bronze`, `silver`, `gold`, `poc` |
| `airflow-init` | `airflow-postgres` + `airflow-redis` healthy | Inicializa o Airflow |

### Camada 3 — Esperam Camada 2 completar

| Serviço | Espera por | Faz |
|---|---|---|
| `openmetadata-server` | postgres + elasticsearch healthy + migrate completed | Servidor OpenMetadata (porta `8585`) |
| `polaris` | postgres healthy + bootstrap completed | Servidor Polaris (porta `8181`) |
| `airflow-apiserver`, `airflow-scheduler`, `airflow-dag-processor`, `airflow-triggerer`, `flower` | airflow-init completed | API/scheduler/monitor do Airflow (porta `8090`) |

### Camada 4 — Esperam Camada 3

| Serviço | Espera por | Faz |
|---|---|---|
| `polaris-init` | `polaris` healthy + `rustfs-init` completed | Roda `setup_polaris.sh`: gera token, cria catálogo `catalogo_cepel`, cria namespace `equipe_dados` |
| `airflow-worker` | `airflow-apiserver` healthy + `airflow-init` completed | Workers Celery |

### Diagrama da cadeia (Polaris)

```
polaris-postgres (healthy)
  └─> polaris-bootstrap (apache/polaris-admin-tool)
        └─> polaris (servidor, healthy, porta 8181)
              └─> polaris-init (one-shot)
                    runs setup_polaris.sh:
                      1. POST /oauth/tokens      → gera token
                      2. create_catalog catalogo_cepel (bucket=poc)
                      3. create_namespace catalogo_cepel.equipe_dados
```

### Diagrama da cadeia (OpenMetadata)

```
openmetadata-postgres (healthy) + om-elasticsearch (healthy)
  └─> openmetadata-migrate (one-shot)
        ./bootstrap/openmetadata-ops.sh migrate
        └─> openmetadata-server (porta 8585, healthy)
```

---

## 3. Scripts manuais (NÃO sobem com `docker compose up -d`)

Estes scripts existem mas precisam ser executados manualmente:

| Script | Local | Quando usar |
|---|---|---|
| `start.sh` | `services/openmetadata/` | Reset completo: `down -v`, sobe tudo, reseta senha admin, reindexa, tenta ingestion |
| `auto_ingest.sh` | `services/openmetadata/` | Ingestion dinâmica Polaris → OpenMetadata (todos os catálogos) |
| `refresh_token.sh` | `services/openmetadata/` | Renova o token do Polaris (expira a cada ~1h) |
| `openmetadata.sh` | `services/openmetadata/` | Bloco de referência com comandos SQL (não é executável) |

> ⚠️ **Importante:** `start.sh` faz seu próprio `docker compose down -v` + `up -d` de dentro de `services/openmetadata/`. Se rodado assim, ele usa o compose local **sem** as variáveis do `.env` da raiz (`OM_POSTGRES_USER`, `OM_POSTGRES_PASSWORD`, `OM_FERNET_KEY`), o que causa falha. Para evitar isso, suba a stack pela raiz do projeto e rode os passos manuais separadamente (ver seção 5), ou exporte as variáveis do `.env` antes de chamar `start.sh`:
> ```bash
> cd services/openmetadata
> env $(grep -v '^#' ../../.env | xargs) ./start.sh
> ```

---

## 4. CLI do Polaris

O Polaris não tem CLI embutida no servidor — existe um pacote Python oficial **`apache-polaris`** publicado no PyPI (wheel pronto, sem precisar compilar nada).

### Restrição de versão

`apache-polaris` exige `Python >=3.10,<3.14`. Se o host tiver Python 3.14 (caso comum em distros recentes), a instalação falha. Soluções, em ordem de praticidade:

1. **Instalar dentro do Jupyter** (já tem Python compatível, 3.10–3.12, e está na rede `infra-net`):
   ```bash
   docker exec jupyter pip install apache-polaris==1.5.0
   ```
2. Container Python 3.13 dedicado, via Docker.
3. `pipx`/venv local com Python 3.13 (se disponível nos repos da distro).

### Uso básico (de dentro do Jupyter)

```bash
docker exec jupyter polaris \
  --host polaris --port 8181 \
  --client-id root --client-secret s3cr3t \
  catalogs list
```

> No terminal do Jupyter ou em uma célula de notebook (`!comando`), o host é `polaris` (nome do container), não `localhost` — porque o Jupyter já está dentro da rede Docker.
>
> Do **host** (fora de containers), seria `--host localhost`.

### Criar um catálogo novo

```bash
polaris --host polaris --port 8181 --client-id root --client-secret s3cr3t \
  catalogs create --type INTERNAL --name meu_catalogo \
  --storage-type S3 \
  --default-base-location s3://meu-bucket/ \
  --allowed-location s3://meu-bucket/ \
  --endpoint http://rustfs:9000 \
  --region us-east-1 \
  --path-style-access \
  --sts-unavailable
```

`--path-style-access` e `--sts-unavailable` são obrigatórias para compatibilidade com RustFS/MinIO.

### Criar um namespace (a CLI não tem subcomando para isso — usa-se a API REST direto)

```bash
TOKEN=$(curl -s -X POST http://polaris:8181/api/catalog/v1/oauth/tokens \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'grant_type=client_credentials&client_id=root&client_secret=s3cr3t&scope=PRINCIPAL_ROLE:ALL' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

curl -s -X POST http://polaris:8181/api/catalog/v1/<catalogo>/namespaces \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"namespace":["<nome_namespace>"]}'
```

### Listar catálogos e namespaces (script Python completo)

```python
import requests

url = "http://polaris:8181"

token = requests.post(f"{url}/api/catalog/v1/oauth/tokens", data={
    "grant_type": "client_credentials",
    "client_id": "root",
    "client_secret": "s3cr3t",
    "scope": "PRINCIPAL_ROLE:ALL"
}).json()["access_token"]

headers = {"Authorization": f"Bearer {token}"}

catalogs = requests.get(f"{url}/api/management/v1/catalogs", headers=headers).json()

for cat in catalogs.get("catalogs", []):
    name = cat["name"]
    print(f"\n=== Catálogo: {name} ===")
    ns = requests.get(f"{url}/api/catalog/v1/{name}/namespaces", headers=headers).json()
    for n in ns.get("namespaces", []):
        print(f"  namespace: {'.'.join(n)}")
```

---

## 5. Setup do OpenMetadata (passo a passo)

Depois que `docker compose up -d` (na **raiz** do projeto) terminar e `openmetadata-server` estiver `healthy`:

### Passo 1 — Resetar a senha do admin

Necessário porque, ao subir do zero (`down -v`), o volume do Postgres é recriado e a senha gerada não bate com `admin`.

```bash
HASH=$(python3 -c "import bcrypt; print(bcrypt.hashpw(b'admin', bcrypt.gensalt()).decode())")

cat > /tmp/reset.sql << EOF
UPDATE user_entity
SET json = jsonb_set(
  json::jsonb,
  '{authenticationMechanism,config,password}',
  '"$HASH"'
)
WHERE json->>'email' = 'admin@open-metadata.org';
EOF

docker exec -i openmetadata-postgres psql -U om_user -d openmetadata_db < /tmp/reset.sql
docker restart openmetadata-server
```

### Passo 2 — Esperar voltar `healthy`

```bash
until docker inspect openmetadata-server --format='{{.State.Health.Status}}' | grep -q "healthy"; do
  echo "aguardando..."
  sleep 10
done
echo "pronto!"
```

### Passo 3 — Reindexar a busca (Elasticsearch)

Necessário porque o volume do Elasticsearch também foi apagado no `down -v`. Sem isso, o Postgres tem os dados mas o Explore/Search fica vazio.

```bash
docker exec openmetadata-server /opt/openmetadata/bootstrap/openmetadata-ops.sh reindex
```

### Passo 4 — Login

```
URL:    http://localhost:8585
Email:  admin@open-metadata.org
Senha:  admin
```

### Passo 5 — Ingestion (Polaris → OpenMetadata)

O OpenMetadata não descobre tabelas por conta própria — ele precisa de um workflow de ingestion que conecta no Polaris, lista catálogos/namespaces/tabelas, e registra tudo.

```bash
cd services/openmetadata
chmod +x auto_ingest.sh
./auto_ingest.sh
```

O `auto_ingest.sh` (versão dinâmica, sem YAMLs estáticos) faz:

1. Login admin no OpenMetadata → pega o JWT do `ingestion-bot`
2. Gera token do Polaris (`client_id=root`, `client_secret=s3cr3t`)
3. **Descobre dinamicamente** todos os catálogos existentes no Polaris via API
4. Para cada catálogo, gera um YAML de ingestion temporário e roda o container `openmetadata/ingestion:1.6.6`
5. Reindexa a busca no final

> Vantagem da versão dinâmica: não é preciso manter um arquivo `.yaml` por catálogo (como era o caso de `iceberg-polaris.yaml` e `iceberg-bronze.yaml`). Sempre que um catálogo novo for criado no Polaris, basta rodar `./auto_ingest.sh` de novo.

**Pegadinhas resolvidas durante o setup:**

| Problema | Causa | Correção |
|---|---|---|
| `JSONDecodeError` ao buscar token do Polaris | Script rodando no host tentando resolver `polaris:8181` (hostname Docker interno, não resolve fora da rede) | Usar `localhost:8181` para chamadas do host; manter `polaris:8181` apenas dentro do YAML que roda em container na rede `infra-net` |
| `Permission denied: '/ingest.yaml'` | `mktemp` cria arquivo com permissão `600`; o container de ingestion roda com outro usuário | `chmod 644` no YAML temporário antes de montar o volume |

---

## 6. Conectando o Spark ao Polaris

### Padrão de nomenclatura — ponto crítico

| Termo | O que é | Exemplo |
|---|---|---|
| **Catálogo Polaris** | Warehouse registrado no Polaris (storage S3 + bucket) | `catalogo_cepel` |
| **Catálogo Spark** | Nome do catálogo configurado em `spark-defaults.conf`, que aponta para um warehouse do Polaris | `polaris`, `bronze`, `silver`, `gold` |

O Spark **não conhece** o nome do catálogo Polaris diretamente — ele só conhece os catálogos Spark configurados em `spark-defaults.conf`. Cada catálogo Spark tem uma propriedade `warehouse` que aponta para o warehouse correspondente no Polaris.

### Erro comum

```python
bronze.writeTo("catalogo_cepel.equipe_dados.pedidos").createOrReplace()
# AnalysisException: [REQUIRES_SINGLE_PART_NAMESPACE] spark_catalog requires
# a single-part namespace, but got `catalogo_cepel`.`equipe_dados`.
```

Isso acontece porque `catalogo_cepel` não é um catálogo Spark registrado — o Spark cai no catálogo padrão (`spark_catalog`), que exige namespace de uma parte só.

### Correção

```python
# 1. Aponta o catálogo Spark "polaris" para o warehouse "catalogo_cepel" do Polaris
spark.conf.set("spark.sql.catalog.polaris.warehouse", "catalogo_cepel")

# 2. Usa o NOME DO CATÁLOGO SPARK (polaris), não o nome do warehouse Polaris
bronze.writeTo("polaris.equipe_dados.pedidos").createOrReplace()
spark.table("polaris.equipe_dados.pedidos").show(truncate=False)
```

**Regra geral:** o caminho é sempre `<catálogo_spark>.<namespace>.<tabela>` — onde `<catálogo_spark>` é o nome configurado em `spark-defaults.conf` (ex: `polaris`), nunca o nome do warehouse no Polaris.

---

## 7. Comandos úteis do dia a dia

### Status dos serviços

```bash
docker ps --filter "name=polaris" --format "table {{.Names}}\t{{.Status}}"
docker ps --filter "name=spark" --format "table {{.Names}}\t{{.Status}}"
```

### Spark UI (ver workers conectados)

```
http://localhost:8080
```

### Apagar tudo (containers, volumes, redes) — irreversível

```bash
docker compose down -v --remove-orphans
docker volume prune -f
docker network prune -f
```

> Use com cuidado: apaga dados do Postgres, Elasticsearch e RustFS permanentemente.

---

## 8. Credenciais padrão

| Serviço | Usuário/Client ID | Senha/Secret |
|---|---|---|
| Polaris (root) | `root` | `s3cr3t` |
| OpenMetadata | `admin@open-metadata.org` | `admin` |

> Credenciais de exemplo/desenvolvimento — trocar antes de qualquer uso em produção.

---

## 9. Resumo do fluxo ponta a ponta

```
1. docker compose up -d (raiz)
   → sobe Postgres/Elasticsearch/Spark/Jupyter/Airflow/Polaris/RustFS
   → polaris-init cria catálogo "catalogo_cepel" + namespace "equipe_dados"

2. Spark grava dados via Iceberg
   spark.conf.set("spark.sql.catalog.polaris.warehouse", "catalogo_cepel")
   df.writeTo("polaris.equipe_dados.pedidos").createOrReplace()
   → arquivos Parquet aparecem no RustFS (bucket poc/equipe_dados/pedidos/)

3. Setup do OpenMetadata (services/openmetadata/)
   - reset de senha admin
   - aguardar healthy
   - reindex do Elasticsearch
   - ./auto_ingest.sh → descobre catálogos no Polaris e registra no OpenMetadata

4. http://localhost:8585 → Explore → Tables
   → tabela "pedidos" aparece com schema, linhagem e metadados
```
