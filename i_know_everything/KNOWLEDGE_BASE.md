# 📚 Knowledge Base — USB Drive `5F44-70A0`

> Consolidated documentation extracted from every text/config/script/doc file on this drive,
> organized for retrieval (RAG). Generated 2026-06-18.
> Binary artifacts (`.jar`, `.dat`, `.rar`, `.tar.gz`, `.zip`, `.docx`, `.ipynb` outputs) are **inventoried** but not transcribed.

The drive is a personal **Data Engineering / Data Lakehouse lab** built around Docker Compose.
Everything orbits one recurring stack: **Apache Spark + HDFS/Hadoop + JupyterLab**, progressively
extended with S3-compatible object stores (**Alarik, RustFS, Ceph**), an **Iceberg REST catalog (Apache Polaris)**,
a **Hive Metastore**, **OpenMetadata** (data catalog), **dbt**, and **Airflow**.
Original author host: `asus@asus-VivoBook-S14-X430UN` (Ubuntu), projects under `~/Desktop/`.

---

## 0. Drive Inventory & Folder Map

Total: ~3.4 GB, 554 files. Many folders are **near-duplicate copies / versions** of the same project.

| Top-level item | What it is |
|---|---|
| `spark-docker_somente/` | **Canonical** Spark+Hadoop+Jupyter lab + the master README (Alarik/RustFS notes). |
| `spark-docker_rustfs/` | Same project, RustFS-focused copy (README identical to `_somente`). |
| `spark-docker_orch/` , `spark-docker_orch (Copy)/` | Orchestrated variant (adds `services/`, ceph, hive-metastore). README adds a Polaris JWT token at the end. |
| `Git_Desktop/cepel_architecture/` | Git repo; same lab (README adds extra access/secret key at end). Project codename **CEPEL architecture**. |
| `infra_mini_cloud/`, `infra_mini_cloud (Copy)/`, `infra_mini_cloud_v1/` | **The full orchestrated "mini cloud"**: Spark + Jupyter + Polaris + RustFS + Hive Metastore + OpenMetadata. |
| `infra_mini_cloud_v1.rar` (546 MB) | Archive snapshot of the mini-cloud (not transcribed). |
| `spark-docker_orch.tar.gz` (485 MB) | Archive snapshot of the orch project (not transcribed). |
| `Ceph/` | Standalone Ceph S3 object-storage setup (compose + 2 READMEs). |
| `BitBucket/repositorio_bucket/` | Git repo: **CHURN_MPE** ML model versioning code (Snowflake model registry). |
| `git_hub_enterprise/` | **Empty.** |
| `New Folder/` | A loose OpenMetadata custom image (Dockerfile + entrypoint + config yaml + compose). |
| `Minikube curl LO https.txt` | Kubernetes/Minikube self-healing tutorial. |
| `System Volume Information/` | Windows filesystem metadata (ignore). |

### Notebooks present (`.ipynb`, mostly scratch / unnamed)
`CHURN_MPE_refatorar.ipynb`, `Untitled*.ipynb`, `Untitlejjd*.ipynb`, `asdasdadsa*.ipynb`, `sdadasda*.ipynb` — mostly Spark/Iceberg/S3 experiments; content not transcribed (binary JSON).

### JARs present (dependency cache)
`hadoop-aws-3.3.4.jar`, `hadoop-aws-3.3.5.jar`, `aws-java-sdk-bundle-1.12.262.jar` (S3A / SDK v1),
`iceberg-spark-runtime-3.5_2.12-1.5.2.jar`, `iceberg-aws-bundle-1.5.2.jar` (Iceberg / SDK v2),
`mysql-connector-j-9.7.0.jar` (Hive Metastore).

---

## 1. Core Architecture — Spark + HDFS + Jupyter

