# JupyterHub + Controle de Acesso (Polaris ACL)

## Visao geral

O JupyterHub substitui o Jupyter single-user e fornece:

- **Login individual** por usuario (porta 8888)
- **Notebooks isolados** — cada usuario recebe seu proprio container
- **Controle de acesso** — o Polaris decide quem pode ler/escrever com base no perfil do usuario

```
Usuario -> login no JupyterHub (porta 8888)
               |
               +-- admin              -> container com root:s3cr3t (ACESSO TOTAL)
               +-- grupo "engenheiros"-> container com credencial de ESCRITA
               +-- grupo "analistas"  -> container com credencial de LEITURA
                         |
                         v
                    infra-net (polaris, spark-master, rustfs...)
```

## Arquitetura de acesso

O controle de acesso funciona em 3 camadas:

```
1. JupyterHub    -> autentica o usuario (login/senha)
2. Perfil        -> determina qual spark-defaults.conf e montado (admin/engenheiro/analista)
3. Polaris       -> valida a credencial e aplica as permissoes (ler/escrever/tudo)
```

O Spark e apenas o motor de processamento — quem decide se pode ou nao e o Polaris.
O Spark nao tem controle de acesso proprio. Ele manda a credencial ao Polaris,
e o Polaris aceita ou rejeita com base nos roles/grants configurados.

## 3 niveis de acesso

| Nivel | Credencial Polaris | spark-defaults usado | Pode fazer |
|-------|-------------------|---------------------|-----------|
| Admin | `root:s3cr3t` | `spark-defaults-admin.conf` | Tudo (criar/dropar catalogos, tabelas, dados) |
| Engenheiro | `spark_user:secret` | `spark-defaults-engenheiro.conf` | Ler + escrever tabelas (nao gerencia catalogos) |
| Analista | `analista:secret` | `spark-defaults-analista.conf` | Somente leitura (SELECT) |

### Regra de selecao de credencial

```
Usuario e admin no JupyterHub?  -> root:s3cr3t (acesso total)
Usuario no grupo "engenheiros"? -> spark_user (leitura + escrita)
Qualquer outro caso             -> analista (somente leitura)
```

Usuarios sem grupo recebem o perfil de **analista** por padrao (principio do menor privilegio).

## Principals e roles no Polaris

Criados pelo script `services/polaris/setup_acl.sh`:

| Principal | Principal Role | Permissao |
|-----------|---------------|-----------|
| `root` | `ALL` | Admin total (gerencia catalogos, tabelas, tudo) |
| `spark_user` | `etl_role` | Leitura + escrita (SELECT, CREATE, DROP, INSERT) |
| `airflow_user` | `etl_role` | Leitura + escrita (servico) |
| `analista` | `leitor_role` | Somente leitura (SELECT) |

### Catalog roles (catalogo_cepel)

| Catalog Role | Privileges |
|-------------|-----------|
| `cepel_leitor` | NAMESPACE_LIST, TABLE_LIST, TABLE_READ_PROPERTIES, TABLE_READ_DATA |
| `cepel_escritor` | Tudo acima + NAMESPACE_CREATE, TABLE_CREATE, TABLE_DROP, TABLE_WRITE_PROPERTIES, TABLE_WRITE_DATA |

### Ligacao entre principals, roles e catalog roles

```
root         -> ALL          -> acesso total (nao precisa de catalog role)
spark_user   -> etl_role     -> cepel_escritor (le + escreve)
airflow_user -> etl_role     -> cepel_escritor (le + escreve)
analista     -> leitor_role  -> cepel_leitor   (so le)
```

## Grupos no JupyterHub

| Grupo | spark-defaults.conf usado | Credencial Polaris | Pode fazer |
|-------|--------------------------|-------------------|-----------|
| (admin) | `spark-defaults-admin.conf` | `root` (ALL) | Tudo |
| `engenheiros` | `spark-defaults-engenheiro.conf` | `spark_user` (etl_role) | SELECT, CREATE, DROP, INSERT |
| `analistas` | `spark-defaults-analista.conf` | `analista` (leitor_role) | SELECT |

## Exemplo pratico

**Admin** no Jupyter:
```sql
SELECT * FROM catalogo_cepel.equipe_dados.tabela   -- funciona
DROP TABLE catalogo_cepel.equipe_dados.tabela      -- funciona
CREATE TABLE catalogo_cepel.equipe_dados.nova (...) -- funciona
-- pode tambem criar/dropar catalogos e namespaces
```

