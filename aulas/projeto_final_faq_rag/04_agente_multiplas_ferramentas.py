import csv
import json
import os
import re
import sqlite3
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
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

CAMINHO_BANCO = RAIZ / "dados" / "banco_vetorial_faq"
if not CAMINHO_BANCO.exists():
    raise SystemExit(
        "Banco vetorial nao encontrado. Execute primeiro "
        "aulas\\aula_04_embeddings_chromadb\\04_criar_banco_vetorial.py"
    )

cliente_chroma = chromadb.PersistentClient(path=str(CAMINHO_BANCO))
try:
    colecao = cliente_chroma.get_collection(
        name=NOME_COLECAO,
        embedding_function=embedding_function,
    )
except Exception as erro:
    raise SystemExit(
        "Colecao faq_colecao_multilingual nao encontrada. Recrie o banco vetorial antes de iniciar o agente."
    ) from erro

ARQUIVO_CHAMADOS = RAIZ / "dados" / "chamados_suporte.csv"

ARQUIVO_MEMORIA = RAIZ / "dados" / "memoria_agente.db"

def inicializar_memoria():
    ARQUIVO_MEMORIA.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(ARQUIVO_MEMORIA) as conexao:
        conexao.execute(
            "CREATE TABLE IF NOT EXISTS historicos_agente ("
            "perfil TEXT PRIMARY KEY, historico TEXT NOT NULL, "
            "solicitacao_suporte_pendente TEXT, atualizado_em TEXT NOT NULL)"
        )

def carregar_memoria(perfil):
    with sqlite3.connect(ARQUIVO_MEMORIA) as conexao:
        linha = conexao.execute(
            "SELECT historico, solicitacao_suporte_pendente "
            "FROM historicos_agente WHERE perfil = ?",
            (perfil,),
        ).fetchone()
    if not linha:
        return None, None
    try:
        historico_salvo = json.loads(linha[0])
        if not isinstance(historico_salvo, list) or not historico_salvo:
            return None, linha[1]
        return historico_salvo, linha[1]
    except (json.JSONDecodeError, TypeError):
        return None, None

def salvar_memoria(perfil, historico_atual, pendencia):
    if not perfil:
        return
    conteudo = json.dumps(historico_atual, ensure_ascii=False)
    with sqlite3.connect(ARQUIVO_MEMORIA) as conexao:
        conexao.execute(
            "INSERT INTO historicos_agente "
            "(perfil, historico, solicitacao_suporte_pendente, atualizado_em) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(perfil) DO UPDATE SET "
            "historico = excluded.historico, "
            "solicitacao_suporte_pendente = excluded.solicitacao_suporte_pendente, "
            "atualizado_em = excluded.atualizado_em",
            (perfil, conteudo, pendencia, datetime.now().isoformat(timespec="seconds")),
        )

def excluir_memoria(perfil):
    with sqlite3.connect(ARQUIVO_MEMORIA) as conexao:
        conexao.execute("DELETE FROM historicos_agente WHERE perfil = ?", (perfil,))

def normalizar_perfil(perfil):
    return unicodedata.normalize("NFKC", perfil).strip().casefold()


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in texto if not unicodedata.combining(c)).casefold()


def detectar_pedido_suporte(texto):
    texto = normalizar(texto)
    indicadores = (
        "quero falar com o suporte",
        "quero falar com suporte",
        "falar com o suporte",
        "falar com suporte",
        "abrir chamado",
        "abrir um chamado",
        "registrar chamado",
        "registrar um chamado",
        "preciso de suporte",
        "quero suporte",
        "chamar o suporte",
        "chamar suporte",
        "atendimento humano",
        "solicito suporte",
    )
    return any(indicador in texto for indicador in indicadores)


