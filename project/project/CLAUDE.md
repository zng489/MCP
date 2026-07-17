# Projeto RAIS 2024

Consulta dos dados da RAIS 2024 (Relação Anual de Informações Sociais) hospedados
no MotherDuck, via DuckDB. Inclui um agente autônomo que escreve o SQL sozinho a
partir de perguntas em linguagem natural.

## Regra principal

**Para qualquer pergunta sobre os dados da RAIS, execute o agente:**

```bash
python agente_rais.py "<a pergunta do usuário>"
```

Mostre ao usuário a resposta final do agente e os SQLs que ele decidiu rodar
(as linhas `→ SQL:` que saem no stderr). Não escreva o SQL você mesmo — deixe o
agente decidir.

## Arquivos

- `agente_rais.py` — o agente autônomo (cérebro = DeepSeek). Recebe a pergunta,
  decide o SQL, executa via `rais_2024.py`, e responde.
- `rais_2024.py` — a ferramenta: função `query_rais(sql)` que roda SQL no MotherDuck.
  Também funciona como script: `python rais_2024.py "SELECT ..."`.
- `.env` — segredos (NÃO versionado): `DEEPSEEK_API_KEY` e `MOTHERDUCK_TOKEN`.

## Detalhes técnicos

- Tabela principal: `mte.rais_ident_2024` (dialeto DuckDB).
- Duas chaves, lidas do `.env` automaticamente:
  - `DEEPSEEK_API_KEY` → o cérebro (o modelo que pensa)
  - `MOTHERDUCK_TOKEN` → os dados (o banco)
- Somente leitura: nunca rodar INSERT/UPDATE/DELETE/DROP nos dados.
- Dependências: `pip install openai duckdb pandas python-dotenv`

## Futuro / notas

- `docs/HOOKS.md` — referência (ainda NÃO implementada) de como automatizar o
  roteamento de perguntas da RAIS de forma determinística via hook do Claude Code.
  Hoje o roteamento é feito por esta `CLAUDE.md`.
