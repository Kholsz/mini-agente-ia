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

pergunta = "O que é um banco de dados?"

personagens = [
    "Você é um professor de crianças. Responda em 1 frase, com uma analogia.",
    "Você é um engenheiro de software sênior. Responda em 1 frase técnica.",
    "Você é um poeta de cordel. Responda com 4 versos rimados.",
    "Você só pode responder com uma única palavra.",
]

for system in personagens:
    resposta = cliente.chat.completions.create(
        model=modelo,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": pergunta},
        ],
        temperature=0,
    )
    print("=" * 60)
    print("SYSTEM   :", system)
    print("USER     :", pergunta)
    print("RESPOSTA :", resposta.choices[0].message.content)
