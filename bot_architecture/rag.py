"""Retrieval híbrido + small-to-big + rerank.

- chunk_docs: cada seção vira blocos PAIS (grandes); cada pai vira FILHOS (pequenos).
- criar_indice: embeda os FILHOS (cache em disco) e monta o BM25 sobre eles.
- buscar: acha os melhores FILHOS (preciso) e devolve os PAIS correspondentes (contexto).
"""
import re
import hashlib

import numpy as np
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi

import config

_modelo = None
_reranker = None


def _get_modelo():
    global _modelo
    if _modelo is None:
        _modelo = SentenceTransformer(config.MODELO_EMB)
    return _modelo


def _get_reranker():
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder
        _reranker = CrossEncoder(config.MODELO_RERANK)
    return _reranker


def _tokens(texto):
    return re.findall(r"\w+", texto.lower())


def _dividir(texto, limite):
    """Quebra um texto em blocos de até `limite` caracteres, por parágrafo."""
    blocos, buffer = [], ""
    for paragrafo in texto.split("\n\n"):
        if buffer and len(buffer) + len(paragrafo) > limite:
            blocos.append(buffer.strip())
            buffer = ""
        buffer += paragrafo + "\n\n"
    if buffer.strip():
        blocos.append(buffer.strip())
    return blocos


def chunk_docs():
    """Retorna (filhos, pais). Cada filho aponta para o índice do seu pai."""
    pais, filhos = [], []
    for nome in config.ARQUIVOS_DOCS:
        arquivo = config.PASTA_DOCS / nome
        if not arquivo.exists():
            continue
        texto = arquivo.read_text(encoding="utf-8")
        for secao in re.split(r"\n(?=## )", texto):
            secao = secao.strip()
            if not secao:
                continue
            for bloco_pai in _dividir(secao, config.TAMANHO_PAI):
                pai_id = len(pais)
                pais.append({"arquivo": nome, "texto": bloco_pai})
                for filho in _dividir(bloco_pai, config.TAMANHO_FILHO):
                    filhos.append({"arquivo": nome, "texto": filho, "pai": pai_id})
    return filhos, pais


def _assinatura(itens):
    h = hashlib.sha256()
    for it in itens:
        h.update(it["texto"].encode("utf-8"))
    return h.hexdigest()


def criar_indice():
    """Embeda os filhos (reusa o cache se os docs não mudaram) e monta o BM25."""
    filhos, pais = chunk_docs()
    assinatura = _assinatura(filhos)
    cache_vec = config.PASTA_CACHE / "vetores.npy"
    cache_sig = config.PASTA_CACHE / "assinatura.txt"

    if cache_vec.exists() and cache_sig.exists() and cache_sig.read_text() == assinatura:
        vetores = np.load(cache_vec)
    else:
        modelo = _get_modelo()
        vetores = modelo.encode([f["texto"] for f in filhos], normalize_embeddings=True)
        np.save(cache_vec, vetores)
        cache_sig.write_text(assinatura)

    bm25 = BM25Okapi([_tokens(f["texto"]) for f in filhos])
    return {"filhos": filhos, "pais": pais, "vetores": vetores, "bm25": bm25}


def _normalizar(x):
    faixa = x.max() - x.min()
    return (x - x.min()) / faixa if faixa > 0 else np.zeros_like(x)


def buscar(indice, pergunta, k=None, minimo=None):
    """Acha os melhores filhos (preciso) e devolve os pais únicos (contexto)."""
    k = k or config.TOP_K
    minimo = config.LIMIAR_MIN if minimo is None else minimo
    filhos, pais = indice["filhos"], indice["pais"]

    # 1. busca híbrida sobre os FILHOS -> candidatos
    consulta = _get_modelo().encode([pergunta], normalize_embeddings=True)[0]
    semantico = _normalizar(indice["vetores"] @ consulta)
    keyword = _normalizar(np.array(indice["bm25"].get_scores(_tokens(pergunta))))
    hibrido = config.PESO_SEMANTICO * semantico + (1 - config.PESO_SEMANTICO) * keyword

    n_cand = config.N_CANDIDATOS if config.USAR_RERANK else max(k * 3, k)
    candidatos = list(np.argsort(hibrido)[::-1][:n_cand])

    # 2. rerank dos filhos candidatos
    if config.USAR_RERANK:
        pares = [(pergunta, filhos[i]["texto"]) for i in candidatos]
        scores = _normalizar(np.array(_get_reranker().predict(pares)))
    else:
        scores = np.array([hibrido[i] for i in candidatos])

    ordem = np.argsort(scores)[::-1]

    # 3. small-to-big: dos melhores filhos, devolve os PAIS únicos
    selecionados, vistos = [], set()
    for pos in ordem:
        if scores[pos] < minimo:
            continue
        pai_id = filhos[candidatos[pos]]["pai"]
        if pai_id in vistos:
            continue
        vistos.add(pai_id)
        selecionados.append(dict(pais[pai_id], score=round(float(scores[pos]), 3)))
        if len(selecionados) >= k:
            break

    # garante pelo menos o melhor pai, mesmo abaixo do limiar
    if not selecionados:
        pos = ordem[0]
        pai_id = filhos[candidatos[pos]]["pai"]
        selecionados = [dict(pais[pai_id], score=round(float(scores[pos]), 3))]
    return selecionados
