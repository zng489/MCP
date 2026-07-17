"""
Memória de longo prazo: conversas persistidas em SQLite entre sessões.
O orquestrador consulta antes de responder para enriquecer o contexto.
"""
import sqlite3
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH


def _conn() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH)
    db.execute("""
        CREATE TABLE IF NOT EXISTS conversas (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            ts       TEXT,
            pergunta TEXT,
            resposta TEXT,
            agente   TEXT,
            aprovado INTEGER DEFAULT 0,
            score    REAL    DEFAULT 0.0
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS fatos (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            ts    TEXT,
            chave TEXT UNIQUE,
            valor TEXT
        )
    """)
    db.commit()
    return db


def salvar_conversa(
    pergunta: str,
    resposta: str,
    agente: str,
    aprovado: bool = False,
    score: float = 0.0,
):
    with _conn() as db:
        db.execute(
            "INSERT INTO conversas (ts, pergunta, resposta, agente, aprovado, score) VALUES (?,?,?,?,?,?)",
            (datetime.now().isoformat(), pergunta, resposta, agente, int(aprovado), score),
        )


def buscar_conversas_similares(pergunta: str, limite: int = 3) -> list[dict]:
    """Busca conversas anteriores com sobreposição de tokens."""
    tokens = set(pergunta.lower().split())
    with _conn() as db:
        rows = db.execute(
            "SELECT pergunta, resposta, agente, ts FROM conversas ORDER BY id DESC LIMIT 100"
        ).fetchall()

    resultados = []
    for row in rows:
        p, r, a, ts = row
        tokens_p = set(p.lower().split())
        overlap = len(tokens & tokens_p) / max(len(tokens), 1)
        if overlap > 0.3:
            resultados.append({"pergunta": p, "resposta": r, "agente": a, "ts": ts, "overlap": overlap})

    resultados.sort(key=lambda x: x["overlap"], reverse=True)
    return resultados[:limite]


def salvar_fato(chave: str, valor: str):
    with _conn() as db:
        db.execute(
            "INSERT OR REPLACE INTO fatos (ts, chave, valor) VALUES (?,?,?)",
            (datetime.now().isoformat(), chave, valor),
        )


def buscar_fatos() -> dict:
    with _conn() as db:
        rows = db.execute("SELECT chave, valor FROM fatos").fetchall()
    return {k: v for k, v in rows}