**Engenheiro** no Jupyter:
```sql
SELECT * FROM catalogo_cepel.equipe_dados.tabela   -- funciona
DROP TABLE catalogo_cepel.equipe_dados.tabela      -- funciona
CREATE TABLE catalogo_cepel.equipe_dados.nova (...) -- funciona
-- NAO pode criar/dropar catalogos
```

**Analista** no Jupyter:
```sql
SELECT * FROM catalogo_cepel.equipe_dados.tabela   -- funciona
DROP TABLE catalogo_cepel.equipe_dados.tabela      -- 403 Forbidden
CREATE TABLE catalogo_cepel.equipe_dados.nova (...) -- 403 Forbidden
```

## Arquivos do JupyterHub

```
services/jupyterhub/
  dockerfile                       # Imagem do Hub (JupyterHub + DockerSpawner + NativeAuthenticator)
  jupyterhub_config.py             # Config central (auth, spawner, grupos, idle culler)
  docker-compose.yml               # Servico na porta 8888 com Docker socket
  spark-defaults-admin.conf        # Spark config com root:s3cr3t (acesso total)
  spark-defaults-engenheiro.conf   # Spark config com credencial de escrita
  spark-defaults-analista.conf     # Spark config com credencial de leitura
  generate-spark-configs.sh        # Gera analista/engenheiro a partir do .env

services/jupyter/
  dockerfile                       # Imagem base dos notebooks (Spark + Iceberg + JupyterLab)
                                   # Usada pelo DockerSpawner para criar containers dos usuarios
  docker-compose.yml               # NAO USADO — pode ser removido (era do Jupyter antigo)
```

## Como funciona o DockerSpawner

1. Usuario faz login no JupyterHub (porta 8888)
2. O `pre_spawn_hook` verifica se e admin, qual grupo pertence, ou nenhum
3. Monta o `spark-defaults.conf` correto (admin, engenheiro ou analista) no container
4. Cria um container `jupyter-{username}` na rede `infra-net`
5. O container usa a imagem `jupyter:dev` (Spark 4.1.2 + Iceberg 1.11.0 + JupyterLab)
6. Quando o usuario faz logout ou fica ocioso por 1h, o container e removido
7. Os dados do usuario persistem no volume `jupyterhub-user-{username}`

## Isolamento de dados (volumes)

Cada usuario recebe um **volume Docker isolado** montado em `/home/jovyan/work`:

```
jupyterhub-user-admin         -> /home/jovyan/work  (so dele)
jupyterhub-user-analista01    -> /home/jovyan/work  (so dele)
jupyterhub-user-engenheiro01  -> /home/jovyan/work  (so dele)
jupyterhub-user-joao          -> /home/jovyan/work  (so dele)
```

- **Nao ha pastas compartilhadas** — ninguem ve o notebook do outro
- O volume e criado automaticamente no primeiro login (comeca vazio)
- O volume **persiste** mesmo quando o container e destruido (logout/idle)
- Na proxima vez que o usuario logar, seus notebooks continuam la

Diferenca do Jupyter antigo:

| | Jupyter antigo | JupyterHub |
|---|---|---|
| Volume | Pasta do host (`./work`) compartilhada | Volume Docker por usuario (isolado) |
| Acesso ao host | Sim (perigoso) | Nao |
| Um apaga arquivo do outro? | Sim | Nao |
| Container roda como root? | Sim (`user: "0:0"`) | Nao (roda como `jovyan`) |

## Spark e Workers

Os containers do JupyterHub sao **clientes Spark** (drivers), nao workers.
Cada notebook se conecta ao mesmo cluster Spark existente:

```
jupyter-admin        ─┐
jupyter-analista01    ├──> spark-master:7077 ──> spark-worker-1, spark-worker-2
jupyter-engenheiro01  │
jupyter-joao         ─┘
```

O processamento roda nos workers. O notebook envia os jobs via `SPARK_MASTER`.
A unica diferenca entre os containers e a **credencial Polaris** no spark-defaults.conf.

### Uso simultaneo

Por padrao, cada SparkSession tenta reservar **todos** os cores do cluster.
Se um usuario ja esta conectado, o segundo fica em fila esperando recursos.

Para permitir uso simultaneo, cada role tem limites de recurso no `spark-defaults`:

