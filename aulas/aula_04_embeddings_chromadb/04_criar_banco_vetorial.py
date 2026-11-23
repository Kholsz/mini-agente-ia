import re
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from pypdf import PdfReader

RAIZ = Path(__file__).resolve().parents[2]
CAMINHO_PDF = RAIZ / "dados" / "faq_projeto_exemplo.pdf"
CAMINHO_BANCO = RAIZ / "dados" / "banco_vetorial_faq"
NOME_COLECAO = "faq_colecao_multilingual"
MODELO_EMBEDDING = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DISTANCIA_MAXIMA = 0.62


def dividir_resposta(texto, limite=1000):
    if len(texto) <= limite:
        return [texto]

    frases = re.split(r"(?<=[.!?])\s+", texto)
    partes = []
    atual = ""

    for frase in frases:
        if not frase:
            continue
        candidato = f"{atual} {frase}".strip()
        if len(candidato) <= limite:
            atual = candidato
        else:
            if atual:
                partes.append(atual)
            ultima_frase = re.split(r"(?<=[.!?])\s+", atual)[-1] if atual else ""
            sobreposicao = f"{ultima_frase} {frase}".strip()
            if len(sobreposicao) <= limite:
                atual = sobreposicao
            elif len(frase) <= limite:
                atual = frase
            else:
                palavras = frase.split()
                atual = ""
                for palavra in palavras:
                    candidato = f"{atual} {palavra}".strip()
                    if len(candidato) <= limite:
                        atual = candidato
                    else:
                        if atual:
                            partes.append(atual)
                        atual = palavra
    if atual:
        partes.append(atual)

    return partes


def extrair_perguntas_respostas(texto):
    linhas = [re.sub(r"\s+", " ", linha).strip() for linha in texto.splitlines()]
    entradas = []
    secao = ""
    pergunta = None
    resposta = []

    def finalizar():
        if pergunta and resposta:
            texto_resposta = " ".join(resposta).strip()
            for indice, parte in enumerate(dividir_resposta(texto_resposta), start=1):
                documento = f"Seção: {secao}\nPergunta: {pergunta}\nResposta: {parte}".strip()
                entradas.append(
                    {
                        "document": documento,
                        "section": secao or "Geral",
                        "question": pergunta,
                        "part": indice,
                    }
                )

    for linha in linhas:
        if not linha or linha == "\x0c":
            continue

        if re.match(r"^\d+\.\s+", linha):
            finalizar()
            pergunta = None
            resposta = []
            secao = linha
        elif linha.endswith("?") and len(linha) <= 240:
            finalizar()
            pergunta = linha
            resposta = []
        elif pergunta:
            resposta.append(linha)

    finalizar()
    return entradas


if not CAMINHO_PDF.is_file():
    raise SystemExit(f"PDF nao encontrado: {CAMINHO_PDF}")

leitor = PdfReader(str(CAMINHO_PDF))
texto_pdf = "\n".join(pagina.extract_text() or "" for pagina in leitor.pages)
entradas = extrair_perguntas_respostas(texto_pdf)

if not entradas:
    raise SystemExit("Nao foi possivel identificar perguntas e respostas no PDF.")

embedding_function = SentenceTransformerEmbeddingFunction(
    model_name=MODELO_EMBEDDING,
    device="cpu",
    normalize_embeddings=True,
)

cliente_chroma = chromadb.PersistentClient(path=str(CAMINHO_BANCO))
nomes_colecoes = {
    item.name if hasattr(item, "name") else str(item)
    for item in cliente_chroma.list_collections()
}

if NOME_COLECAO in nomes_colecoes:
    cliente_chroma.delete_collection(name=NOME_COLECAO)

colecao = cliente_chroma.create_collection(
    name=NOME_COLECAO,
    metadata={"hnsw:space": "cosine"},
    embedding_function=embedding_function,
)

ids = [f"faq_{indice:04d}" for indice in range(1, len(entradas) + 1)]
documentos = [entrada["document"] for entrada in entradas]
metadados = [
    {
        "section": entrada["section"],
        "question": entrada["question"],
        "part": entrada["part"],
        "source": CAMINHO_PDF.name,
    }
    for entrada in entradas
]

colecao.add(ids=ids, documents=documentos, metadatas=metadados)
print(f"{len(documentos)} trechos de FAQ organizados por pergunta e resposta.")

pergunta_teste = "Qual e a politica de garantia e devolucao?"
resultado = colecao.query(
    query_texts=[pergunta_teste],
    n_results=min(4, colecao.count()),
    include=["documents", "distances", "metadatas"],
)

print("\n--- Teste de Busca ---")
print("Pergunta:", pergunta_teste)
selecionados = []
for documento, distancia, metadata in zip(
    resultado["documents"][0],
    resultado["distances"][0],
    resultado["metadatas"][0],
):
    if distancia <= DISTANCIA_MAXIMA:
        selecionados.append((documento, distancia, metadata))

if not selecionados:
    print("Nenhum trecho atingiu o limite inicial de relevancia.")
else:
    for documento, distancia, metadata in selecionados[:2]:
        print(f"\nDistancia: {distancia:.3f}")
        print(f"Pergunta no FAQ: {metadata.get('question', '')}")
        print(documento)
