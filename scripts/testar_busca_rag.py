from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

RAIZ = Path(__file__).resolve().parents[1]
CAMINHO_BANCO = RAIZ / "dados" / "banco_vetorial_faq"
NOME_COLECAO = "faq_colecao_multilingual"
MODELO_EMBEDDING = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DISTANCIA_MAXIMA = 0.62
QUANTIDADE_CANDIDATOS = 4

embedding_function = SentenceTransformerEmbeddingFunction(
    model_name=MODELO_EMBEDDING,
    device="cpu",
    normalize_embeddings=True,
)

cliente_chroma = chromadb.PersistentClient(path=str(CAMINHO_BANCO))
try:
    colecao = cliente_chroma.get_collection(
        name=NOME_COLECAO,
        embedding_function=embedding_function,
    )
except Exception as erro:
    raise SystemExit("Colecao multilíngue nao encontrada. Recrie o banco vetorial.") from erro

consultas = [
    ("Garantia", "Qual e o prazo da garantia de fabrica?"),
    ("Devolucao", "Se eu comprar pela internet e mudar de ideia, quantos dias tenho?"),
    ("Pagamento", "Quais meios posso usar para pagar uma compra?"),
    ("Informacao ausente", "A TechStore vende smartphones da Samsung?"),
    ("Assistencia", "A loja faz instalacao do Windows?"),
]

print("=" * 68)
print("TESTE DE RECUPERACAO DO RAG")
print(f"Limite de distancia: {DISTANCIA_MAXIMA:.2f}")
print("=" * 68)

for categoria, pergunta in consultas:
    quantidade = min(QUANTIDADE_CANDIDATOS, colecao.count())
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
        candidatos.append((float(distancia), documento, metadata or {}))

    candidatos.sort(key=lambda item: item[0])
    melhor = candidatos[0][0] if candidatos else None
    aceitos = [
        item for item in candidatos
        if item[0] <= DISTANCIA_MAXIMA and item[0] <= melhor + 0.16
    ] if melhor is not None else []

    print(f"\n[{categoria}] {pergunta}")
    if not candidatos:
        print("Nenhum resultado retornado.")
        continue

    for distancia, documento, metadata in candidatos:
        status = "ACEITO" if (distancia, documento, metadata) in aceitos[:2] else "FILTRADO"
        pergunta_faq = metadata.get("question", "Pergunta nao identificada")
        print(f"{status} | distancia={distancia:.3f} | {pergunta_faq}")

    if aceitos:
        print(f"Trechos enviados ao modelo: {min(2, len(aceitos))}")
    else:
        print("Trechos enviados ao modelo: 0")
