"""
PokéAPI MCP Server
Expõe as funções get_pokemon, get_type e list_pokemon como tools MCP.

Instalação:
    pip install mcp requests

Uso (stdio — para Claude Desktop / Claude Code):
    python pokeapi_mcp_server.py

Configuração no claude_desktop_config.json:
    {
      "mcpServers": {
        "pokeapi": {
          "command": "python",
          "args": ["/caminho/para/pokeapi_mcp_server.py"]
        }
      }
    }
"""

import requests
from mcp.server.fastmcp import FastMCP

BASE_URL = "https://pokeapi.co/api/v2"

mcp = FastMCP(
    "PokéAPI",
    instructions="Servidor MCP que consulta a PokéAPI. Use as tools para buscar Pokémon, tipos e listas.",
)


# ── Tools ──────────────────────────────────────────────────────────────────────


@mcp.tool()
def get_pokemon(name: str) -> dict:
    """Retorna detalhes de um Pokémon pelo nome ou ID.

    Args:
        name: Nome (ex: 'pikachu') ou ID numérico do Pokémon.

    Returns:
        Dicionário com id, name, types, abilities, stats e URL da imagem.
        Retorna mensagem de erro se não encontrado.
    """
    r = requests.get(f"{BASE_URL}/pokemon/{name.lower()}", timeout=10)
    if r.status_code != 200:
        return {"error": f"Pokémon '{name}' não encontrado."}
    d = r.json()
    return {
        "id": d["id"],
        "name": d["name"],
        "types": [t["type"]["name"] for t in d["types"]],
        "abilities": [a["ability"]["name"] for a in d["abilities"]],
        "stats": {s["stat"]["name"]: s["base_stat"] for s in d["stats"]},
        "image": d["sprites"]["front_default"],
    }


@mcp.tool()
def get_type(name: str) -> dict:
    """Retorna as relações de dano de um tipo Pokémon.

    Args:
        name: Nome do tipo (ex: 'fire', 'water', 'grass').

    Returns:
        Dicionário com o nome do tipo e suas relações:
        - forte_contra: tipos que recebem dano duplo
        - fraco_contra: tipos que recebem dano pela metade
        - sem_efeito: tipos imunes a este tipo
    """
    r = requests.get(f"{BASE_URL}/type/{name.lower()}", timeout=10)
    if r.status_code != 200:
        return {"error": f"Tipo '{name}' não encontrado."}
    d = r.json()
    return {
        "name": d["name"],
        "forte_contra": [t["name"] for t in d["damage_relations"]["double_damage_to"]],
        "fraco_contra": [t["name"] for t in d["damage_relations"]["half_damage_to"]],
        "sem_efeito": [t["name"] for t in d["damage_relations"]["no_damage_to"]],
    }


@mcp.tool()
def list_pokemon(limit: int = 20, offset: int = 0) -> list[dict]:
    """Lista Pokémon com paginação.

    Args:
        limit:  Quantidade de Pokémon a retornar (padrão: 20, máx: 100).
        offset: Posição inicial na lista (padrão: 0).

    Returns:
        Lista de dicionários com 'name' e 'url' de cada Pokémon.
    """
    limit = min(limit, 100)  # limita para não sobrecarregar a API
    r = requests.get(
        f"{BASE_URL}/pokemon",
        params={"limit": limit, "offset": offset},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["results"]


# ── Resources ──────────────────────────────────────────────────────────────────


@mcp.resource("pokemon://{name}")
def pokemon_resource(name: str) -> str:
    """Pokémon como recurso MCP (carregado no contexto do LLM)."""
    data = get_pokemon(name)
    if "error" in data:
        return data["error"]
    lines = [
        f"# {data['name'].capitalize()} (#{data['id']})",
        f"**Tipos:** {', '.join(data['types'])}",
        f"**Habilidades:** {', '.join(data['abilities'])}",
        "**Stats base:**",
        *[f"  - {stat}: {val}" for stat, val in data["stats"].items()],
        f"**Sprite:** {data['image']}",
    ]
    return "\n".join(lines)


@mcp.resource("type://{name}")
def type_resource(name: str) -> str:
    """Tipo Pokémon como recurso MCP."""
    data = get_type(name)
    if "error" in data:
        return data["error"]
    lines = [
        f"# Tipo: {data['name'].capitalize()}",
        f"**Forte contra:** {', '.join(data['forte_contra']) or '—'}",
        f"**Fraco contra:** {', '.join(data['fraco_contra']) or '—'}",
        f"**Sem efeito em:** {', '.join(data['sem_efeito']) or '—'}",
    ]
    return "\n".join(lines)


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Transporte padrão: stdio (ideal para Claude Desktop / Claude Code)
    # Para HTTP: mcp.run(transport="streamable-http")
    mcp.run()