| Role | `spark.cores.max` | `spark.executor.memory` | `spark.driver.memory` |
|------|-------------------|------------------------|-----------------------|
| Analista | 1 | 512m | 512m |
| Engenheiro | 1 | 512m | 512m |
| Admin | 1 | 512m | 512m |

Os workers estao configurados com:

| Worker | Cores | Memoria |
|--------|-------|---------|
| spark-worker-1 | 1 | 1g |
| spark-worker-2 | 1 | 1g |
| **Total cluster** | **2** | **2g** |

Isso permite **2 sessoes simultaneas**, cada uma usando 1 worker (1 core + 512m).
A configuracao e leve (maquina de 11GB/6 cores) e suficiente pra testes com dados pequenos.

Para ajustar os limites:
- **Workers**: editar `SPARK_WORKER_CORES` e `SPARK_WORKER_MEMORY` em `services/spark/docker-compose.yml`
- **Por role**: editar o bloco de limites no topo de cada `spark-defaults-*.conf` em `services/jupyterhub/`
- Aplicar: `docker compose up -d --no-deps spark-worker-1 spark-worker-2` e reiniciar os servers dos usuarios no JupyterHub

## Relacao com outros servicos

O JupyterHub **nao afeta** o funcionamento do Airflow, Polaris e OpenMetadata:

```
┌────────────────────────────────────────────────────────────────┐
│                          POLARIS                               │
│                                                                │
│   Quem acessa?              Credencial         Permissao       │
│                                                                │
│   JupyterHub (admin)      → root:s3cr3t      → ACESSO TOTAL   │
│   JupyterHub (engenheiro) → spark_user:secret→ LE + ESCREVE   │
│   JupyterHub (analista)   → analista:secret  → SO LE          │
│   Airflow (DAGs)          → root:s3cr3t      → ACESSO TOTAL   │
│   OpenMetadata (ingestion)→ root:s3cr3t      → ACESSO TOTAL   │
│   Spark cluster (workers) → NAO acessa Polaris diretamente    │
└────────────────────────────────────────────────────────────────┘
```

- **Airflow**: continua usando `root:s3cr3t` nos DAGs via `spark-defaults.conf` do cluster.
  Opcionalmente pode ser migrado para `airflow_user` (credencial dedicada com etl_role).
- **OpenMetadata**: continua usando `root:s3cr3t` nos scripts de ingestion (`auto_ingest.sh`).
- **Spark cluster**: `spark-defaults.conf` do cluster (em `services/spark/`) nao foi alterado.
  Continua com `root:s3cr3t`. Apenas os notebooks do JupyterHub usam configs diferentes.

## Limites por usuario

### Container Jupyter (JupyterHub)

| Recurso | Limite |
|---------|--------|
| RAM | 4 GB |
| CPU | 2 cores |
| Idle timeout | 1 hora (desliga automaticamente) |
| Tempo maximo | 8 horas |

Configuravel em `jupyterhub_config.py` via `c.DockerSpawner.mem_limit` e `c.DockerSpawner.cpu_limit`.

### Sessao Spark (por role)

| Recurso | Analista | Engenheiro | Admin |
|---------|----------|------------|-------|
| Cores max | 1 | 1 | 1 |
| Executor memory | 512m | 512m | 512m |
| Driver memory | 512m | 512m | 512m |

Configuravel nos arquivos `spark-defaults-*.conf` em `services/jupyterhub/`.
Esses limites garantem que multiplos usuarios possam usar o cluster Spark ao mesmo tempo.

## Deploy inicial

### 1. Criar principals/roles no Polaris

```bash
cd ~/docker-apps/infra_mini_cloud_v5/services/polaris
bash setup_acl.sh
```

Salvar as credenciais impressas (client_id e client_secret de cada principal).
As credenciais so aparecem uma vez — se perder, precisa recriar o principal.

### 2. Colar credenciais no .env

Editar `~/docker-apps/infra_mini_cloud_v5/.env` e substituir os placeholders:

```env
POLARIS_ANALISTA_CLIENT_ID=<client_id do analista>
POLARIS_ANALISTA_CLIENT_SECRET=<client_secret do analista>
POLARIS_ENGENHEIRO_CLIENT_ID=<client_id do spark_user>
POLARIS_ENGENHEIRO_CLIENT_SECRET=<client_secret do spark_user>
POLARIS_AIRFLOW_CLIENT_ID=<client_id do airflow_user>
POLARIS_AIRFLOW_CLIENT_SECRET=<client_secret do airflow_user>
```

