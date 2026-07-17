"""
Memória de curto prazo: histórico da sessão atual (em memória RAM).
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class Mensagem:
    role: str    # "user" | "assistant" | "system"
    content: str


@dataclass
class ShortTermMemory:
    historico: List[Mensagem] = field(default_factory=list)
    max_mensagens: int = 20

    def adicionar(self, role: str, content: str):
        self.historico.append(Mensagem(role=role, content=content))
        if len(self.historico) > self.max_mensagens:
            # preserva sempre o primeiro system message + últimas N-1
            sistema = [m for m in self.historico if m.role == "system"][:1]
            resto = [m for m in self.historico if m.role != "system"]
            self.historico = sistema + resto[-(self.max_mensagens - 1):]

    def para_openai(self) -> List[dict]:
        return [{"role": m.role, "content": m.content} for m in self.historico]

    def resumo(self) -> str:
        """Últimas 3 trocas para debug."""
        linhas = [
            f"{m.role.upper()}: {m.content[:120]}"
            for m in self.historico
            if m.role != "system"
        ]
        return "\n".join(linhas[-6:])