```
┌──────────────────────────────────────────────────────┐
│                    spark-net (bridge)                  │
│  Jupyter ──────────────────▶ Spark Master (:7077)      │
│  (:8888, driver)                  │                     │
│                            ┌──────┴──────┐              │
│                            ▼             ▼              │
│                       Worker 1       Worker 2           │
│  HDFS DataNode ◀──────────▶ HDFS NameNode (:8020)       │
└──────────────────────────────────────────────────────┘
```

- **Spark Master** = scheduler/coordinator (does NOT process data). RPC `7077`, UI `8080`.
- **Workers** = execute tasks; register at `spark://spark-master:7077`. Each reports cores/memory.
- **Jupyter** = the Spark **driver** (creates `SparkSession`, serializes Python, collects results).
- **HDFS NameNode** = namespace/index only (metadata: fsimage + edits). Lose it → lose all HDFS.
- **HDFS DataNode** = stores real 128 MB blocks; heartbeats NameNode every 3 s.

### Port reference

| Container | Container port | Host port | Purpose |
|---|---|---|---|
| spark-master | 8080 | 8080 (orch: 8088) | Master UI |
| spark-master | 7077 | 7077 | Spark RPC |
| spark-worker-1 | 8081 | 8081 | Worker 1 UI |
| spark-worker-2 | 8081 | **8082** | Worker 2 UI (8081 taken → mapped to 8082) |
| jupyter | 8888 | 8888 | JupyterLab (`?token=spark123`) |
| hdfs-namenode | 9870 | 9870 | NameNode UI |
| hdfs-namenode | 8020 | 8020 | Hadoop RPC |
| hdfs-datanode | 9864 / 9866 | 9864 / 9866 | DataNode UI / data transfer |

Default JupyterLab token: **`spark123`**. Spark monitoring UI for a running app: `http://localhost:4040`.

### Known limitation: HDFS WebUI "Browse Directory"
You can browse dirs but **cannot view file contents** in the web UI under Docker. The NameNode HTTP-redirects to the DataNode using **internal container hostnames** the host browser can't resolve. Architectural, not a config bug. Everything else works: Spark read/write, `hdfs dfs -ls`, WebHDFS REST (`curl http://localhost:9870/webhdfs/v1/<path>/?op=LISTSTATUS`).

---

## 2. Dockerfile Build Knowledge (Spark / Hadoop / Jupyter)

### `gcompat` rule (Alpine musl vs glibc)
| Image | Needs `gcompat`? | Why |
|---|---|---|
| spark (master/workers) | ✅ Yes | Snappy (Parquet compression) is glibc-compiled |
| hadoop (namenode/datanode) | ✅ Yes | `libhadoop.so` is glibc-compiled |
| jupyter | ❌ No | Debian base already uses glibc |

