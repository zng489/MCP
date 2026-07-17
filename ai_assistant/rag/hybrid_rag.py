"""
RAG híbrido — adaptado do bot_architecture com os docs do ai_assistant/:
- Semântica (all-MiniLM-L6-v2) + BM25 + rerank cross-encoder
- Small-to-big: busca em chunks filhos, retorna o chunk pai completo
- Cache de embeddings em .cache/ (recalcula só quando os docs mudam)
"""
import hashlib
import sys
from pathlib import Path
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder
from rank_bm25 import BM25Okapi

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (
    DOCS_DIR, CACHE_DIR, ARQUIVOS_DOCS,
    EMBEDDING_MODEL, RERANK_MODEL,
    TOP_K, N_CANDIDATOS, PESO_SEMANTICO,
    TAMANHO_PAI, TAMANHO_FILHO, LIMIAR_MIN, USAR_RERANK,
)

CACHE_DIR.mkdir(exist_ok=True)


def _ler_docs() -> list[dict]:
    docs = []
    for nome in ARQUIVOS_DOCS:
        caminho = DOCS_DIR / nome
        if caminho.exists():
            docs.append({"texto": caminho.read_text(encoding="utf-8"), "fonte": nome})
    return docs


def _chunks_pai_filho(docs: list[dict]) -> tuple[list[dict], list[dict]]:
    pais, filhos = [], []
    for doc in docs:
        texto, fonte = doc["texto"], doc["fonte"]
        for i in range(0, len(texto), TAMANHO_PAI - 200):
            pai_txt = texto[i: i + TAMANHO_PAI]
            pai_idx = len(pais)
            pais.append({"texto": pai_txt, "fonte": fonte, "idx": pai_idx})
            for j in range(0, len(pai_txt), TAMANHO_FILHO - 50):
                filho_txt = pai_txt[j: j + TAMANHO_FILHO]
                filhos.append({"texto": filho_txt, "fonte": fonte, "pai_idx": pai_idx})
    return pais, filhos


def _hash_docs(docs: list[dict]) -> str:
    conteudo = "".join(d["texto"] for d in docs)
    return hashlib.md5(conteudo.encode()).hexdigest()


class HybridRAG:
    def __init__(self):
        self._embedding_model: Optional[SentenceTransformer] = None
        self._rerank_model: Optional[CrossEncoder] = None
        self._pais: list[dict] = []
        self._filhos: list[dict] = []
        self._vetores: Optional[np.ndarray] = None
        self._bm25: Optional[BM25Okapi] = None
        self._carregado = False

    def _carregar_modelos(self):
        if self._embedding_model is None:
            self._embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        if USAR_RERANK and self._rerank_model is None:
            self._rerank_model = CrossEncoder(RERANK_MODEL)

    def carregar(self):
        """Carrega docs, gera/lê cache de embeddings e inicializa BM25."""
        self._carregar_modelos()
        docs = _ler_docs()
        if not docs:
            raise RuntimeError(f"Nenhum doc encontrado em {DOCS_DIR}. Verifique ARQUIVOS_DOCS em config.py.")

        hash_atual = _hash_docs(docs)
        self._pais, self._filhos = _chunks_pai_filho(docs)

        cache_file = CACHE_DIR / "vetores_hybrid.npz"
        hash_file = CACHE_DIR / "hash_hybrid.txt"

        if cache_file.exists() and hash_file.exists():
            if hash_file.read_text().strip() == hash_atual:
                data = np.load(cache_file)
                self._vetores = data["vetores"]
                self._inicializar_bm25()
                self._carregado = True
                return

        textos_filhos = [f["texto"] for f in self._filhos]
        self._vetores = self._embedding_model.encode(
            textos_filhos, show_progress_bar=True, normalize_embeddings=True
        ).astype(np.float32)
        np.savez(cache_file, vetores=self._vetores)
        hash_file.write_text(hash_atual)
        self._inicializar_bm25()
        self._carregado = True

    def _inicializar_bm25(self):
        tokenizado = [f["texto"].lower().split() for f in self._filhos]
        self._bm25 = BM25Okapi(tokenizado)

    def buscar(self, pergunta: str) -> list[dict]:
        """Retorna os TOP_K chunks pais mais relevantes para a pergunta."""
        if not self._carregado:
            self.carregar()

        vetor_q = self._embedding_model.encode(
            [pergunta], normalize_embeddings=True
        )[0].astype(np.float32)

        scores_sem = self._vetores @ vetor_q

        tokens_q = pergunta.lower().split()
        scores_bm25 = np.array(self._bm25.get_scores(tokens_q), dtype=np.float32)
        max_bm25 = scores_bm25.max() or 1.0
        scores_bm25_norm = scores_bm25 / max_bm25

        scores = PESO_SEMANTICO * scores_sem + (1 - PESO_SEMANTICO) * scores_bm25_norm

        top_idx = np.argsort(scores)[::-1][:N_CANDIDATOS]
        candidatos = [
            {"filho": self._filhos[i], "score": float(scores[i])}
            for i in top_idx
            if float(scores[i]) >= LIMIAR_MIN
        ]

        if USAR_RERANK and self._rerank_model and candidatos:
            pares = [(pergunta, c["filho"]["texto"]) for c in candidatos]
            scores_rerank = self._rerank_model.predict(pares)
            for c, s in zip(candidatos, scores_rerank):
                c["score_rerank"] = float(s)
            candidatos.sort(key=lambda x: x["score_rerank"], reverse=True)

        pais_vistos: set[int] = set()
        resultado = []
        for c in candidatos:
            pai_idx = c["filho"]["pai_idx"]
            if pai_idx not in pais_vistos:
                pais_vistos.add(pai_idx)
                resultado.append(self._pais[pai_idx])
            if len(resultado) >= TOP_K:
                break

        return resultado
