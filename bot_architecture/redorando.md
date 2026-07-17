# Ingestion Polaris -> OpenMetadata (apos gravar dados novos)

## Quando rodar

Toda vez que voce gravar tabelas novas no Polaris (via Spark/Jupyter ou Airflow),
o OpenMetadata **nao descobre automaticamente**. Voce precisa rodar a ingestion
para que as tabelas aparecam em **Explore -> Tables** no OM.

## Catalogos disponiveis

Cada catalogo do Polaris tem seu proprio YAML de ingestion:

| Catalogo | YAML | Service no OM |
|----------|------|---------------|
| `poc_catalog` | `iceberg-polaris.yaml` | Iceberg |
| `bronze` | `iceberg-bronze.yaml` | Iceberg_Bronze |
| `silver` | `iceberg-silver.yaml` (criar a partir do bronze) | Iceberg_Silver |
| `gold` | `iceberg-gold.yaml` (criar a partir do bronze) | Iceberg_Gold |

**Importante**: a ingestion so enxerga o catalogo configurado no YAML. Se voce gravou
dados no `bronze`, precisa rodar a ingestion com `iceberg-bronze.yaml`, nao com
`iceberg-polaris.yaml`.

## Modo automatico (recomendado)

O script `auto_ingest.sh` faz tudo de uma vez para o `poc_catalog`:

```bash
cd ~/docker-apps/infra_mini_cloud_v5/services/openmetadata
bash auto_ingest.sh
```

O que ele faz em sequencia:
1. Faz login como admin no OM e pega o JWT do `ingestion-bot`
2. Renova o token do Polaris (expira em ~1h) via `refresh_token.sh`
3. Roda a ingestion (container `openmetadata/ingestion:1.6.6`)
4. Reindexa a busca do Elasticsearch

No final, as tabelas aparecem em `http://<IP>:8585 -> Explore -> Tables`.

## Rodar ingestion para outros catalogos (bronze, silver, gold)

Para catalogos alem do `poc_catalog`, rode manualmente com o YAML correspondente:

```bash
cd ~/docker-apps/infra_mini_cloud_v5/services/openmetadata

# 1. renovar o token do Polaris no YAML desejado
bash refresh_token.sh                    # atualiza iceberg-polaris.yaml
# para outros YAMLs, renovar o token manualmente:
TOK=$(curl -s -X POST "http://localhost:8181/api/catalog/v1/oauth/tokens" \
  -d "grant_type=client_credentials&client_id=root&client_secret=s3cr3t&scope=PRINCIPAL_ROLE:ALL" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
# substituir no YAML (ex: bronze)
python3 -c "
import re
s = open('iceberg-bronze.yaml').read()
new = re.sub(r'(token: \")[^\"]*\"', r'\1$TOK\"', s, count=1)
open('iceberg-bronze.yaml','w').write(new)
"

# 2. rodar a ingestion com o YAML do catalogo
docker run --rm --network infra-net \
  -v "$(pwd)/iceberg-bronze.yaml":/ingest.yaml:ro \
  --entrypoint metadata \
  openmetadata/ingestion:1.6.6 \
  ingest -c /ingest.yaml

# 3. reindexar a busca
docker exec openmetadata-server /opt/openmetadata/bootstrap/openmetadata-ops.sh reindex
```

## Criar YAML para silver ou gold

Copie o `iceberg-bronze.yaml` e troque o `serviceName` e `name`/`warehouseLocation`:

```bash
cp iceberg-bronze.yaml iceberg-silver.yaml
# editar: serviceName -> Iceberg_Silver, name -> silver, warehouseLocation -> silver

cp iceberg-bronze.yaml iceberg-gold.yaml
# editar: serviceName -> Iceberg_Gold, name -> gold, warehouseLocation -> gold
```

Campos a alterar no YAML:

```yaml
source:
  serviceName: Iceberg_Silver   # nome unico no OM
  serviceConnection:
    config:
      catalog:
        name: silver             # nome do catalogo no Polaris
        warehouseLocation: "silver"
```

## Modo manual (passo a passo)

### 1. Renovar token do Polaris

```bash
cd ~/docker-apps/infra_mini_cloud_v5/services/openmetadata
bash refresh_token.sh
```

### 2. Pegar o JWT do ingestion-bot

Acesse o OpenMetadata (`http://<IP>:8585`):
- Va em **Settings -> Bots -> ingestion-bot**
- Copie o JWT token
- Cole no campo `jwtToken` do arquivo YAML correspondente

Ou via API:

```bash
# login admin
PASS_B64=$(printf '%s' "admin" | base64)
ACCESS=$(curl -s -X POST "http://localhost:8585/api/v1/users/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"admin@open-metadata.org\",\"password\":\"$PASS_B64\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['accessToken'])")

# pegar ID do bot
BOT_ID=$(curl -s "http://localhost:8585/api/v1/bots/name/ingestion-bot" \
  -H "Authorization: Bearer $ACCESS" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['botUser']['id'])")

# pegar JWT
curl -s "http://localhost:8585/api/v1/users/token/$BOT_ID" \
  -H "Authorization: Bearer $ACCESS" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['JWTToken'])"
```

### 3. Rodar a ingestion

```bash
docker run --rm --network infra-net \
  -v "$(pwd)/iceberg-polaris.yaml":/ingest.yaml:ro \
  --entrypoint metadata \
  openmetadata/ingestion:1.6.6 \
  ingest -c /ingest.yaml
```

### 4. Reindexar a busca

```bash
docker exec openmetadata-server /opt/openmetadata/bootstrap/openmetadata-ops.sh reindex
```

## Resultado esperado

```
Workflow Iceberg Summary:
  Processed records: 4
  Errors: 0
  Success %: 100.0
```

Se houver erros, verifique:

- **Token do Polaris expirado**: rode `bash refresh_token.sh` novamente
- **JWT do ingestion-bot invalido**: gere um novo via UI ou API (passo 2)
- **Polaris fora do ar**: `docker compose ps` e verifique se o Polaris esta healthy
- **Tabelas nao aparecem na busca**: rode o reindex (passo 4) ou veja [re_index.md](re_index.md)
- **Tabelas de outro catalogo nao aparecem**: verifique se esta usando o YAML correto
  (ex: `iceberg-bronze.yaml` para dados do catalogo `bronze`)

## Tokens e expiracao

| Token | Expira | Como renovar |
|-------|--------|--------------|
| Polaris (OAuth) | ~1 hora | `bash refresh_token.sh` |
| ingestion-bot (JWT) | Unlimited | Gerado uma vez, nao expira |
| Admin (login) | ~1 hora | Login novamente via API |

## Referencia

- Arquivos de config da ingestion:
  - `services/openmetadata/iceberg-polaris.yaml` (poc_catalog)
  - `services/openmetadata/iceberg-bronze.yaml` (bronze)
- Script automatico: `services/openmetadata/auto_ingest.sh`
- Script de token Polaris: `services/openmetadata/refresh_token.sh`
- Documentacao de reindex: [re_index.md](re_index.md)
- README principal: [README.md](README.md) - Secao 7