### Hadoop Dockerfile (Alpine + Java 17) — key fixes
- Base `eclipse-temurin:17-jre-alpine`; `apk add bash wget procps tini gcompat`.
- `HADOOP_VERSION=3.3.6`, `HADOOP_HOME=/opt/hadoop`.
- **Disable native libs** (`rm -f $HADOOP_HOME/lib/native/*`) and set `HADOOP_OPTS=-Djava.library.path=` to avoid **DataNode SIGSEGV** on musl.
- Add Java 17 module flag `--add-opens java.base/java.lang=ALL-UNNAMED` to namenode/datanode opts (fixes JAXB/WebHDFS `NoClassDefFoundError`).
- Set these directly in `hadoop-env.sh` (env vars weren't propagating to the DataNode).
- `core-site.xml` → `fs.defaultFS=hdfs://hdfs-namenode:8020`; `hdfs-site.xml` → `dfs.permissions.enabled=false` (dev only; fixes Jupyter `jovyan` vs root permission denials).

| Problem | Cause | Fix |
|---|---|---|
| DataNode SIGSEGV | glibc `libhadoop.so` on musl | `gcompat` + remove native libs |
| JAXB `NoClassDefFoundError` | Java 17 needs flags | `--add-opens java.base/java.lang=ALL-UNNAMED` |
| HDFS permission denied | root vs jovyan | `dfs.permissions.enabled=false` |
| `HADOOP_OPTS` ignored | env not propagated | define in `hadoop-env.sh` |

### Jupyter Dockerfile — Java requirement
`COPY --from=eclipse-temurin:17-jre-alpine /opt/java ...` **fails** (path not exposed). Install Java via apt instead:
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl tini procps default-jre-headless && rm -rf /var/lib/apt/lists/*
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"
```
Wrong/missing `JAVA_HOME` → `SparkSession` fails to start (PySpark can't find the JVM).

### Spark download tips
Don't use `wget -q` while debugging (it hides errors). Verify `SPARK_VERSION` exists on the mirror. Spark version used: **3.5.8**; Hadoop **3.3.4** (S3A) / 3.3.6 (HDFS image). Delta Lake `io.delta:delta-spark_2.12:3.1.0`.

### Spark Master not reachable by workers
Error `Connection refused: spark-master:7077`. Fix: start master with `--host 0.0.0.0` so it listens on all interfaces (not just localhost). Restart master + workers.

---

## 3. S3-Compatible Object Storage Integrations

This drive experimented with **three** S3-compatible stores. Key insight: **path-style access + internal Docker hostname/port** are always required.

> Inside a container, `localhost` = the container itself. Always address other services by their **compose service name** (e.g. `http://rustfs:9000`, `http://alarik:8080`), never `localhost`.

### 3a. Alarik (`ghcr.io/achtungsoftware/alarik`) — 15 documented problems
Alarik is **not S3-compatible enough** for Spark's native committers. Summary of broken S3 APIs:

| S3 API | Status in Alarik | Impact |
|---|---|---|
| PutObject | OK | simple writes work |
| GetObject / ListObjectsV2 | OK | reads/listing work |
| HeadObject | **BUGGED** — returns 200 for nonexistent paths | breaks `mkdirs`, `exists()`, overwrite |
| CopyObject | broken | breaks rename, algorithm v2 |
| DeleteObjects (bulk) | returns 404 | breaks cleanup |
| CompleteMultipartUpload | hangs/timeout | breaks directory committer |

| Committer | Result |
|---|---|
| FileOutputCommitter v1 | FAIL (no rename) |
| FileOutputCommitter v2 | FAIL (no CopyObject) |
| S3A Magic | FAIL (HeadObject bug → mkdirs) |
| S3A Directory | HANGS (CompleteMultipartUpload) |
| **HDFS staging + boto3 upload** | ✅ **WORKS** (uses only PutObject) |

**Notable problem→fix pairs:**
- `UnknownHostException: bronze.alarik` → AWS SDK uses virtual-hosted style. Set `fs.s3a.path.style.access=true` **in the SparkSession builder** (S3AFileSystem caches on first call, so `spark.conf.set()` later is ignored).
- `Connection refused :8085` → use internal port `http://alarik:8080` (8085 is host-only).
- `403 Forbidden` → real credentials (generate access key in Alarik console `http://localhost:3005`, login `alarik/alarik`).
- `ClassNotFoundException PathOutputCommitProtocol` → install `spark-hadoop-cloud_2.12-3.5.5.jar` into `/opt/spark/jars/` of **all** containers + Jupyter's pyspark jars dir, then restart + restart kernel. (`spark.jars.packages` via `.config()` doesn't work once JVM is running.)
- Container name conflicts → `docker rm -f alarik console spark-master spark-worker-1 spark-worker-2 jupyter hdfs-namenode hdfs-datanode`.
- Shared write across workers fails (only `_SUCCESS`, no parquet) → workers write to their own local FS. Use HDFS as staging (supports atomic rename; no cross-UID issues) instead of a shared Docker volume (which fails cross-user rename / permission denied → `chmod -R 777`).

**Final working Alarik pattern: write to HDFS staging, copy to local via Hadoop Java API, upload via boto3.**
```python
def spark_write_to_alarik(df, bucket, prefix):
    hdfs_tmp = "hdfs://hdfs-namenode:8020/tmp/alarik_staging"
    local_tmp = "/tmp/alarik_local_staging"
    df.write.mode("overwrite").parquet(hdfs_tmp)
    fs = spark._jvm.org.apache.hadoop.fs.FileSystem.get(
        spark._jvm.java.net.URI("hdfs://hdfs-namenode:8020"),
        spark._jsc.hadoopConfiguration())
    # copyToLocalFile each non-_/ file, then:
    s3 = boto3.client("s3", endpoint_url="http://alarik:8080",
                      aws_access_key_id=ACCESS_KEY, aws_secret_access_key=SECRET_KEY)
    s3.upload_file(local, bucket, f"{prefix}/{name}")
    # cleanup hdfs_tmp + local_tmp
```
Reading from Alarik works directly via S3A (`path.style.access=true`, endpoint `http://alarik:8080`, `bucket.probe=0`).

### 3b. RustFS (`rustfs/rustfs:latest`)
S3-compatible, behaves like MinIO. Console `:9001`, API `:9000`. Default creds in this lab: `rustfs` / `rustfs123`.
```python
os.environ['PYSPARK_SUBMIT_ARGS'] = (
  '--packages org.apache.hadoop:hadoop-aws:3.3.4,'
  'com.amazonaws:aws-java-sdk-bundle:1.12.262,'
  'org.apache.hadoop:hadoop-client-api:3.3.4,'
  'org.apache.hadoop:hadoop-client-runtime:3.3.4 pyspark-shell')
spark = (SparkSession.builder.appName("RustFS-Spark3.5")
  .config("spark.hadoop.fs.s3a.endpoint", "http://rustfs:9000")
  .config("spark.hadoop.fs.s3a.access.key", "rustfs")
  .config("spark.hadoop.fs.s3a.secret.key", "rustfs123")
  .config("spark.hadoop.fs.s3a.path.style.access", "true")
  .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
  .config("spark.hadoop.fs.s3a.aws.credentials.provider",
          "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")
  .getOrCreate())
df.write.mode("overwrite").parquet("s3a://yuan/produtos.parquet")
```

### 3c. Ceph (`quay.io/ceph/daemon:latest-octopus`) — S3 object storage
Standalone in `Ceph/`. RGW S3 API on host `5050` (container 8080), Dashboard `8443`, S3 Browser (`cloudlena/s3manager`) `9090`. Creds `myaccesskey` / `mysecretkey`. Fixed IP `192.168.100.2` on `ceph-net` (`192.168.100.0/24`).

| Problem | Cause | Fix |
|---|---|---|
| Container crash, DNS `Name or service not known` | `CEPH_DEMO_BUCKET` var | **Remove** `CEPH_DEMO_BUCKET` |
| curl `Connection reset` | wrong port 7480 | map `5050:8080` |
| `NoSuchBucket: localhost` | RGW virtual-hosted style | clear `rgw dns name` in `ceph.conf`: `sed -i 's/rgw dns name = rgw/rgw dns name = /'` then restart |
| curl PUT `AccessDenied` | no S3 auth | use `s3cmd` with creds |
| Dashboard `Address already in use` 8080 | RGW uses 8080 | Dashboard → port 8443 |
| `Password too weak` | Ceph policy | use `Admin@2026!` |
| Dashboard shows no buckets | Octopus v15 limitation | add `s3manager` browser (or upgrade to Quincy v17) |

`~/.s3cfg`: `access_key/secret_key`, `host_base=host_bucket=localhost:5050`, `use_https=False`, `signature_v2=True`.
Dashboard login: `admin` / `Admin@2026!`. Octopus = EOL; recommendation for real use = **Ceph Quincy v17** (Dashboard shows S3 buckets natively).

---

## 4. Spark S3A Performance / Tuning Reference

```python
# Connections / upload
spark.hadoop.fs.s3a.connection.maximum   = 100
spark.hadoop.fs.s3a.fast.upload          = true
spark.hadoop.fs.s3a.fast.upload.buffer   = disk
spark.hadoop.fs.s3a.multipart.size       = 67108864   # 64 MB
spark.hadoop.fs.s3a.block.size           = 134217728   # 128 MB
# Memory
spark.executor.memory = 3g ; spark.executor.memoryOverhead = 1g
spark.driver.memory   = 2g ; spark.driver.memoryOverhead   = 512m
spark.memory.fraction = 0.8 ; spark.memory.storageFraction = 0.2
# CPU / shuffle
spark.executor.cores = 2 ; spark.sql.shuffle.partitions = 40
spark.shuffle.compress = true ; spark.shuffle.spill.compress = true
spark.io.compression.codec = lz4
# Serialization
spark.serializer = org.apache.spark.serializer.KryoSerializer
spark.kryoserializer.buffer.max = 256m
# Adaptive Query Execution
spark.sql.adaptive.enabled = true
spark.sql.adaptive.coalescePartitions.enabled = true
spark.sql.adaptive.skewJoin.enabled = true
```
Best practices: separate storage disk for data, monitor via Spark UI `:4040`, tune `shuffle.partitions` to CPU count, avoid tiny datasets (overhead). Designed for self-hosted (CasaOS).

---

## 5. The Orchestrated "Mini Cloud" (`infra_mini_cloud`)

Root `docker-compose.yml` composes per-service files via `extends:`. Full stack:
**hive-metastore, mysql, spark-master, spark-worker-1, spark-worker-2, jupyter, polaris** (+ optional polaris-setup, openmetadata-server, openmetadata-ingestion).

Networks: `spark-net` (internal bridge) + `rust-net` (**external** — must `docker network create --driver bridge --subnet 192.168.100.0/24 rust-net` first). Pattern: bring up the **external/storage container first**, then connect others: `docker network connect rust-net spark-master`.

### Service summary

| Service | Image | Ports (host:container) | Notes |
|---|---|---|---|
| spark-master | `spark-master:latest` | 7077, 8088:8080 | `user: 0:0`, `--host 0.0.0.0`, mounts `spark-defaults.conf` |
| spark-worker-1/2 | `spark-master:latest` | 8081, 8082:8081 | `sleep 10` before start; 1 core / 2g each |
| jupyter | `jupyter:latest` | 8888 | token `spark123`, `--allow-root` |
| polaris | `apache/polaris:latest` | 8181 (catalog API), 8182 (health) | Iceberg REST catalog |
| rustfs | `rustfs/rustfs:latest` | 9000 (S3), 9001 (console) | fixed IP `192.168.100.10` on rust-net |
| s3browser | `cloudlena/s3manager` | 9090:8080 | web S3 browser |
| hive-metastore | built (`hive-metastore:latest`) | 9084:9083 | warehouse `s3a://raw/warehouse/` |
| mysql (metastore) | `mysql:5.7` | 3307:3306 | db `metastore`, pass `metastorepass` |
| openmetadata-mysql | `mysql:8.0` | 3308:3306 | db `openmetadata_db` |
| om-elasticsearch | `elasticsearch:8.15.0` | 9201:9200, 9301:9300 | single-node, security off |
| openmetadata-server | `openmetadata/server:1.6.6` | 8585 (API), 8586 (admin) | cluster `mini-data-lake` |

### Apache Polaris (Iceberg REST catalog)
- Bootstrap creds: realm `POLARIS`, client `root` / secret `s3cr3t` (`POLARIS_BOOTSTRAP_CREDENTIALS: POLARIS,root,s3cr3t`).
- Storage types enabled: `S3,GCS,AZURE,S3_COMPATIBLE`. Uses RustFS as backing S3 (`rustfs`/`rustfs123`).
- Get an OAuth token:
```bash
TOKEN=$(curl -s -X POST http://localhost:8181/api/catalog/v1/oauth/tokens \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d "grant_type=client_credentials&client_id=root&client_secret=s3cr3t&scope=PRINCIPAL_ROLE:ALL" \
  | jq -r '.access_token')
```
- Create catalog (`rustfs_catalog`, base `s3://raw`, endpoint `http://rustfs:9000`, pathStyle, region us-east-1) and a `bronze` namespace via the management/catalog APIs (`Polaris-Realm: POLARIS` header). Tokens expire in ~1h.

### `spark-defaults.conf` (Iceberg + Polaris wiring)
```properties
spark.sql.extensions                         org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions
spark.sql.catalog.polaris                    org.apache.iceberg.spark.SparkCatalog
spark.sql.catalog.polaris.type               rest
spark.sql.catalog.polaris.uri                http://polaris:8181/api/catalog
spark.sql.catalog.polaris.credential         root:s3cr3t
spark.sql.catalog.polaris.scope              PRINCIPAL_ROLE:ALL
spark.sql.catalog.polaris.header.Polaris-Realm  POLARIS
spark.sql.catalog.polaris.io-impl            org.apache.iceberg.aws.s3.S3FileIO
spark.sql.catalog.polaris.s3.endpoint        http://rustfs:9000
spark.sql.catalog.polaris.s3.access-key-id   rustfs
spark.sql.catalog.polaris.s3.secret-access-key rustfs123
spark.sql.catalog.polaris.s3.path-style-access true
spark.driver.extraJavaOptions   -Daws.accessKeyId=rustfs -Daws.secretAccessKey=rustfs123 -Daws.region=us-east-1 ...
spark.executor.extraJavaOptions -Daws.accessKeyId=rustfs -Daws.secretAccessKey=rustfs123 -Daws.region=us-east-1
```

### ⚠️ Critical JAR conflict: SDK v1 vs v2
- **SDK v1** `com.amazonaws:aws-java-sdk-bundle` (2010) → used by `hadoop-aws` / `S3AFileSystem` (package `com.amazonaws.*`).
- **SDK v2** `software.amazon.awssdk` (2018) → used by `iceberg-aws-bundle` / `S3FileIO` (package `software.amazon.awssdk.*`).
- They **conflict**. The lab swaps JAR sets via two scripts — **never run both** (each removes the other's JARs); restart Jupyter kernel after.
  - `setup_jars_polaris.sh`: removes `hadoop-aws-*` + `aws-java-sdk-bundle-*`, installs `iceberg-spark-runtime-3.5_2.12-1.5.2.jar` + `iceberg-aws-bundle-1.5.2.jar` into all spark containers + jupyter.
  - `setup_jars_hive.sh`: the inverse, for Hive Catalog + S3A.
- `spark-defaults.conf` keeps the S3A (SDK v1 / Hive) block commented out — uncomment only when using Hive Catalog instead of Polaris.

### Hive Metastore (`hive-site.xml`)
- Backing DB: MySQL `jdbc:mysql://mysql:3306/metastore?createDatabaseIfNotExist=true`, user `root` / `metastorepass`.
- `hive.metastore.schema.verification=false`.
- Warehouse on S3A: `hive.metastore.warehouse.dir = s3a://raw/warehouse/`, endpoint `http://rustfs:9000`, creds rustfs/rustfs123, path-style, ssl off.
- Uses `mysql-connector-j-9.7.0.jar`.

---

## 6. OpenMetadata (Data Catalog) + Polaris Ingestion

Two long tutorials cover this (`infra_mini_cloud/services/openmetadata/README.md`, `infra_mini_cloud/test/readme.md`).

### Deployment (compose in `New Folder/` and `infra_mini_cloud/openmetadata/`)
- `openmetadata/server:1.6.6` + dedicated MySQL 8.0 (`openmetadata_db`, `om_user`/`om_user_pass`, root `om_root_pass`) + Elasticsearch 8.15.0 (single-node, security disabled, 1g heap).
- A one-shot `openmetadata-migrate` job runs `./bootstrap/openmetadata-ops.sh migrate` before the server starts (`service_completed_successfully`).
- Server env: `FERNET_KEY=jJgVqL9KpHx8t4YzW2mNcR5sA7bDfG1kU3oX6eQ0vBw=`, `OPENMETADATA_CLUSTER_NAME=mini-data-lake`, server `0.0.0.0:8585`, admin `:8586`, healthcheck `GET /healthcheck` on 8586.
- Custom image (`New Folder/`): `FROM openmetadata/server:1.6.6` + `apk add procps` + entrypoint that runs migrate then `/openmetadata-start.sh`.
- Config yaml uses MySQL `jdbc:mysql://mysql:3306/openmetadata_db`, ES host `elasticsearch:9200`, `secretsManager: noop`, `clusterName: mini-data-lake`.

### Ingesting Iceberg/Polaris metadata into OpenMetadata
- `services/openmetadata/iceberg-polaris.yaml` — ingestion workflow: source `type: iceberg`, catalog `poc_catalog`, connection `uri: http://polaris:8181/api/catalog` + a **Polaris JWT token** (expires ~1h), sink `metadata-rest` to `http://openmetadata-server:8585/api` using the OM **ingestion-bot JWT**.
- `run_ingest.py`:
```python
import yaml
from metadata.workflow.metadata import MetadataWorkflow
config = yaml.safe_load(open('/tmp/iceberg-polaris.yaml'))
wf = MetadataWorkflow.create(config); wf.execute(); wf.print_status()
```
- Workflow per the README: (1) generate fresh Polaris token, (2) substitute token into the YAML, (3) run ingestion. Recurring pain points documented: tokens expire every 1h; OM 1.6.6 `RestCatalogConnection` accepted fields; checking ES indices (`_cat/indices`) for created table indices; replacing the `jwtToken` after expiry.

---

## 7. Ceph Quick Setup (standalone, `Ceph/`)

`docker-compose.yml` runs `ceph` (`command: demo`, daemons `mon,mgr,osd,rgw`) + `s3browser`. Post-deploy script (`setup.sh`) does: down -v + volume prune → up -d → wait 60s → clear `rgw dns name` → set dashboard port 8443 + ssl false + enable dashboard module → create `admin/Admin@2026!` → restart → `ceph status` + `ceph mgr services`.

Useful: `docker exec ceph ceph status|osd pool ls|mgr services`, `radosgw-admin user list|user info --uid=demo|bucket list`. s3cmd ops: `mb/ls/put/get/del/rb s3://meubucket`.

---

## 8. Kubernetes / Minikube Self-Healing Tutorial (`Minikube curl LO https.txt`)

A complete POC: install Docker + Minikube + kubectl → tiny Python `http.server` app with `/health`, `/crash` (`sys.exit(1)`), `/` (returns pod hostname) → `Dockerfile` (`python:3.11-slim`) → `deployment.yaml` (2 replicas + NodePort service).
- Key gotcha: `eval $(minikube docker-env)` makes `docker build` build **inside** Minikube so K8s finds the image (`eval $(minikube docker-env -u)` to revert).
- Deploy `kubectl apply -f deployment.yaml`; URL via `minikube service python-poc-service --url`.
- Self-healing demo: `kubectl get pods -w` in one terminal, `curl .../crash` in another → pod goes `Error → CrashLoopBackOff → Running` automatically.
- Scale: `kubectl scale deployment python-poc --replicas=4`. Cleanup: `kubectl delete -f`, `minikube stop/delete`.

---

## 9. BitBucket repo — CHURN_MPE ML model versioning (Python)

`CHURN_MPE_get_versions.py` — utilities for a churn model in a **Snowflake** model registry:
- `get_next_model_version(model_obj, versions)` → next `V<n>` name (parses existing `V1,V2,...`, returns max+1, or `V1` if none).
- `get_rounded_metrics(metrics)` → rounds to 2 decimals and flattens nested dict into `parent.child` keys (e.g. `1.f1-score`).
- `get_best_version(versions)` → picks version with highest **F1-score of class 1**, then runs Snowflake SQL `ALTER MODEL {db}.{schema}.{model_name} SET DEFAULT_VERSION = '<name>'`.
- Companion notebook `CHURN_MPE_refatorar.ipynb` (not transcribed).

---

## 10. Docker / Network Cheat Sheet (collected from docs)

```bash
# Lifecycle
docker compose up -d --build ; docker compose ps ; docker compose logs -f <svc>
docker compose down            # keep volumes
docker compose down -v         # DELETE volumes (HDFS/data lost!)
docker exec -it <svc> bash

# Nuke everything
docker stop $(docker ps -aq) ; docker rm $(docker ps -aq)
docker network prune ; docker volume prune ; docker volume rm $(docker volume ls -q)

# External network for the mini-cloud
docker network create --driver bridge --subnet 192.168.100.0/24 rust-net
docker network connect rust-net spark-master   # join a container to an external net

# Check Iceberg JARs across containers
for C in spark-master spark-worker-1 spark-worker-2 jupyter; do
  echo "=== $C ==="; docker exec $C ls /opt/spark/jars/ | grep iceberg; done
```
- `ENTRYPOINT ["tini", "--"]` → `tini` is PID 1, reaps zombies and forwards signals; runs whatever command follows.
- Bind mount (`./data:/path`) = host-editable, visible; **named volume** = Docker-managed (`/var/lib/docker/volumes/`), better perf, needs `docker cp` to extract.
- Disable Ubuntu screen lock (author's note): `gsettings set org.gnome.desktop.screensaver lock-enabled false` and `... lockdown disable-lock-screen true`.

---

## 11. 🔐 Credentials & Secrets Found On This Drive

> These are **embedded in the lab files** (dev/demo credentials). Listed here for completeness — **rotate any that map to a real system**, and do not reuse in production.

| System | Key / value |
|---|---|
| Alarik (S3) | access `DANLQMEACSNA6BQMHSPV` / secret `iCj2+E7qMODIpuw7xGrxHCEGlpRbVPjz7AWVW06g`, login `alarik/alarik` |
| RustFS | `rustfs` / `rustfs123` |
| Ceph S3 | `myaccesskey` / `mysecretkey`; Dashboard `admin` / `Admin@2026!` |
| Polaris | client `root` / secret `s3cr3t`, realm `POLARIS` |
| Hive Metastore MySQL | `root` / `metastorepass` |
| OpenMetadata MySQL | `om_user` / `om_user_pass`, root `om_root_pass`; Fernet `jJgVqL9KpHx8t4YzW2mNcR5sA7bDfG1kU3oX6eQ0vBw=` |
| Jupyter | token `spark123` |
| cepel_architecture README tail | access `TBB2FP1397303Y7WBVDZ` / secret `OAXgrixy2e4JAJPfnMBRF9JZiO4arX38LNVLMj9+` |
| Various | short-lived Polaris & OpenMetadata-bot JWTs (expired) embedded in `iceberg-polaris.yaml` and README tails |

---

## 12. File-Type Inventory (counts, excluding `.git`)

`.dat` ×147 (binary data), `.ipynb` ×77 (notebooks), `.yml` ×73 (compose), `.jar` ×24, `.txt` ×22, `.md` ×21, `.sh` ×16, `.log` ×12, `.xml` ×5, `dockerfile`/`Dockerfile` (multiple), `.conf` ×4, `.docx` ×3, `.py` ×3, `.properties` ×2, `.zip` ×3, `.rar` ×1, `.tar.gz` ×1.

Word docs (not transcribed; same content as the READMEs above): `documentacao_mini_data_lake.docx` (in `infra_mini_cloud*/test/`). `.~lock.*` files are LibreOffice lock files (safe to ignore).
