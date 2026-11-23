import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts"))
load_dotenv(RAIZ / ".env")

from estoque_database import banco_tem_dados, consultar_banco, inicializar_banco, registrar_movimentacao
from relatorios_estoque import gerar_relatorio_json

chave_api = os.getenv("OPENAI_API_KEY", "").strip()
if not chave_api:
    raise SystemExit("Chave OPENAI_API_KEY nao encontrada no arquivo .env")

cliente = OpenAI(api_key=chave_api, base_url="https://api.groq.com/openai/v1")
modelo = os.getenv("OPENAI_CHAT_MODEL", "openai/gpt-oss-120b")

inicializar_banco()
if not banco_tem_dados():
    raise SystemExit("Execute primeiro: python scripts\\criar_banco_estoque.py")


def consultar_estoque(operacao, termo="", limite=10):
    return consultar_banco(operacao, termo, limite)


def gerar_relatorio_estoque(tipo_relatorio, data_inicio=None, data_fim=None, termo=""):
    return gerar_relatorio_json(tipo_relatorio, data_inicio, data_fim, termo)

def movimentar_estoque(codigo, tipo, quantidade, motivo):
    try:
        resultado = registrar_movimentacao(codigo, tipo, quantidade, motivo)
        return json.dumps(resultado, ensure_ascii=False)
    except (ValueError, TypeError) as erro:
        return json.dumps({"status": "erro", "mensagem": str(erro)}, ensure_ascii=False)


ferramentas = [
    {
        "type": "function",
        "function": {
            "name": "consultar_estoque",
            "description": "Consulta produtos, precos, quantidades, estoque minimo, historico de movimentacoes e resumo do estoque. Esta ferramenta nao altera os dados.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operacao": {
                        "type": "string",
                        "enum": ["listar_produtos", "consultar_produto", "consultar_estoque_baixo", "historico_movimentacoes", "resumo_estoque"],
                    },
                    "termo": {"type": "string"},
                    "limite": {"type": "integer", "minimum": 1, "maximum": 50},
                },
                "required": ["operacao"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "movimentar_estoque",
            "description": "Registra uma entrada ou saida real no estoque e cria uma linha no historico SQL. Use somente quando o usuario pedir explicitamente para registrar, dar entrada, dar baixa ou retirar unidades. Nunca use para perguntas de consulta. Nunca invente codigo, tipo, quantidade ou motivo. Se faltar qualquer informacao, pergunte antes de chamar a ferramenta. Para saidas, o sistema valida o saldo e bloqueia estoque negativo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "codigo": {"type": "string", "description": "Codigo exato do produto, por exemplo MED001."},
                    "tipo": {"type": "string", "enum": ["entrada", "saida"]},
                    "quantidade": {"type": "integer", "minimum": 1},
                    "motivo": {"type": "string", "minLength": 3, "maxLength": 200},
                },
                "required": ["codigo", "tipo", "quantidade", "motivo"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gerar_relatorio_estoque",
            "description": "Gera e salva arquivos CSV de relatorios do estoque. Use quando o usuario pedir para gerar, exportar ou preparar um relatorio. Para movimentacoes_periodo, informe data_inicio e data_fim no formato AAAA-MM-DD; se faltarem, pergunte antes de chamar. Tipos: estoque_completo, estoque_baixo, historico_movimentacoes, movimentacoes_periodo e resumo_estoque.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tipo_relatorio": {
                        "type": "string",
                        "enum": ["estoque_completo", "estoque_baixo", "historico_movimentacoes", "movimentacoes_periodo", "resumo_estoque"],
                    },
                    "data_inicio": {"type": "string", "description": "Data inicial no formato AAAA-MM-DD."},
                    "data_fim": {"type": "string", "description": "Data final no formato AAAA-MM-DD."},
                    "termo": {"type": "string", "description": "Filtro opcional por nome ou codigo de produto."},
                },
                "required": ["tipo_relatorio"],
                "additionalProperties": False,
            },
        },
    },
]