### 3. Gerar spark-defaults por perfil

```bash
cd ~/docker-apps/infra_mini_cloud_v5/services/jupyterhub
bash generate-spark-configs.sh
```

Isso gera `spark-defaults-analista.conf` e `spark-defaults-engenheiro.conf` a partir
do `spark-defaults.conf` original, substituindo `root:s3cr3t` pelas credenciais do `.env`.
O `spark-defaults-admin.conf` e uma copia direta do original (ja usa `root:s3cr3t`).

### 4. Build das imagens

```bash
cd ~/docker-apps/infra_mini_cloud_v5

# Rebuild jupyter:dev (adicionou jupyterhub ao pip install)
cd services/jupyter && docker build -t jupyter:dev .

# Build jupyterhub:dev (Hub + DockerSpawner + NativeAuth)
cd ../.. && docker compose build jupyterhub
```

### 5. Subir o JupyterHub

```bash
docker compose up -d jupyterhub
```

### 6. Criar usuario admin

Acessar `http://<IP>:8888/hub/signup` e cadastrar o usuario `admin` com uma senha.
O usuario `admin` esta pre-configurado como administrador no `jupyterhub_config.py`.

### 7. Criar grupos e usuarios

Via API (usando o token de setup definido no `jupyterhub_config.py`):

```bash
TOKEN="setup-token-infra-mini-cloud-v5"
URL="http://localhost:8888/hub/api"

# Criar grupos
curl -X POST ${URL}/groups/analistas   -H "Authorization: token ${TOKEN}"
curl -X POST ${URL}/groups/engenheiros -H "Authorization: token ${TOKEN}"

# Criar usuario
curl -X POST ${URL}/users/joao -H "Authorization: token ${TOKEN}"

# Atribuir a grupo
curl -X POST ${URL}/groups/analistas/users \
  -H "Authorization: token ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"users":["joao"]}'
```

### 8. Cadastrar senha do usuario

O usuario precisa acessar `http://<IP>:8888/hub/signup` e definir sua senha.
Apos o signup, um admin deve autorizar o usuario (via UI em `/hub/authorize`
ou diretamente no banco SQLite do JupyterHub).

Autorizacao via banco (caso necessario):

```bash
docker exec jupyterhub python3 -c "
import sqlite3
db = sqlite3.connect('/srv/jupyterhub/jupyterhub.sqlite')
db.execute(\"UPDATE users_info SET is_authorized = 1 WHERE username = 'joao'\")
db.commit()
"
```

## Gerenciamento de usuarios

### Adicionar usuario novo

1. Criar via API: `POST /hub/api/users/{username}`
2. Atribuir a grupo: `POST /hub/api/groups/{grupo}/users`
3. Usuario faz signup em `/hub/signup` para definir senha
4. Admin autoriza (via UI do JupyterHub em `/hub/authorize` ou via banco)

### Remover usuario

```bash
curl -X DELETE ${URL}/users/joao -H "Authorization: token ${TOKEN}"
```

O volume `jupyterhub-user-joao` nao e removido automaticamente.
Para remover os dados do usuario:

```bash
docker volume rm jupyterhub-user-joao
```

### Mudar grupo de um usuario

```bash
# Remover do grupo atual
curl -X DELETE ${URL}/groups/analistas/users \
  -H "Authorization: token ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"users":["joao"]}'

# Adicionar ao novo grupo
curl -X POST ${URL}/groups/engenheiros/users \
  -H "Authorization: token ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"users":["joao"]}'
```

O usuario precisa **reiniciar seu notebook** para pegar o novo spark-defaults.
Parar o server do usuario:

```bash
curl -X DELETE ${URL}/users/joao/server -H "Authorization: token ${TOKEN}"
```

No proximo login, o container sera recriado com o spark-defaults do novo grupo.

### Promover usuario a admin

```bash
curl -X PATCH ${URL}/users/joao \
  -H "Authorization: token ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"admin": true}'
```

O usuario passa a receber `spark-defaults-admin.conf` (root:s3cr3t, acesso total)
e pode gerenciar outros usuarios no JupyterHub.

### Listar usuarios e grupos

