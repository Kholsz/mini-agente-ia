from datetime import date, datetime, timedelta
from pathlib import Path
import json
import re

import pandas as pd
from sqlalchemy import text

from estoque_database import banco_tem_dados, engine, inicializar_banco

RAIZ = Path(__file__).resolve().parents[1]
PASTA_RELATORIOS = RAIZ / "relatorios"

CTE_SALDO = (
    "WITH saldo AS ("
    "SELECT produto_id, "
    "SUM(CASE WHEN tipo = 'entrada' THEN quantidade ELSE -quantidade END) AS estoque_atual "
    "FROM movimentacoes GROUP BY produto_id) "
)


def _validar_data(valor, campo):
    texto = str(valor or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", texto):
        raise ValueError(f"{campo.capitalize()} invalida. Use o formato AAAA-MM-DD.")
    try:
        return date.fromisoformat(texto)
    except ValueError as erro:
        raise ValueError(f"{campo.capitalize()} invalida. Use o formato AAAA-MM-DD.") from erro


def _consultar_dataframe(consulta, parametros=None):
    with engine.connect() as conexao:
        return pd.read_sql(text(consulta), conexao, params=parametros or {})


def _nome_arquivo(tipo_relatorio, data_inicio=None, data_fim=None):
    partes = [tipo_relatorio]
    if data_inicio:
        partes.append(data_inicio.replace("-", ""))
    if data_fim:
        partes.append(data_fim.replace("-", ""))
    partes.append(datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    nome = "_".join(re.sub(r"[^a-zA-Z0-9_-]", "", parte) for parte in partes)
    return PASTA_RELATORIOS / f"{nome}.csv"


def _proteger_csv(quadro):
    seguro = quadro.copy()
    for coluna in seguro.columns:
        if seguro[coluna].dtype == object or pd.api.types.is_string_dtype(seguro[coluna].dtype):
            seguro[coluna] = seguro[coluna].map(
                lambda valor: "'" + valor
                if isinstance(valor, str) and valor.lstrip().startswith(("=", "+", "-", "@", "\t", "\r"))
                else valor
            )
    return seguro


def _exportar_dataframe(quadro, tipo_relatorio, data_inicio=None, data_fim=None):
    PASTA_RELATORIOS.mkdir(parents=True, exist_ok=True)
    caminho = _nome_arquivo(tipo_relatorio, data_inicio, data_fim)
    _proteger_csv(quadro).to_csv(caminho, index=False, sep=";", decimal=",", encoding="utf-8-sig")
    return caminho


def _resultado(quadro, tipo_relatorio, data_inicio=None, data_fim=None):
    caminho = _exportar_dataframe(quadro, tipo_relatorio, data_inicio, data_fim)
    amostra = quadro.head(10).to_dict(orient="records")
    return {
        "status": "sucesso",
        "tipo_relatorio": tipo_relatorio,
        "total_registros": int(len(quadro)),
        "arquivo": str(caminho.relative_to(RAIZ)),
        "colunas": list(quadro.columns),
        "amostra": amostra,
    }


def gerar_relatorio(tipo_relatorio, data_inicio=None, data_fim=None, termo=""):
    inicializar_banco()
    if not banco_tem_dados():
        raise FileNotFoundError("Banco de dados de estoque nao encontrado ou sem produtos cadastrados.")

    tipo_relatorio = str(tipo_relatorio or "").strip().lower()
    termo = str(termo or "").strip()
    filtro = f"%{termo}%"

    if tipo_relatorio == "estoque_completo":
        consulta = (
            CTE_SALDO
            + "SELECT p.codigo AS codigo, p.nome AS produto, p.categoria AS categoria, "
            "p.fabricante AS fabricante, ROUND(p.preco, 2) AS preco_unitario, "
            "COALESCE(s.estoque_atual, 0) AS estoque_atual, p.estoque_minimo AS estoque_minimo, "
            "CASE WHEN COALESCE(s.estoque_atual, 0) <= p.estoque_minimo THEN 'REPOR' ELSE 'OK' END AS situacao, "
            "ROUND(COALESCE(s.estoque_atual, 0) * p.preco, 2) AS valor_em_estoque "
            "FROM produtos p LEFT JOIN saldo s ON s.produto_id = p.id "
            "WHERE p.ativo = 1 ORDER BY p.nome"
        )
        quadro = _consultar_dataframe(consulta)
        return _resultado(quadro, tipo_relatorio)

    if tipo_relatorio == "estoque_baixo":
        consulta = (
            CTE_SALDO
            + "SELECT p.codigo AS codigo, p.nome AS produto, p.categoria AS categoria, "
            "COALESCE(s.estoque_atual, 0) AS estoque_atual, p.estoque_minimo AS estoque_minimo, "
            "p.estoque_minimo - COALESCE(s.estoque_atual, 0) AS unidades_para_minimo "
            "FROM produtos p LEFT JOIN saldo s ON s.produto_id = p.id "
            "WHERE p.ativo = 1 AND COALESCE(s.estoque_atual, 0) <= p.estoque_minimo "
            "ORDER BY unidades_para_minimo DESC, p.nome"
        )
        quadro = _consultar_dataframe(consulta)
        return _resultado(quadro, tipo_relatorio)

    if tipo_relatorio == "historico_movimentacoes":
        parametros = {"termo": filtro if termo else "%"}
        condicao_termo = "AND (:termo = '%' OR LOWER(p.nome) LIKE LOWER(:termo) OR LOWER(p.codigo) LIKE LOWER(:termo)) "
        condicoes_data = ""
        inicio = None
        fim = None
        if data_inicio:
            inicio = _validar_data(data_inicio, "data_inicio")
            condicoes_data += "AND m.data_hora >= :data_inicio "
            parametros["data_inicio"] = inicio.isoformat()
        if data_fim:
            fim = _validar_data(data_fim, "data_fim")
            condicoes_data += "AND m.data_hora < :data_fim_exclusiva "
            parametros["data_fim_exclusiva"] = (fim + timedelta(days=1)).isoformat()
        if inicio and fim and inicio > fim:
            raise ValueError("A data inicial nao pode ser posterior a data final.")
        consulta = (
            "SELECT m.id AS movimentacao_id, p.codigo AS codigo, p.nome AS produto, "
            "m.tipo AS tipo, m.quantidade AS quantidade, m.motivo AS motivo, "
            "m.data_hora AS data_hora FROM movimentacoes m "
            "JOIN produtos p ON p.id = m.produto_id "
            "WHERE 1 = 1 " + condicao_termo + condicoes_data
            + "ORDER BY m.data_hora DESC, m.id DESC"
        )
        quadro = _consultar_dataframe(consulta, parametros)
        return _resultado(quadro, tipo_relatorio, inicio.isoformat() if inicio else None, fim.isoformat() if fim else None)

    if tipo_relatorio == "movimentacoes_periodo":
        inicio = _validar_data(data_inicio, "data_inicio")
        fim = _validar_data(data_fim, "data_fim")
        if inicio > fim:
            raise ValueError("A data inicial nao pode ser posterior a data final.")
        consulta = (
            "SELECT m.id AS movimentacao_id, p.codigo AS codigo, p.nome AS produto, "
            "m.tipo AS tipo, m.quantidade AS quantidade, m.motivo AS motivo, "
            "m.data_hora AS data_hora FROM movimentacoes m "
            "JOIN produtos p ON p.id = m.produto_id "
            "WHERE m.data_hora >= :data_inicio AND m.data_hora < :data_fim_exclusiva "
            "ORDER BY m.data_hora DESC, m.id DESC"
        )
        parametros = {
            "data_inicio": inicio.isoformat(),
            "data_fim_exclusiva": (fim + timedelta(days=1)).isoformat(),
        }
        quadro = _consultar_dataframe(consulta, parametros)
        return _resultado(quadro, tipo_relatorio, inicio.isoformat(), fim.isoformat())

    if tipo_relatorio == "resumo_estoque":
        consulta = (
            CTE_SALDO
            + "SELECT COUNT(p.id) AS total_produtos, "
            "COALESCE(SUM(COALESCE(s.estoque_atual, 0)), 0) AS unidades_em_estoque, "
            "ROUND(COALESCE(SUM(COALESCE(s.estoque_atual, 0) * p.preco), 0), 2) AS valor_estimado_estoque, "
            "SUM(CASE WHEN COALESCE(s.estoque_atual, 0) <= p.estoque_minimo THEN 1 ELSE 0 END) AS produtos_no_minimo_ou_abaixo "
            "FROM produtos p LEFT JOIN saldo s ON s.produto_id = p.id WHERE p.ativo = 1"
        )
        quadro = _consultar_dataframe(consulta)
        return _resultado(quadro, tipo_relatorio)

    raise ValueError(
        "Tipo de relatorio invalido. Use estoque_completo, estoque_baixo, historico_movimentacoes, movimentacoes_periodo ou resumo_estoque."
    )


def gerar_relatorio_json(tipo_relatorio, data_inicio=None, data_fim=None, termo=""):
    try:
        resultado = gerar_relatorio(tipo_relatorio, data_inicio, data_fim, termo)
        return json.dumps(resultado, ensure_ascii=False, default=str)
    except Exception as erro:
        return json.dumps({"status": "erro", "mensagem": str(erro)}, ensure_ascii=False)
