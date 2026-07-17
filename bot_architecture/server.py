"""Servidor web: API REST (/api/chat) + página de chat (/).

Rodar:  uvicorn server:app --reload --port 8000
Depois: abra http://localhost:8000
"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from rag import criar_indice
from chat import responder

app = FastAPI(title="Bot infra_mini_cloud")

# índice carregado UMA vez no startup (não a cada requisição)
INDICE = None


@app.on_event("startup")
def carregar():
    global INDICE
    INDICE = criar_indice()


class Pergunta(BaseModel):
    pergunta: str
    historico: list[dict] = []


@app.post("/api/chat")
def chat(req: Pergunta):
    r = responder(INDICE, req.pergunta, req.historico)
    return r


@app.get("/health")
def health():
    return {"status": "ok", "indexado": INDICE is not None}


PAGINA = """
<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<title>Bot infra_mini_cloud</title>
<style>
 body{font-family:system-ui;max-width:760px;margin:24px auto;padding:0 12px}
 #chat{border:1px solid #ddd;border-radius:8px;padding:12px;height:60vh;overflow:auto}
 .msg{margin:8px 0;padding:8px 12px;border-radius:8px;white-space:pre-wrap}
 .user{background:#e8f0fe;text-align:right}
 .bot{background:#f5f5f5}
 .meta{color:#888;font-size:12px;margin-top:4px}
 #linha{display:flex;gap:8px;margin-top:12px}
 #q{flex:1;padding:10px} button{padding:10px 16px}
</style></head><body>
<h2>Bot da stack infra_mini_cloud</h2>
<div id="chat"></div>
<div id="linha"><input id="q" placeholder="Pergunte algo..." autofocus>
<button onclick="enviar()">Enviar</button></div>
<script>
let historico=[];
const chat=document.getElementById('chat'), q=document.getElementById('q');
function add(txt,classe,meta){
  const d=document.createElement('div'); d.className='msg '+classe; d.textContent=txt;
  if(meta){const m=document.createElement('div'); m.className='meta'; m.textContent=meta; d.appendChild(m);}
  chat.appendChild(d); chat.scrollTop=chat.scrollHeight;
}
async function enviar(){
  const pergunta=q.value.trim(); if(!pergunta)return;
  add(pergunta,'user'); q.value=''; add('...','bot');
  const carregando=chat.lastChild;
  try{
    const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({pergunta,historico})});
    const j=await r.json();
    carregando.remove();
    add(j.texto,'bot',`fontes: ${j.fontes.join(', ')} · US$ ${j.custo.toFixed(5)} · ${j.latencia}s`);
    historico.push({role:'user',content:pergunta});
    historico.push({role:'assistant',content:j.texto});
    historico=historico.slice(-12);
  }catch(e){carregando.remove(); add('erro: '+e,'bot');}
}
q.addEventListener('keydown',e=>{if(e.key==='Enter')enviar();});
</script></body></html>
"""


@app.get("/", response_class=HTMLResponse)
def home():
    return PAGINA