```bash
# Todos os usuarios
curl -s ${URL}/users -H "Authorization: token ${TOKEN}" | python3 -m json.tool

# Todos os grupos
curl -s ${URL}/groups -H "Authorization: token ${TOKEN}" | python3 -m json.tool
```

## Credenciais de acesso

| Servico | URL | Usuario | Senha |
|---------|-----|---------|-------|
| JupyterHub | http://localhost:8888 | admin | admin12345 |
| JupyterHub | http://localhost:8888 | analista01 | analista123 |
| JupyterHub | http://localhost:8888 | engenheiro01 | engenheiro123 |
| Airflow | http://localhost:8090 | airflow | airflow |
| Polaris | http://localhost:8181 | root | s3cr3t |
| RustFS | http://localhost:9001 | rustfs | rustfs123 |
| OpenMetadata | http://localhost:8585 | admin@open-metadata.org | admin |

## Tokens e expiracao

| Token | Expira | Como renovar |
|-------|--------|--------------|
| Polaris OAuth (analista/spark_user) | ~1 hora | Spark renova automaticamente via REST |
| Polaris OAuth (root) | ~1 hora | Spark renova automaticamente via REST |
| JupyterHub session | 30 dias | Refaz login |
| API token (setup) | Nao expira | Definido no jupyterhub_config.py |

## Troubleshooting

### Usuario nao consegue logar

1. Verificar se fez signup: o usuario precisa se cadastrar em `/hub/signup`
2. Verificar se esta autorizado: `is_authorized` deve ser `1` no banco
   ```bash
   docker exec jupyterhub python3 -c "
   import sqlite3
   db = sqlite3.connect('/srv/jupyterhub/jupyterhub.sqlite')
   for r in db.execute('SELECT username, is_authorized FROM users_info').fetchall():
       print(r)
   "
   ```
3. Verificar logs: `docker logs jupyterhub 2>&1 | grep <username>`

### Container do usuario nao sobe

1. Verificar imagem: `docker images jupyter:dev` — deve existir e ter jupyterhub instalado
   ```bash
   docker run --rm jupyter:dev pip show jupyterhub
   ```
2. Verificar rede: `docker network inspect infra-net` — deve existir
3. Verificar spark-defaults: os 3 arquivos devem existir em `services/jupyterhub/`
   ```bash
   ls -la services/jupyterhub/spark-defaults-*.conf
   ```
4. Verificar logs: `docker logs jupyterhub 2>&1 | grep -i error`

### Polaris retorna 403

1. **Credencial errada**: verificar se o `spark-defaults-*.conf` tem a credencial correta
   ```bash
   grep "credential" services/jupyterhub/spark-defaults-analista.conf
   ```
2. **Permissao nao existe**: rodar `setup_acl.sh` novamente (idempotente, retorna 409 nos existentes)
3. **Token expirado**: o Spark renova automaticamente via REST. Se usar curl manualmente, gere novo token

### Regenerar credenciais do Polaris

Se as credenciais foram perdidas, os principals precisam ser recriados no Polaris
(nao ha como recuperar o client_secret). Passos:

1. Deletar os principals antigos no Polaris (ou recriar o banco)
2. Rodar `setup_acl.sh` novamente
3. Atualizar o `.env` com as novas credenciais
4. Rodar `generate-spark-configs.sh`
5. Reiniciar o JupyterHub: `docker compose restart jupyterhub`

### Atualizar config do JupyterHub

O `jupyterhub_config.py` e copiado para dentro da imagem no build,
mas o volume `jupyterhub-data` pode sobrescrever. Para aplicar mudancas:

```bash
# Copiar config atualizado para o container
docker cp services/jupyterhub/jupyterhub_config.py jupyterhub:/srv/jupyterhub/jupyterhub_config.py

# Reiniciar
docker compose restart jupyterhub
```

## Subindo tudo do zero

Sequencia completa para subir toda a stack desde o inicio:

