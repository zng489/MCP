# Hooks — automação determinística (referência para o futuro)

> **Status: NÃO implementado.** Este documento é só uma referência caso, mais pra
> frente, a gente queira automatizar o roteamento de perguntas da RAIS de forma
> rígida. Hoje o projeto usa o `CLAUDE.md`, que já resolve bem.

## O que é um hook

Um **hook** é um comando de shell que o **próprio Claude Code (a ferramenta) executa
automaticamente** em certos momentos — não é o modelo que decide. Por isso é
determinístico: está programado pra rodar, e roda.

Diferença para o `CLAUDE.md`:

| | `CLAUDE.md` | Hook |
|---|---|---|
| O que é | uma *instrução* que o modelo segue | um *comando* que a ferramenta roda |
| Depende do modelo interpretar? | sim | não |
| Confiabilidade do disparo | alta | total (sempre roda no evento) |

### Eventos onde um hook pode disparar

| Evento | Quando dispara |
|---|---|
| `UserPromptSubmit` | quando você envia uma mensagem (antes do modelo ver) |
| `PreToolUse` | antes de o modelo usar uma ferramenta |
| `PostToolUse` | depois que uma ferramenta roda |
| `Stop` | quando o modelo termina de responder |
| `SessionStart` | ao abrir a conversa |

## A pegadinha do "determinístico"

O hook garante que **algo roda num evento** — mas ele **não sabe**, sozinho, se a sua
pergunta "é sobre RAIS". Isso é uma decisão semântica, e um hook é só um shell script.
Pra ele decidir, você cai em **comparação por palavra-chave** (procurar "RAIS",
"vínculo", "UF", "salário" no texto). Determinístico, mas tosco: erra perguntas que não
usam essas palavras e dispara em falso quando aparecem por acaso.

Resumo: o hook torna a **execução** garantida, não a **classificação** inteligente.

## Como seria feito (roteamento de perguntas da RAIS)

Um hook `UserPromptSubmit` que, ao enviar a mensagem, checa palavras-chave e — se bater —
roda o agente e injeta a resposta no contexto do modelo.

### 1. Pré-requisito

O script usa `jq` para ler o JSON da mensagem. Instalar:

```bash
sudo apt install jq      # Debian/Ubuntu
```

### 2. O script — `.claude/hooks/rais.sh`

```bash
#!/usr/bin/env bash
# Recebe um JSON no stdin com a mensagem do usuário no campo "prompt".
prompt=$(jq -r '.prompt')

# Se a mensagem mencionar termos da RAIS, roda o agente automaticamente.
if echo "$prompt" | grep -qiE 'rais|vínculo|vinculo|\buf\b|salári|município'; then
  echo "=== Resultado do agente_rais.py (executado automaticamente pelo hook) ==="
  python agente_rais.py "$prompt" 2>&1
fi
# Tudo que esse script imprime no stdout entra no contexto do modelo.
```

Tornar executável:

```bash
chmod +x .claude/hooks/rais.sh
```

### 3. Registrar em `.claude/settings.json`

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command", "command": "bash .claude/hooks/rais.sh" } ] }
    ]
  }
}
```

### Fluxo resultante

```
Você envia: "quais as 10 UFs com mais vínculos?"
   ↓
A ferramenta roda .claude/hooks/rais.sh ANTES do modelo
   ↓
o script vê "UF"/"vínculos" → roda agente_rais.py → captura o resultado
   ↓
o resultado já entra pronto no contexto do modelo
```

Não depende do modelo adivinhar nada.

## Quando vale a pena

- **Vale**: garantia rígida e automação sem supervisão — ex.: rodar testes antes de todo
  commit, bloquear comandos perigosos, formatar código automaticamente.
- **Não vale (ainda)**: rotear perguntas da RAIS. O `CLAUDE.md` já cobre isso com muito
  menos complexidade, e o hook herda a fragilidade da palavra-chave.

## Para implementar no futuro

1. Instalar `jq`.
2. Criar `.claude/hooks/rais.sh` (conteúdo acima) e dar `chmod +x`.
3. Criar/editar `.claude/settings.json` com o bloco de `hooks`.
4. Reabrir a conversa no projeto para o hook passar a valer.

Documentação oficial: https://docs.claude.com/en/docs/claude-code/hooks
