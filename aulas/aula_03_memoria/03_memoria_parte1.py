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

print("=" * 60)
print("CHAMADA 1 — O USUARIO SE APRESENTA")
print("=" * 60)

apresentacao = (
    "Oi! Meu nome é Ana\n"
    "e meu projeto é um sistema\n"
    "de estoque de uma farmácia."
)

resposta = cliente.chat.completions.create(
    model=modelo,
    messages=[{"role": "user", "content": apresentacao}],
    temperature=0,
)

print("USER     :", apresentacao)
print("ASSISTANT:", resposta.choices[0].message.content)

print("\nA Parte II da aula de memória não estava no material recebido.")
