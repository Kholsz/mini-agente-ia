import os
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
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
NOME_COLECAO = "faq_colecao_multilingual"
MODELO_EMBEDDING = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DISTANCIA_MAXIMA = 0.62
QUANTIDADE_CANDIDATOS = 4
QUANTIDADE_CONTEXTO = 2

embedding_function = SentenceTransformerEmbeddingFunction(
    model_name=MODELO_EMBEDDING,
    device="cpu",
    normalize_embeddings=True,
)

cliente_chroma = chromadb.PersistentClient(
    path=str(RAIZ / "dados" / "banco_vetorial_faq")
)

try:
    colecao = cliente_chroma.get_collection(
        name=NOME_COLECAO,
        embedding_function=embedding_function,
    )
except Exception as erro:
    raise SystemExit("Colecao multilíngue nao encontrada. Recrie o banco vetorial.") from erro

regras = (
    "Voce e um assistente virtual da TechStore. Responda usando somente os trechos atuais do FAQ. "
    "Nao use conhecimento externo para completar informacoes ausentes. "
    "Se os trechos nao responderem diretamente a pergunta, diga que nao encontrou essa informacao no FAQ "
    "e recomende contato com o suporte humano. Nao invente produtos, prazos, valores, garantias ou procedimentos. "
    "Diferencie uma informacao semelhante de uma confirmacao explicita."
)

historico = [{"role": "system", "content": regras}]


def recuperar_contexto(pergunta):
    quantidade = min(QUANTIDADE_CANDIDATOS, colecao.count())
    if quantidade == 0:
        return []

    resultado = colecao.query(
        query_texts=[pergunta],
        n_results=quantidade,
        include=["documents", "distances", "metadatas"],
    )

    documentos = resultado.get("documents", [[]])[0]
    distancias = resultado.get("distances", [[]])[0]
    metadados = resultado.get("metadatas", [[]])[0]
    candidatos = []

    for documento, distancia, metadata in zip(documentos, distancias, metadados):
        if distancia <= DISTANCIA_MAXIMA:
            candidatos.append(
                {
                    "document": documento,
                    "distance": float(distancia),
                    "metadata": metadata or {},
                }
            )

    if not candidatos:
        return []

    melhor_distancia = min(item["distance"] for item in candidatos)
    candidatos = [
        item for item in candidatos
        if item["distance"] <= melhor_distancia + 0.16
    ]
    candidatos.sort(key=lambda item: item["distance"])
    return candidatos[:QUANTIDADE_CONTEXTO]


print("=" * 60)
print("Chatbot RAG iniciado! Digite sua pergunta ou 'sair' para encerrar.")
print("=" * 60)

while True:
    pergunta = input("\nVoce: ").strip()

    if pergunta.casefold() in ("sair", "exit"):
        print("Ate logo!")
        break
    if not pergunta:
        continue

    trechos = recuperar_contexto(pergunta)
    if not trechos:
        print(
            "\nAssistente: Nao encontrei no FAQ um trecho suficientemente relacionado a essa pergunta. "
            "Recomendo entrar em contato com o suporte humano da TechStore."
        )
        continue

    blocos_contexto = []
    for indice, item in enumerate(trechos, start=1):
        metadata = item["metadata"]
        blocos_contexto.append(
            f"Trecho {indice}\n"
            f"Pergunta do FAQ: {metadata.get('question', 'Nao identificada')}\n"
            f"Conteudo: {item['document']}"
        )

    contexto = "\n\n---\n\n".join(blocos_contexto)
    mensagem_usuario = f"Trechos recuperados do FAQ:\n{contexto}\n\nPergunta do cliente: {pergunta}"
    historico.append({"role": "user", "content": mensagem_usuario})

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

    texto_resposta = resposta.choices[0].message.content or "Nao consegui gerar uma resposta."
    historico.append({"role": "assistant", "content": texto_resposta})
    print(f"\nAssistente: {texto_resposta}")

    if len(historico) > 13:
        historico = [historico[0]] + historico[-12:]
