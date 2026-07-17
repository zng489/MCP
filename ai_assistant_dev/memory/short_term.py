"""
Memória de curto prazo: histórico da sessão atual (em memória RAM).
"""
#from dataclasses import dataclass, field
from typing import List


#@dataclass
#class Mensagem:
#    role: str    # "user" | "assistant" | "system"
#    content: str





class Mensagem:
    # sem __init__ precisaria declarar os dados internos manualmente,
    # com __init__ vc declara varios de uma vez msg = Mensagem("user", "Olá")   # já nasce com os dados
    def __init__(self, 
                role: str, 
                content: str):
        self.role = role
        #print(self.role)
        self.content = content

    # Depurar — você consegue ver o que está dentro do objeto sem precisar acessar cada atributo manualmente.
    def __repr__(self):
        return f"Mensagem(role={self.role}, content={self.content})"



class ShortTermMemory:
    def __init__(self, max_mensagens: int = 20):
        self.historico: List[Mensagem] = []
        self.max_mensagens = max_mensagens

    def adicionar(self, role: str, content: str):

        self.historico.append(Mensagem(role=role, content=content))
        #print('ZHANG')
        #print(self.historico)
        #print(self.max_mensagens)
        if len(self.historico) > self.max_mensagens:
            sistema = [m for m in self.historico if m.role == "system"][:1]
            resto = [m for m in self.historico if m.role != "system"]
            self.historico = sistema + resto[-(self.max_mensagens - 1):]

    def para_openai(self) -> List[dict]:
        return [{"role": m.role, "content": m.content} for m in self.historico]

    def resumo(self) -> str:
        linhas = [
            f"{m.role.upper()}: {m.content[:120]}"
            for m in self.historico
            if m.role != "system"
        ]
        return "\n".join(linhas[-6:])



if __name__ == "__main__":
    mem = ShortTermMemory()
    mem.adicionar("system", "Você é um assistente de infraestrutura.")
    mem.adicionar("user", "Qual a porta do Jupyter?")
    mem.adicionar("assistant", "A porta do Jupyter é 8888.")

    #print(mem.historico)
    #print(mem.para_openai())
    print(mem.resumo())