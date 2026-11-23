import importlib.util
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
load_dotenv(RAIZ / ".env")

modulos = {
    "openai": "openai",
    "python-dotenv": "dotenv",
    "tiktoken": "tiktoken",
    "sentence-transformers": "sentence_transformers",
    "chromadb": "chromadb",
    "pandas": "pandas",
    "sqlalchemy": "sqlalchemy",
    "pypdf": "pypdf",
}

falhas = []
print("=" * 60)
print("VERIFICACAO DO AMBIENTE — MINI-AGENTE")
print("=" * 60)

if sys.version_info >= (3, 10):
    print(f"[OK] Python {sys.version.split()[0]}")
else:
    print(f"[ERRO] Python {sys.version.split()[0]} — necessario Python 3.10 ou superior")
    falhas.append("Python 3.10 ou superior")

for nome, modulo in modulos.items():
    if importlib.util.find_spec(modulo) is not None:
        print(f"[OK] {nome}")
    else:
        print(f"[ERRO] {nome} nao encontrado")
        falhas.append(nome)

chave = os.getenv("OPENAI_API_KEY", "").strip()
if chave:
    print("[OK] OPENAI_API_KEY encontrada no .env")
else:
    print("[ERRO] OPENAI_API_KEY ausente ou vazia no .env")
    falhas.append("OPENAI_API_KEY no .env")

faq = RAIZ / "dados" / "faq_projeto_exemplo.pdf"
if faq.is_file():
    print("[OK] dados/faq_projeto_exemplo.pdf")
else:
    print("[AVISO] dados/faq_projeto_exemplo.pdf ainda nao foi encontrado")

print("=" * 60)
if falhas:
    print("Ambiente com pendencias. Verifique os itens marcados com [ERRO].")
    raise SystemExit(1)

print("Ambiente OK — pronto para começar!")
