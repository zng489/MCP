"""
Guardrail de entrada:
- Detecta prompt injection / jailbreak por padrão regex
- Classifica intenção: docs | sql | ambiguo | bloqueado
"""
import re
from typing import Literal

Intent = Literal["docs", "sql", "ambiguo", "bloqueado"]

PADROES_INJECTION = [
    r"ignore (all |previous |above )?instructions",
    r"you are now",
    r"act as (if you are|a) ",
    r"jailbreak",
    r"disregard (your|all)",
    r"forget (your|all) (rules|instructions)",
    r"sudo ",
    r"ignore previous",
    r"new persona",
]

PALAVRAS_SQL = {
    "rais", "vínculos", "emprego", "cbo", "uf", "salário", "setor",
    "cnae", "município", "trabalhador", "contagem", "média", "total",
    "quantos", "quais", "compare", "ranking", "top", "sql", "registro",
    "admissão", "demissão", "faixa", "remuneração",
}

PALAVRAS_DOCS = {
    "spark", "polaris", "rustfs", "airflow", "iceberg", "jupyter",
    "docker", "hdfs", "qdrant", "minio", "openmetadata", "hive",
    "instalar", "configurar", "porta", "token", "credencial", "erro",
    "stack", "infra", "cluster", "compose", "parquet", "bucket",
    "metastore", "catalog", "bronze", "silver", "gold",
}


def validar_entrada(pergunta: str) -> tuple[Intent, str]:
    """
    Retorna (intent, motivo).
    intent = "bloqueado" se detectar injection ou pergunta inválida.
    """
    p_lower = pergunta.lower().strip()

    if not p_lower:
        return "bloqueado", "Pergunta vazia"

    if len(pergunta) > 2000:
        return "bloqueado", "Pergunta muito longa (máx 2000 chars)"

    for padrao in PADROES_INJECTION:
        if re.search(padrao, p_lower):
            return "bloqueado", f"Padrão suspeito: '{padrao}'"

    tokens = set(p_lower.split())
    score_sql = len(tokens & PALAVRAS_SQL)
    score_docs = len(tokens & PALAVRAS_DOCS)

    if score_sql > score_docs:
        return "sql", f"sql={score_sql} docs={score_docs}"
    elif score_docs > score_sql:
        return "docs", f"docs={score_docs} sql={score_sql}"
    else:
        return "ambiguo", f"scores iguais (sql={score_sql} docs={score_docs})"
