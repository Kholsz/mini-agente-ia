import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

RAIZ = Path(__file__).resolve().parents[2]
load_dotenv(RAIZ / ".env")

chave_api = os.getenv("OPENAI_API_KEY")
if not chave_api:
    raise SystemExit("Chave OPENAI_API_KEY nao encontrada no arquivo .env")

cliente = OpenAI(
    api_key=chave_api,
    base_url="https://api.groq.com/openai/v1",
)
modelo = os.getenv("OPENAI_CHAT_MODEL", "openai/gpt-oss-120b")

pergunta = "O que é inteligência artificial?"

print("=" * 60)
print("PRIMEIRA CHAMADA — SEM INSTRUCAO DE SYSTEM")
print("=" * 60)
print("USER:", pergunta)

resposta = cliente.chat.completions.create(
    model=modelo,
    messages=[{"role": "user", "content": pergunta}],
    temperature=0,
)

print("ASSISTANT:", resposta.choices[0].message.content)
