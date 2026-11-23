import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

diretorio = Path(__file__).resolve().parent
load_dotenv(diretorio / ".env")

chave = os.getenv("OPENAI_API_KEY")
modelo = os.getenv("OPENAI_CHAT_MODEL", "openai/gpt-oss-120b")

if not chave:
    raise SystemExit("ERRO: Chave da API não encontrada no .env")

cliente = OpenAI(
    api_key=chave,
    base_url="https://api.groq.com/openai/v1"
)

try:
    resposta = cliente.chat.completions.create(
        model=modelo,
        messages=[
            {
                "role": "user",
                "content": "Olá! Explique brevemente o que é inteligência artificial."
            }
        ]
    )

    print("\nCONEXÃO COM GROQ REALIZADA COM SUCESSO!")
    print("\nResposta da IA:")
    print(resposta.choices[0].message.content)

except Exception as erro:
    print("\nERRO AO CONECTAR COM A GROQ:")
    print(erro)