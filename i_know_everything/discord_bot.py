# discord_bot.py
import json
import re
import traceback
from pathlib import Path
import yaml
import discord
from openai import OpenAI                       # SDK OpenAI apontando pro DeepSeek
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Carrega segredos/config do config.yaml (mesma pasta deste script)
HERE = Path(__file__).resolve().parent
cfg = yaml.safe_load((HERE / "config.yaml").read_text(encoding="utf-8"))

deepseek = OpenAI(api_key=cfg["deepseek_api_key"],
                  base_url=cfg.get("deepseek_base_url", "https://api.deepseek.com"))
MODEL = cfg.get("model", "deepseek-chat")
# Caminho absoluto pro server, pra não depender de onde o bot é iniciado
SERVER = StdioServerParameters(command="python", args=[str(HERE / "kb_server.py")])

def to_openai_tools(mcp_tools):
    return [{
        "type": "function",
        "function": {"name": t.name,
                     "description": t.description or "",
                     "parameters": t.inputSchema},
    } for t in mcp_tools.tools]

async def answer(question: str) -> str:
    async with stdio_client(SERVER) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = to_openai_tools(await session.list_tools())
            messages = [
                {"role": "system", "content":
                 "Você responde dúvidas SEMPRE consultando a base via tools antes de responder."},
                {"role": "user", "content": question},
            ]
            for _ in range(5):                  # limite de rodadas de tool-calling
                resp = deepseek.chat.completions.create(
                    model=MODEL, messages=messages, tools=tools)
                msg = resp.choices[0].message
                if not msg.tool_calls:
                    return msg.content
                messages.append(msg.model_dump())
                for call in msg.tool_calls:
                    args = json.loads(call.function.arguments or "{}")
                    result = await session.call_tool(call.function.name, args)
                    text = "\n".join(c.text for c in result.content if hasattr(c, "text"))
                    messages.append({"role": "tool",
                                     "tool_call_id": call.id, "content": text})
            return "Não consegui concluir (muitas iterações)."

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"[ON_READY] Logado como {client.user} (id={client.user.id}) — bot online.")

@client.event
async def on_message(message):
    print(f"[MSG] de={message.author} canal={message.channel} conteudo={message.content!r}")
    if message.author == client.user:
        return

    dm = isinstance(message.channel, discord.DMChannel)
    # menção direta de USUÁRIO (<@id>)
    mencionado = client.user in message.mentions
    # menção de CARGO do próprio bot (<@&id>) — é o que acontece com "@China Bot"
    if not mencionado and message.guild is not None:
        bot_role_ids = {r.id for r in message.guild.me.roles}
        mencionado = any(r.id in bot_role_ids for r in message.role_mentions)
    print(f"[MSG] mencionado={mencionado} dm={dm}")
    if not (mencionado or dm):
        return

    # Remove qualquer menção (usuário <@id>/<@!id> e cargo <@&id>) e espaços
    q = re.sub(r"<@[!&]?\d+>", "", message.content).strip()
    print(f"[MSG] pergunta limpa={q!r}")
    if not q:
        await message.channel.send("Manda a pergunta junto com a menção 🙂")
        return

    try:
        async with message.channel.typing():
            reply = await answer(q)
        reply = reply or "(resposta vazia)"
        print(f"[RESP] {reply[:200]!r}...")
        for i in range(0, len(reply), 1900):     # Discord limita 2000 chars/msg
            await message.channel.send(reply[i:i + 1900])
    except Exception as e:
        traceback.print_exc()                     # traceback completo no terminal
        await message.channel.send(f"Erro: {e}")

client.run(cfg["discord_token"])
