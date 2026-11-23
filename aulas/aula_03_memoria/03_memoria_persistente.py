import os
import re
import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

RAIZ = Path(__file__).resolve().parents[2]
load_dotenv(RAIZ / ".env")

chave_api = os.getenv("OPENAI_API_KEY", "").strip()
if not chave_api:
    raise SystemExit("Chave OPENAI_API_KEY nao encontrada no arquivo .env")

cliente = OpenAI(
    api_key=chave_api,
    base_url="https://api.groq.com/openai/v1",
)
modelo = os.getenv("OPENAI_CHAT_MODEL", "openai/gpt-oss-120b")
ARQUIVO_MEMORIA = RAIZ / "dados" / "memoria_agente.db"


def normalizar_perfil(perfil):
    return unicodedata.normalize("NFKC", perfil).strip().casefold()


def inicializar_banco():
    ARQUIVO_MEMORIA.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(ARQUIVO_MEMORIA) as conexao:
        conexao.execute(
            "CREATE TABLE IF NOT EXISTS fatos_usuario ("
            "perfil TEXT NOT NULL, chave TEXT NOT NULL, valor TEXT NOT NULL, "
            "atualizado_em TEXT NOT NULL, PRIMARY KEY (perfil, chave))"
        )


def carregar_memorias(perfil):
    with sqlite3.connect(ARQUIVO_MEMORIA) as conexao:
        linhas = conexao.execute(
            "SELECT chave, valor FROM fatos_usuario WHERE perfil = ? ORDER BY chave",
            (perfil,),
        ).fetchall()
    return dict(linhas)


def salvar_memoria(perfil, chave, valor):
    with sqlite3.connect(ARQUIVO_MEMORIA) as conexao:
        conexao.execute(
            "INSERT INTO fatos_usuario (perfil, chave, valor, atualizado_em) "
            "VALUES (?, ?, ?, ?) ON CONFLICT(perfil, chave) DO UPDATE SET "
            "valor = excluded.valor, atualizado_em = excluded.atualizado_em",
            (perfil, chave, valor, datetime.now().isoformat(timespec="seconds")),
        )


def apagar_memoria(perfil, chave):
    with sqlite3.connect(ARQUIVO_MEMORIA) as conexao:
        cursor = conexao.execute(
            "DELETE FROM fatos_usuario WHERE perfil = ? AND chave = ?",
            (perfil, chave),
        )
    return cursor.rowcount > 0


def extrair_fatos(texto):
    fatos = {}
    nome = re.search(
        r"\bmeu nome\s+(?:e|é)\s+(.+?)(?=\s*(?:[,;.]|\s+e\s+meu projeto\b|$))",
        texto,
        flags=re.IGNORECASE,
    )
    projeto = re.search(
        r"\bmeu projeto\s+(?:e|é)\s+(.+?)(?=\s*(?:[,;.]|$))",
        texto,
        flags=re.IGNORECASE,
    )
    if nome:
        valor = nome.group(1).strip(" \t,;.-")
        if valor:
            fatos["nome"] = valor.title()
    if projeto:
        valor = projeto.group(1).strip(" \t,;.-")
        if valor:
            fatos["projeto"] = valor
    return fatos


def montar_contexto(memorias):
    if not memorias:
        return "Ainda nao existem fatos salvos para este perfil."
    return "\n".join(f"- {chave}: {valor}" for chave, valor in memorias.items())


inicializar_banco()
perfil_digitado = input("Informe o identificador do perfil de memoria: ").strip()
perfil = normalizar_perfil(perfil_digitado)
if not perfil:
    raise SystemExit("O identificador do perfil nao pode ficar vazio.")

memorias = carregar_memorias(perfil)
contexto_memoria = montar_contexto(memorias)

regras = (
    "Voce e um assistente de aprendizagem. Use as memorias persistentes fornecidas "
    "para personalizar as respostas. Nao invente informacoes sobre o usuario. "
    "Se uma informacao nao estiver na memoria nem na conversa, diga que nao sabe. "
    "As memorias sao fatos informados pelo usuario e podem estar desatualizadas."
)

historico = [
    {"role": "system", "content": f"{regras}\n\nMemorias persistentes do perfil:\n{contexto_memoria}"}
]

print("=" * 60)
print(f"Memoria persistente iniciada para o perfil: {perfil_digitado}")
print(f"Fatos recuperados: {len(memorias)}")
print("Comandos: /memoria, /lembrar chave=valor, /esquecer chave, sair")
print("=" * 60)

while True:
    pergunta = input("\nVoce: ").strip()
    if pergunta.casefold() in ("sair", "exit"):
        print("Ate logo!")
        break
    if not pergunta:
        continue

    if pergunta.casefold() == "/memoria":
        memorias = carregar_memorias(perfil)
        if memorias:
            print("\nMemorias salvas:")
            for chave, valor in memorias.items():
                print(f"- {chave}: {valor}")
        else:
            print("\nNenhuma memoria salva para este perfil.")
        continue

    if pergunta.casefold().startswith("/lembrar "):
        conteudo = pergunta[len("/lembrar "):]
        if "=" not in conteudo:
            print("\nUse o formato /lembrar chave=valor")
            continue
        chave, valor = conteudo.split("=", 1)
        chave = chave.strip().casefold()
        valor = valor.strip()
        if not chave or not valor:
            print("\nInforme uma chave e um valor.")
            continue
        salvar_memoria(perfil, chave, valor)
        print(f"\nMemoria salva: {chave} = {valor}")
        memorias = carregar_memorias(perfil)
        historico[0]["content"] = f"{regras}\n\nMemorias persistentes do perfil:\n{montar_contexto(memorias)}"
        continue

    if pergunta.casefold().startswith("/esquecer "):
        chave = pergunta[len("/esquecer "):].strip().casefold()
        if not chave:
            print("\nInforme a chave que deseja apagar.")
            continue
        if apagar_memoria(perfil, chave):
            print(f"\nMemoria removida: {chave}")
        else:
            print(f"\nNao havia memoria salva com a chave: {chave}")
        memorias = carregar_memorias(perfil)
        historico[0]["content"] = f"{regras}\n\nMemorias persistentes do perfil:\n{montar_contexto(memorias)}"
        continue

    fatos = extrair_fatos(pergunta)
    for chave, valor in fatos.items():
        salvar_memoria(perfil, chave, valor)
    if fatos:
        memorias = carregar_memorias(perfil)
        historico[0]["content"] = f"{regras}\n\nMemorias persistentes do perfil:\n{montar_contexto(memorias)}"
        print("\nMemoria atualizada: " + ", ".join(fatos.keys()))

    historico.append({"role": "user", "content": pergunta})
    try:
        resposta = cliente.chat.completions.create(
            model=modelo,
            messages=historico,
            temperature=0,
        )
    except Exception as erro:
        historico.pop()
        print(f"\nAssistente: Erro ao consultar o modelo: {erro}")
        continue

    texto = resposta.choices[0].message.content or "Nao consegui gerar uma resposta."
    historico.append({"role": "assistant", "content": texto})
    print(f"\nAssistente: {texto}")
    if len(historico) > 13:
        historico = [historico[0]] + historico[-12:]