funcoes_disponiveis = {
    "consultar_estoque": consultar_estoque,
    "movimentar_estoque": movimentar_estoque,
    "gerar_relatorio_estoque": gerar_relatorio_estoque,
}

instrucoes = (
    "Voce e um assistente de estoque de farmacia. "
    "Use consultar_estoque para perguntas sobre produtos, precos, saldos, estoque minimo, movimentacoes e resumo. "
    "Use movimentar_estoque somente quando o usuario solicitar explicitamente uma entrada ou saida de unidades. "
    "Use gerar_relatorio_estoque quando o usuario pedir para gerar ou exportar um relatorio. "
    "Para relatorios de movimentacoes por periodo, solicite as duas datas se nao estiverem informadas; nunca invente datas. "
    "Antes de registrar uma movimentacao, obtenha codigo do produto, tipo, quantidade e motivo. "
    "Se algum desses dados estiver ausente ou ambiguo, faca uma pergunta objetiva e nao chame a ferramenta. "
    "Nunca invente dados. Nunca registre uma saida sem validar o codigo e o saldo; a funcao faz essa validacao. "
    "Ao receber resultado com status sucesso, confirme o codigo, produto, tipo, quantidade e novo saldo. "
    "Ao receber status erro, explique o motivo sem afirmar que a movimentacao foi realizada. "
    "Ao gerar um relatorio, informe a quantidade de registros e o caminho do arquivo CSV retornado pela ferramenta. "
    "Use somente os resultados das ferramentas para informar dados do estoque. "
    "Nao diga que alterou dados se nenhuma movimentacao foi registrada. "
    "Para perguntas gerais que nao dependam do banco, responda diretamente."
)

historico = [{"role": "system", "content": instrucoes}]

print("=" * 60)
print("AGENTE DE ESTOQUE COM CONSULTAS, MOVIMENTACOES E RELATORIOS")
print("Digite 'sair' para encerrar.")
print("=" * 60)

while True:
    pergunta = input("\nVoce: ").strip()
    if pergunta.casefold() in ("sair", "exit"):
        print("Ate logo!")
        break
    if not pergunta:
        continue

    historico.append({"role": "user", "content": pergunta})
    concluiu = False

    for tentativa in range(6):
        try:
            resposta = cliente.chat.completions.create(
                model=modelo,
                messages=historico,
                tools=ferramentas,
                tool_choice="auto",
                temperature=0,
            )
        except Exception as erro:
            print(f"\nAgente: Erro ao consultar o modelo: {erro}")
            concluiu = True
            break

        mensagem = resposta.choices[0].message
        historico.append(mensagem.model_dump(exclude_none=True))

        if not mensagem.tool_calls:
            print(f"\nAgente: {mensagem.content or 'Nao consegui gerar uma resposta.'}")
            concluiu = True
            break

        for chamada in mensagem.tool_calls:
            nome_funcao = chamada.function.name
            try:
                argumentos = json.loads(chamada.function.arguments or "{}")
                funcao = funcoes_disponiveis.get(nome_funcao)
                if funcao is None:
                    resultado = json.dumps({"status": "erro", "mensagem": "Ferramenta nao permitida."}, ensure_ascii=False)
                else:
                    resultado = funcao(**argumentos)
            except Exception as erro:
                resultado = json.dumps({"status": "erro", "mensagem": str(erro)}, ensure_ascii=False)

            print(f"   [Agente usou a ferramenta: {nome_funcao}]")
            print(f"   [Resultado: {resultado}]")
            historico.append({"role": "tool", "tool_call_id": chamada.id, "content": str(resultado)})

    if not concluiu:
        print("\nAgente: Nao consegui concluir a solicitacao dentro do limite de tentativas.")

    if len(historico) > 25:
        historico = [historico[0]] + historico[-24:]