```bash
cd ~/docker-apps/infra_mini_cloud_v5

# ── 1. Build das imagens ──────────────────────────────────────────
cd services/jupyter && docker build -t jupyter:dev .
cd ../..
docker compose build

# ── 2. Subir a infra base ─────────────────────────────────────────
docker compose up -d
# Aguardar tudo ficar healthy:
docker compose ps

# ── 3. Criar ACL no Polaris ───────────────────────────────────────
cd services/polaris
bash setup_acl.sh
# ANOTAR as credenciais impressas (client_id e client_secret)

# ── 4. Colar credenciais no .env ──────────────────────────────────
cd ../..
# Editar .env e substituir os PLACEHOLDER_RUN_SETUP_ACL pelos valores reais

# ── 5. Gerar spark-defaults por perfil ────────────────────────────
cd services/jupyterhub
bash generate-spark-configs.sh

# ── 6. Reiniciar JupyterHub (para pegar os novos configs) ────────
cd ../..
docker compose restart jupyterhub

# ── 7. Criar admin no JupyterHub ─────────────────────────────────
# Acessar http://<IP>:8888/hub/signup
# Cadastrar usuario "admin" com uma senha

# ── 8. Criar grupos e usuarios ───────────────────────────────────
TOKEN="setup-token-infra-mini-cloud-v5"
URL="http://localhost:8888/hub/api"

curl -X POST ${URL}/groups/analistas   -H "Authorization: token ${TOKEN}"
curl -X POST ${URL}/groups/engenheiros -H "Authorization: token ${TOKEN}"

# Criar usuarios e atribuir a grupos conforme necessario
# (ver secao "Gerenciamento de usuarios" acima)

# ── 9. OpenMetadata (opcional, profile governanca) ────────────────
docker compose --profile governanca up -d

# Aguardar o OpenMetadata ficar healthy (~2 minutos):
docker compose --profile governanca ps

# ── 10. Ingestion do Polaris no OpenMetadata ──────────────────────
# O OpenMetadata NAO descobre tabelas automaticamente.
# Precisa rodar a ingestion para catalogar as tabelas do Polaris.

cd services/openmetadata

# Modo automatico (poc_catalog):
bash auto_ingest.sh

# O script faz em sequencia:
#   1. Login como admin no OM e pega o JWT do ingestion-bot
#   2. Renova o token do Polaris (expira em ~1h)
#   3. Roda a ingestion (container openmetadata/ingestion:1.6.6)
#   4. Reindexa a busca do Elasticsearch

# Para outros catalogos (bronze, silver, gold):
# Renovar token e rodar com o YAML correspondente:
TOK=$(curl -s -X POST "http://localhost:8181/api/catalog/v1/oauth/tokens" \
  -d "grant_type=client_credentials&client_id=root&client_secret=s3cr3t&scope=PRINCIPAL_ROLE:ALL" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Substituir token no YAML desejado e rodar:
docker run --rm --network infra-net \
  -v "$(pwd)/iceberg-bronze.yaml":/ingest.yaml:ro \
  --entrypoint metadata \
  openmetadata/ingestion:1.6.6 \
  ingest -c /ingest.yaml

# Reindexar a busca:
docker exec openmetadata-server /opt/openmetadata/bootstrap/openmetadata-ops.sh reindex
```

### Verificacao final

Apos todos os passos, verificar que tudo esta funcionando:

```bash
# Todos os containers healthy?
docker compose --profile governanca ps

# JupyterHub acessivel?
curl -s -o /dev/null -w "%{http_code}" http://localhost:8888/hub/login
# Esperado: 200

# Polaris respondendo?
curl -s -o /dev/null -w "%{http_code}" http://localhost:8181/api/management/v1/catalogs
# Esperado: 200

# Airflow acessivel?
curl -s -o /dev/null -w "%{http_code}" http://localhost:8090
# Esperado: 200

# OpenMetadata acessivel?
curl -s -o /dev/null -w "%{http_code}" http://localhost:8585
# Esperado: 200

# Tabelas aparecendo no OpenMetadata?
# Acessar http://<IP>:8585 -> Explore -> Tables
```

### Ordem de dependencia dos servicos

```
rustfs          ─┐
polaris-postgres ├──> polaris ──> polaris-init (setup_acl.sh)
                 │
spark-master    ─┤
spark-worker-1   ├──> jupyterhub
spark-worker-2  ─┘
                 
airflow-postgres ─┐
airflow-redis    ─┴──> airflow-init ──> airflow (apiserver, scheduler, worker...)

openmetadata-postgres ─┐
om-elasticsearch      ─┴──> openmetadata-server ──> ingestion (auto_ingest.sh)
```

## Spark — Especificacoes completas

### Imagem Docker

| Componente | Versao |
|------------|--------|
| Base | `eclipse-temurin:21-jre-alpine` (Java 21) |
| Spark | 4.1.2 |
| Scala | 2.13 |
| Iceberg | 1.11.0 |
| Python | 3.12 |

