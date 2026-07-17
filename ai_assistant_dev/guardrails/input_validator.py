"""
Guardrail de entrada:
- Detecta prompt injection / jailbreak por padrão regex
- Classifica intenção: docs | sql | ambiguo | bloqueado
"""
import re

#from typing import Literal
Intent = ["docs", "sql", "ambiguo", "bloqueado"]

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

print(PADROES_INJECTION)
print(PALAVRAS_SQL)
print(PALAVRAS_DOCS)


def validar_entrada(pergunta: str) -> tuple[str, str]:
    """
    Retorna (intent, motivo).
    intent = "bloqueado" se detectar injection ou pergunta inválida.
    """

    p_lower = pergunta

    """
    # se p_lower estiver vazia"
    if not p_lower:
        return "bloqueado", "Pergunta vazia"
    """

    # Regra: isinstance dá True se for do tipo, False se não for.

    # if not False:   # → True
    # É exatamente isso. O not inverte:
    # not False   # → True
    # not True    # → False


    # Vamos supor pergunta = None, que não é uma string
    # Se pergunta = None é não é string, então isinstance(pergunta, str) == False
    # Logo fica "if not False --> True" 
    # isinstance(None, str)   # → False   (porque None NÃO é string)


    # Vamos supor pergunta = "palavra_qualquer", que é uma string
    # Se pergunta = "palavra_qualquer" é string, então isinstance(pergunta, str) == True
    # Logo fica "if not True --> False", ENTAO COMEÇA essa condição "or not pergunta.strip()";
    # Então "palavra_qualquer.strip() --> True", "not True --> False"
    
    if not isinstance(pergunta, str) or not pergunta.strip():
        return "bloqueado", "Pergunta vazia ou inválida"
    
    p_lower = pergunta.lower().strip()

    if len(pergunta) > 2000:
        return "bloqueado", "Pergunta muito longa (máx 2000 chars)"

    for padrao in PADROES_INJECTION:
        if re.search(padrao, p_lower):
            return "bloqueado", f"Padrão suspeito: '{padrao}'"

    # set tirar as duplicadas
    tokens = set(p_lower.split())
    print(tokens)


    # O & entre dois sets é o operador de interseção: e
    # le devolve um novo set só com os elementos que aparecem nos dois conjuntos ao mesmo tempo
    score_sql = len(tokens & PALAVRAS_SQL)
    score_docs = len(tokens & PALAVRAS_DOCS)

    if score_sql > score_docs:
        return "sql", f"sql={score_sql} docs={score_docs}"
    elif score_docs > score_sql:
        return "docs", f"docs={score_docs} sql={score_sql}"
    else:
        return "ambiguo", f"scores iguais (sql={score_sql} docs={score_docs})"
    

#if __name__ == "__main__":
#    pergunta = "jailbreak"
#    validar_entrada(pergunta)

if __name__ == "__main__":
    pergunta = "quantos trabalhadores por uf e salário"
    resultado = validar_entrada(pergunta)
    print(resultado)