def extrair_nome(texto):
    padroes = (
        r"\bmeu nome\s+(?:é|e)\s+(.+?)(?=\s*(?:[,;.]|\s+e\s+(?:quero|preciso|gostaria)|$))",
        r"\bme chamo\s+(.+?)(?=\s*(?:[,;.]|\s+e\s+(?:quero|preciso|gostaria)|$))",
    )
    for padrao in padroes:
        correspondencia = re.search(padrao, texto, re.IGNORECASE)
        if correspondencia:
            nome = correspondencia.group(1).strip(" \t,;.-")
            if nome:
                return nome.title()
    return None


def nome_informado_isolado(texto):
    nome = texto.strip().strip(".,;:")
    if re.fullmatch(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ' -]{0,79}", nome):
        return nome.title()
    return None


def extrair_assunto(texto):
    assunto = texto

    assunto = re.sub(
        r"\bmeu nome\s+(?:é|e)\s+.+?(?=\s*(?:[,;.]|\s+e\s+(?:quero|preciso|gostaria)|$))",
        " ",
        assunto,
        flags=re.IGNORECASE,
    )
    assunto = re.sub(
        r"\bme chamo\s+.+?(?=\s*(?:[,;.]|\s+e\s+(?:quero|preciso|gostaria)|$))",
        " ",
        assunto,
        flags=re.IGNORECASE,
    )

    comandos = (
        r"\b(?:e\s+)?(?:eu\s+)?(?:quero|preciso\s+de|gostaria\s+de)\s+"
        r"(?:falar\s+com\s+(?:o\s+)?suporte|"
        r"abrir\s+(?:um\s+)?chamado|"
        r"registrar\s+(?:um\s+)?chamado|"
        r"chamar\s+(?:o\s+)?suporte|"
        r"receber\s+atendimento(?:\s+humano)?)\b"
    )
    assunto = re.sub(comandos, " ", assunto, flags=re.IGNORECASE)
    assunto = re.sub(r"\b(?:com|para)\s+suport(?:e)?\b", " ", assunto, flags=re.IGNORECASE)
    assunto = re.sub(r"\b(?:e\s+)?abrir\s+(?:um\s+)?chamado\b", " ", assunto, flags=re.IGNORECASE)
    assunto = re.sub(r"\b(?:e\s+)?falar\s+com\s+(?:o\s+)?suporte\b", " ", assunto, flags=re.IGNORECASE)
    assunto = re.sub(r"\b(?:e\s+)?quero\s+suporte\b", " ", assunto, flags=re.IGNORECASE)
    assunto = re.sub(r"\s+", " ", assunto)
    assunto = re.sub(r"^[\s,;:.\-]+|[\s,;:.\-]+$", "", assunto)
    assunto = re.sub(r"^(?:e\s+)?(?:porque|pois|sobre)\s+", "", assunto, flags=re.IGNORECASE)

    return assunto or "Solicitação de atendimento humano"


def buscar_no_faq(termo_busca):
    quantidade = min(QUANTIDADE_CANDIDATOS, colecao.count())
    if quantidade == 0:
        return "O FAQ ainda nao possui documentos cadastrados."

    resultado = colecao.query(
        query_texts=[termo_busca],
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
        return (
            "Nenhum trecho suficientemente relevante foi encontrado no FAQ. "
            "Informe ao cliente que essa informacao nao consta no FAQ e recomende o suporte humano."
        )

    melhor_distancia = min(item["distance"] for item in candidatos)
    candidatos = [
        item for item in candidatos
        if item["distance"] <= melhor_distancia + 0.16
    ]
    candidatos.sort(key=lambda item: item["distance"])

    blocos = []
    for indice, item in enumerate(candidatos[:QUANTIDADE_CONTEXTO], start=1):
        metadata = item["metadata"]
        blocos.append(
            f"Trecho {indice}\n"
            f"Pergunta do FAQ: {metadata.get('question', 'Nao identificada')}\n"
            f"Conteudo: {item['document']}\n"
            f"Distancia semantica: {item['distance']:.3f}"
        )

    return "\n\n---\n\n".join(blocos)


def calcular_desconto_pix(valor, tipo):
    if tipo not in ("produto", "servico"):
        raise ValueError("O tipo deve ser 'produto' ou 'servico'.")

    try:
        valor_decimal = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        raise ValueError("O valor informado nao e um numero valido.")

    if not valor_decimal.is_finite() or valor_decimal <= 0:
        raise ValueError("O valor deve ser maior que zero.")

    percentual = Decimal("0.10") if tipo == "produto" else Decimal("0.05")
    valor_final = (valor_decimal * (Decimal("1") - percentual)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    desconto = (valor_decimal - valor_final).quantize(Decimal("0.01"))

    return (
        f"Valor original: R$ {valor_decimal:.2f} | "
        f"Desconto PIX: {percentual * 100:.0f}% (R$ {desconto:.2f}) | "
        f"Valor final: R$ {valor_final:.2f}"
    )


def abrir_chamado_suporte(nome_cliente, assunto):
    nome_cliente = str(nome_cliente).strip()
    assunto = str(assunto).strip()

    if not nome_cliente:
        raise ValueError("O nome do cliente e obrigatorio.")
    if not assunto:
        raise ValueError("O assunto do chamado e obrigatorio.")

    ARQUIVO_CHAMADOS.parent.mkdir(parents=True, exist_ok=True)
    agora = datetime.now()
    numero_chamado = agora.strftime("%Y%m%d%H%M%S%f")
    precisa_cabecalho = not ARQUIVO_CHAMADOS.exists() or ARQUIVO_CHAMADOS.stat().st_size == 0

    with ARQUIVO_CHAMADOS.open("a", newline="", encoding="utf-8") as arquivo:
        escritor = csv.writer(arquivo)
        if precisa_cabecalho:
            escritor.writerow(["numero_chamado", "cliente", "assunto", "data_hora"])
        escritor.writerow([numero_chamado, nome_cliente, assunto, agora.isoformat(timespec="microseconds")])

    return f"Chamado #{numero_chamado} aberto com sucesso para {nome_cliente}."


ferramentas = [
    {
        "type": "function",
        "function": {
            "name": "buscar_no_faq",
            "description": "Busca informacoes oficiais no FAQ sobre produtos, precos, regras e suporte.",
            "parameters": {
                "type": "object",
                "properties": {
                    "termo_busca": {"type": "string", "description": "Assunto ou duvida a pesquisar"}
                },
                "required": ["termo_busca"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calcular_desconto_pix",
            "description": "Calcula o preco final com desconto PIX: 10% para produto e 5% para servico.",
            "parameters": {
                "type": "object",
                "properties": {
                    "valor": {"type": "number", "description": "Valor original em reais"},
                    "tipo": {"type": "string", "enum": ["produto", "servico"]},
                },
                "required": ["valor", "tipo"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "abrir_chamado_suporte",
            "description": "Registra um chamado quando o cliente pede explicitamente atendimento humano.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nome_cliente": {"type": "string", "description": "Nome informado pelo cliente"},
                    "assunto": {"type": "string", "description": "Resumo do problema relatado"},
                },
                "required": ["nome_cliente", "assunto"],
                "additionalProperties": False,
            },
        },
    },
]

funcoes_disponiveis = {
    "buscar_no_faq": buscar_no_faq,
    "calcular_desconto_pix": calcular_desconto_pix,
    "abrir_chamado_suporte": abrir_chamado_suporte,
}

INSTRUCOES_SISTEMA = (
    "Voce e o assistente virtual da TechStore e possui tres ferramentas. "
    "Use buscar_no_faq para duvidas sobre produtos, precos, regras e suporte. "
    "Use calcular_desconto_pix para calcular o valor final no PIX: 10% para produtos e 5% para servicos. "
    "Quando o cliente pedir explicitamente para falar com o suporte ou abrir chamado, "
    "o programa chamara a ferramenta de registro. Nao afirme que um chamado foi aberto sem o resultado da ferramenta. "
    "Responda sobre politicas da empresa somente com base nos trechos relevantes retornados pelo FAQ. "
    "Se a ferramenta informar que nenhum trecho suficientemente relevante foi encontrado, "
    "diga que a informacao nao consta no FAQ. Nao use conhecimento externo para completar lacunas. "
    "Nao invente prazos, garantias, beneficios ou procedimentos que nao estejam no FAQ. "
    "Se o FAQ nao trouxer a informacao, diga que nao encontrou a resposta e recomende o suporte humano. "
    "Para cumprimentos e perguntas gerais, responda diretamente. "
    "Use o historico anterior como contexto da conversa, mas nao trate informacoes antigas como politicas oficiais da loja."
)

def novo_historico():
    return [{"role": "system", "content": INSTRUCOES_SISTEMA}]

inicializar_memoria()
print("=" * 60)
print("Agente com 3 ferramentas e memoria persistente")
print("=" * 60)
ativar_memoria = input("Deseja salvar e recuperar o historico neste computador? (s/n): ").strip().casefold() in ("s", "sim")
perfil_memoria = ""
historico = novo_historico()
solicitacao_suporte_pendente = None

if ativar_memoria:
    perfil_digitado = input("Informe um identificador para este perfil (ex.: ana): ").strip()
    perfil_memoria = normalizar_perfil(perfil_digitado)
    if not perfil_memoria:
        raise SystemExit("Perfil vazio. Execute novamente e informe um identificador.")
    historico_salvo, pendencia_salva = carregar_memoria(perfil_memoria)
    if historico_salvo:
        historico = historico_salvo
        historico[0] = {"role": "system", "content": INSTRUCOES_SISTEMA}
        solicitacao_suporte_pendente = pendencia_salva
        print(f"Memoria recuperada para o perfil: {perfil_digitado}")
        print(f"Mensagens recuperadas: {max(0, len(historico) - 1)}")
    else:
        print(f"Novo perfil de memoria criado: {perfil_digitado}")
else:
    print("Memoria persistente desativada nesta sessao.")

print("Comandos: /memoria, /limpar_memoria e sair")
print("=" * 60)

while True:
    pergunta = input("\nVoce: ").strip()

    if pergunta.casefold() in ("sair", "exit"):
        salvar_memoria(perfil_memoria, historico, solicitacao_suporte_pendente)
        print("Ate logo!")
        break
    if not pergunta:
        continue

    if pergunta.casefold() == "/memoria":
        if not perfil_memoria:
            print("\nAgente: A memoria persistente esta desativada nesta sessao.")
        else:
            print(f"\nAgente: Perfil ativo: {perfil_memoria}")
            print(f"Mensagens armazenadas: {max(0, len(historico) - 1)}")
            print(f"Arquivo local: {ARQUIVO_MEMORIA}")
        continue

    if pergunta.casefold() == "/limpar_memoria":
        if not perfil_memoria:
            print("\nAgente: A memoria persistente esta desativada nesta sessao.")
            continue
        confirmacao = input("Apagar o historico salvo deste perfil? (s/n): ").strip().casefold()
        if confirmacao in ("s", "sim"):
            excluir_memoria(perfil_memoria)
            historico = novo_historico()
            solicitacao_suporte_pendente = None
            print("\nAgente: Memoria do perfil apagada.")
        else:
            print("\nAgente: Operacao cancelada.")
        continue

    if solicitacao_suporte_pendente is not None:
        nome_informado = extrair_nome(pergunta) or nome_informado_isolado(pergunta)
        if not nome_informado:
            print("\nAgente: Informe seu nome para que eu possa registrar o chamado.")
            continue

        texto_do_problema = solicitacao_suporte_pendente
        solicitacao_suporte_pendente = None
        historico.append({"role": "user", "content": pergunta})
        pedido_explicito_suporte = True
    else:
        historico.append({"role": "user", "content": pergunta})
        pedido_explicito_suporte = detectar_pedido_suporte(pergunta)
        nome_informado = extrair_nome(pergunta) if pedido_explicito_suporte else None
        texto_do_problema = pergunta

        if pedido_explicito_suporte and not nome_informado:
            solicitacao_suporte_pendente = pergunta
            salvar_memoria(perfil_memoria, historico, solicitacao_suporte_pendente)
            print("\nAgente: Para registrar o chamado, informe seu nome.")
            continue

    if pedido_explicito_suporte:
        assunto_informado = extrair_assunto(texto_do_problema)
        parametros = {
            "model": modelo,
            "messages": historico,
            "tools": ferramentas,
            "tool_choice": {
                "type": "function",
                "function": {"name": "abrir_chamado_suporte"},
            },
            "temperature": 0,
        }

        try:
            resposta = cliente.chat.completions.create(**parametros)
            mensagem = resposta.choices[0].message
        except Exception as erro:
            salvar_memoria(perfil_memoria, historico, solicitacao_suporte_pendente)
            print(f"\nAgente: Nao foi possivel solicitar a ferramenta de suporte: {erro}")
            continue

        historico.append(mensagem.model_dump(exclude_none=True))
        chamadas = mensagem.tool_calls or []
        if not chamadas:
            salvar_memoria(perfil_memoria, historico, solicitacao_suporte_pendente)
            print("\nAgente: Nao consegui executar a abertura do chamado. Tente novamente.")
            continue

        pedido = chamadas[0]
        if pedido.function.name != "abrir_chamado_suporte":
            salvar_memoria(perfil_memoria, historico, solicitacao_suporte_pendente)
            print("\nAgente: O modelo selecionou uma ferramenta inesperada. Nenhum chamado foi registrado.")
            continue

        argumentos = {
            "nome_cliente": nome_informado,
            "assunto": assunto_informado,
        }

        try:
            resultado = abrir_chamado_suporte(**argumentos)
        except Exception as erro:
            resultado = f"Erro ao registrar o chamado: {erro}"
            print(f"\nAgente: {resultado}")
            salvar_memoria(perfil_memoria, historico, solicitacao_suporte_pendente)
            continue

        historico.append(
            {
                "role": "tool",
                "tool_call_id": pedido.id,
                "content": resultado,
            }
        )
        historico.append({"role": "assistant", "content": resultado})
        print(f"\nAgente: {resultado}")
        if len(historico) > 31:
            historico = [historico[0]] + historico[-30:]
        salvar_memoria(perfil_memoria, historico, solicitacao_suporte_pendente)
        continue

    for tentativa in range(5):
        parametros = {
            "model": modelo,
            "messages": historico,
            "tools": ferramentas,
            "tool_choice": "auto",
            "temperature": 0,
        }

        try:
            resposta = cliente.chat.completions.create(**parametros)
        except Exception as erro:
            print(f"\nAgente: Ocorreu um erro ao consultar o modelo: {erro}")
            break

        mensagem = resposta.choices[0].message
        historico.append(mensagem.model_dump(exclude_none=True))

        if not mensagem.tool_calls:
            print(f"\nAgente: {mensagem.content or 'Nao consegui gerar uma resposta.'}")
            break

        for pedido in mensagem.tool_calls:
            nome_funcao = pedido.function.name
            try:
                argumentos = json.loads(pedido.function.arguments or "{}")
            except json.JSONDecodeError:
                resultado_funcao = "Argumentos invalidos enviados para a ferramenta."
            else:
                funcao = funcoes_disponiveis.get(nome_funcao)
                if funcao is None:
                    resultado_funcao = f"Ferramenta desconhecida: {nome_funcao}"
                else:
                    try:
                        resultado_funcao = str(funcao(**argumentos))
                    except Exception as erro:
                        resultado_funcao = f"Erro ao executar {nome_funcao}: {erro}"

            print(f"   [Agente usou a ferramenta: {nome_funcao}]")
            print(f"   [Resultado: {resultado_funcao}]")
            historico.append(
                {
                    "role": "tool",
                    "tool_call_id": pedido.id,
                    "content": resultado_funcao,
                }
            )
    else:
        print("\nAgente: Nao consegui concluir a operacao dentro do limite de tentativas.")

    if len(historico) > 31:
        historico = [historico[0]] + historico[-30:]
    salvar_memoria(perfil_memoria, historico, solicitacao_suporte_pendente)