JARs incluidos: `iceberg-spark-runtime-4.1_2.13-1.11.0.jar` + `iceberg-aws-bundle-1.11.0.jar`

### Cluster

| Container | Cores | Memoria | Porta |
|-----------|-------|---------|-------|
| spark-master | — | — | 7077 (RPC), 8088 (UI) |
| spark-worker-1 | 1 | 1g | 8081 |
| spark-worker-2 | 1 | 1g | 8082 |
| **Total** | **2** | **2g** | |

### Limites por sessao (spark-defaults)

| Config | Analista | Engenheiro | Admin |
|--------|----------|------------|-------|
| `spark.cores.max` | 1 | 1 | 1 |
| `spark.executor.cores` | 1 | 1 | 1 |
| `spark.executor.memory` | 512m | 512m | 512m |
| `spark.driver.memory` | 512m | 512m | 512m |
| `spark.dynamicAllocation.enabled` | false | false | false |

Permite **2 sessoes simultaneas** — cada uma ocupa 1 worker (1 core + 512m).

### Catalogos Iceberg (via Polaris REST)

| Catalogo Spark | Warehouse Polaris | Descricao |
|----------------|-------------------|-----------|
| `polaris` | (definido no notebook) | Catalogo generico |
| `bronze` | bronze | Camada raw/ingestao |
| `silver` | silver | Camada tratada |
| `gold` | gold | Camada consumo |

### Credenciais Polaris por role

| Role | Credencial (`client_id:client_secret`) | Permissao |
|------|----------------------------------------|-----------|
| Admin | `root:s3cr3t` | Acesso total |
| Engenheiro | `df2ed7e6984fec77:0156d6d09b370b550f77739ca89eed2a` | Leitura + escrita |
| Analista | `0060c351145db430:6ec11c147be49cdda0e23f2bd8bfcdee` | Somente leitura |

### Storage (S3FileIO → RustFS)

| Config | Valor |
|--------|-------|
| `s3.endpoint` | `http://rustfs:9000` |
| `s3.access-key-id` | `rustfs` |
| `s3.secret-access-key` | `rustfs123` |
| `s3.path-style-access` | `true` |
| `io-impl` | `org.apache.iceberg.aws.s3.S3FileIO` |

### Arquivos de configuracao

| Arquivo | Funcao |
|---------|--------|
| `services/spark/dockerfile` | Imagem base (Spark + Iceberg JARs) |
| `services/spark/docker-compose.yml` | Master + 2 workers |
| `services/spark/spark-defaults.conf` | Config do cluster (master/workers, usa root:s3cr3t) |
| `services/jupyterhub/spark-defaults-admin.conf` | Config admin montado no container Jupyter |
| `services/jupyterhub/spark-defaults-engenheiro.conf` | Config engenheiro montado no container Jupyter |
| `services/jupyterhub/spark-defaults-analista.conf` | Config analista montado no container Jupyter |

### URLs de acesso

| URL | O que |
|-----|-------|
| http://localhost:8088 | Spark Master UI (sem auth) |
| http://localhost:8081 | Worker 1 UI |
| http://localhost:8082 | Worker 2 UI |
| `spark://spark-master:7077` | Endpoint RPC (interno, rede infra-net) |

### Como ajustar recursos

Para aumentar a capacidade do cluster (ex: mais usuarios simultaneos):

1. **Workers** — editar `SPARK_WORKER_CORES` e `SPARK_WORKER_MEMORY` em `services/spark/docker-compose.yml`
2. **Por role** — editar o bloco de limites no topo de cada `spark-defaults-*.conf` em `services/jupyterhub/`
3. **Aplicar** — `docker compose up -d --no-deps spark-worker-1 spark-worker-2` e reiniciar os servers no JupyterHub

Regra geral: a soma de `spark.executor.memory` de todas as sessoes simultaneas deve caber na soma de `SPARK_WORKER_MEMORY` dos workers.

## Referencia

- Script de ACL: `services/polaris/setup_acl.sh`
- Config do JupyterHub: `services/jupyterhub/jupyterhub_config.py`
- Gerador de configs: `services/jupyterhub/generate-spark-configs.sh`
- Dockerfile dos notebooks: `services/jupyter/dockerfile`
- Documentacao de ingestion: [redorando.md](redorando.md)
- README principal: [README.md](README.md)
