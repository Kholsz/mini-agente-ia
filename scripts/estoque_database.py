from datetime import datetime, timedelta
from pathlib import Path
import json
import re

import pandas as pd
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError

RAIZ = Path(__file__).resolve().parents[1]
CAMINHO_BANCO = RAIZ / "dados" / "estoque_farmacia.db"
engine = create_engine(
    f"sqlite:///{CAMINHO_BANCO.as_posix()}",
    future=True,
    connect_args={"check_same_thread": False, "timeout": 30},
)


@event.listens_for(engine, "connect")
def configurar_sqlite(conexao_dbapi, registro):
    cursor = conexao_dbapi.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.execute("PRAGMA busy_timeout = 30000")
    cursor.close()


def inicializar_banco():
    CAMINHO_BANCO.parent.mkdir(parents=True, exist_ok=True)
    with engine.begin() as conexao:
        conexao.execute(
            text(
                "CREATE TABLE IF NOT EXISTS produtos ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "codigo TEXT NOT NULL UNIQUE CHECK (length(trim(codigo)) BETWEEN 2 AND 30),"
                "nome TEXT NOT NULL CHECK (length(trim(nome)) BETWEEN 2 AND 160),"
                "categoria TEXT NOT NULL CHECK (length(trim(categoria)) BETWEEN 2 AND 80),"
                "fabricante TEXT NOT NULL CHECK (length(trim(fabricante)) BETWEEN 2 AND 100),"
                "preco REAL NOT NULL CHECK (preco >= 0),"
                "estoque_minimo INTEGER NOT NULL DEFAULT 0 CHECK (estoque_minimo >= 0),"
                "ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1))"
                ")"
            )
        )
        conexao.execute(
            text(
                "CREATE TABLE IF NOT EXISTS movimentacoes ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "produto_id INTEGER NOT NULL,"
                "tipo TEXT NOT NULL CHECK (tipo IN ('entrada', 'saida')) ,"
                "quantidade INTEGER NOT NULL CHECK (quantidade > 0),"
                "motivo TEXT NOT NULL CHECK (length(trim(motivo)) BETWEEN 3 AND 200),"
                "data_hora TEXT NOT NULL,"
                "FOREIGN KEY (produto_id) REFERENCES produtos(id)"
                ")"
            )
        )
        conexao.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_movimentacoes_produto_data "
                "ON movimentacoes (produto_id, data_hora)"
            )
        )
        conexao.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_movimentacoes_data_id "
                "ON movimentacoes (data_hora, id)"
            )
        )
        conexao.execute(
            text(
                "CREATE TRIGGER IF NOT EXISTS trg_movimentacao_produto_ativo "
                "BEFORE INSERT ON movimentacoes "
                "FOR EACH ROW "
                "WHEN COALESCE((SELECT ativo FROM produtos WHERE id = NEW.produto_id), 0) <> 1 "
                "BEGIN SELECT RAISE(ABORT, 'Produto inexistente ou inativo'); END"
            )
        )
        conexao.execute(
            text(
                "CREATE TRIGGER IF NOT EXISTS trg_movimentacao_sem_estoque_negativo "
                "BEFORE INSERT ON movimentacoes "
                "FOR EACH ROW "
                "WHEN NEW.tipo = 'saida' AND NEW.quantidade > COALESCE(("
                "SELECT SUM(CASE WHEN tipo = 'entrada' THEN quantidade ELSE -quantidade END) "
                "FROM movimentacoes WHERE produto_id = NEW.produto_id), 0) "
                "BEGIN SELECT RAISE(ABORT, 'Estoque insuficiente'); END"
            )
        )
        conexao.execute(
            text(
                "CREATE TRIGGER IF NOT EXISTS trg_validar_movimentacao "
                "BEFORE INSERT ON movimentacoes "
                "FOR EACH ROW "
                "WHEN NEW.quantidade < 1 OR NEW.quantidade > 1000000 "
                "OR length(trim(NEW.motivo)) < 3 OR length(trim(NEW.motivo)) > 200 "
                "BEGIN SELECT RAISE(ABORT, 'Dados da movimentacao invalidos'); END"
            )
        )
        conexao.execute(
            text(
                "CREATE TRIGGER IF NOT EXISTS trg_movimentacoes_sem_edicao "
                "BEFORE UPDATE ON movimentacoes "
                "FOR EACH ROW BEGIN "
                "SELECT RAISE(ABORT, 'O historico de movimentacoes nao pode ser editado'); "
                "END"
            )
        )
        conexao.execute(
            text(
                "CREATE TRIGGER IF NOT EXISTS trg_movimentacoes_sem_exclusao "
                "BEFORE DELETE ON movimentacoes "
                "FOR EACH ROW BEGIN "
                "SELECT RAISE(ABORT, 'O historico de movimentacoes nao pode ser excluido'); "
                "END"
            )
        )


def popular_dados_exemplo():
    produtos = [
        {"codigo": "MED001", "nome": "Dipirona 500 mg - 20 comprimidos", "categoria": "Analgesicos", "fabricante": "Medley", "preco": 12.90, "estoque_minimo": 20},
        {"codigo": "MED002", "nome": "Paracetamol 750 mg - 20 comprimidos", "categoria": "Analgesicos", "fabricante": "EMS", "preco": 9.50, "estoque_minimo": 25},
        {"codigo": "MED003", "nome": "Loratadina 10 mg - 12 comprimidos", "categoria": "Antialergicos", "fabricante": "Neo Quimica", "preco": 8.90, "estoque_minimo": 15},
        {"codigo": "MED004", "nome": "Soro fisiologico 0,9% - 500 ml", "categoria": "Solucoes", "fabricante": "Farmax", "preco": 7.90, "estoque_minimo": 10},
        {"codigo": "MED005", "nome": "Vitamina C 1 g - 10 comprimidos efervescentes", "categoria": "Vitaminas", "fabricante": "Cimed", "preco": 15.90, "estoque_minimo": 12},
        {"codigo": "EQP001", "nome": "Termometro digital", "categoria": "Equipamentos", "fabricante": "G-Tech", "preco": 24.90, "estoque_minimo": 5},
    ]
    with engine.begin() as conexao:
        quantidade_produtos = conexao.execute(text("SELECT COUNT(*) FROM produtos")).scalar_one()
        if quantidade_produtos == 0:
            conexao.execute(
                text(
                    "INSERT INTO produtos "
                    "(codigo, nome, categoria, fabricante, preco, estoque_minimo) "
                    "VALUES (:codigo, :nome, :categoria, :fabricante, :preco, :estoque_minimo)"
                ),
                produtos,
            )
        quantidade_movimentacoes = conexao.execute(text("SELECT COUNT(*) FROM movimentacoes")).scalar_one()
        if quantidade_movimentacoes == 0:
            ids = {
                linha.codigo: linha.id
                for linha in conexao.execute(text("SELECT id, codigo FROM produtos")).all()
            }
            agora = datetime.now()
            registros = [
                ("MED001", "entrada", 40, "Estoque inicial", 0),
                ("MED001", "saida", 5, "Venda", 1),
                ("MED002", "entrada", 25, "Estoque inicial", 0),
                ("MED002", "saida", 8, "Venda", 1),
                ("MED003", "entrada", 10, "Estoque inicial", 0),
                ("MED004", "entrada", 30, "Estoque inicial", 0),
                ("MED004", "saida", 3, "Venda", 1),
                ("MED005", "entrada", 8, "Estoque inicial", 0),
                ("EQP001", "entrada", 6, "Estoque inicial", 0),
            ]
            movimentacoes = []
            for codigo, tipo, quantidade, motivo, dias_atras in registros:
                data_hora = (agora - timedelta(days=dias_atras)).isoformat(timespec="seconds")
                movimentacoes.append({"produto_id": ids[codigo], "tipo": tipo, "quantidade": quantidade, "motivo": motivo, "data_hora": data_hora})
            conexao.execute(
                text(
                    "INSERT INTO movimentacoes "
                    "(produto_id, tipo, quantidade, motivo, data_hora) "
                    "VALUES (:produto_id, :tipo, :quantidade, :motivo, :data_hora)"
                ),
                movimentacoes,
            )


def executar_consulta(operacao, termo="", limite=10):
    if not isinstance(operacao, str):
        raise ValueError("Operacao de consulta invalida.")
    if isinstance(limite, bool):
        raise ValueError("O limite deve ser um numero inteiro entre 1 e 50.")
    try:
        limite = int(limite)
    except (TypeError, ValueError):
        raise ValueError("O limite deve ser um numero inteiro entre 1 e 50.")
    if limite < 1 or limite > 50:
        raise ValueError("O limite deve estar entre 1 e 50.")
    if not isinstance(termo, str):
        raise ValueError("O termo de pesquisa deve ser texto.")
    termo = termo.strip()
    if len(termo) > 100:
        raise ValueError("O termo de pesquisa deve ter no maximo 100 caracteres.")
    termo_escapado = termo.replace("!", "!!").replace("%", "!%").replace("_", "!_")
    filtro = f"%{termo_escapado}%"
    consultas = {
        "listar_produtos": (
            "WITH saldo AS (SELECT produto_id, SUM(CASE WHEN tipo = 'entrada' THEN quantidade ELSE -quantidade END) AS estoque_atual FROM movimentacoes GROUP BY produto_id) "
            "SELECT p.codigo, p.nome, p.categoria, p.fabricante, p.preco, COALESCE(s.estoque_atual, 0) AS estoque_atual, p.estoque_minimo "
            "FROM produtos p LEFT JOIN saldo s ON s.produto_id = p.id WHERE p.ativo = 1 ORDER BY p.nome LIMIT :limite",
            {"limite": limite},
        ),
        "consultar_produto": (
            "WITH saldo AS (SELECT produto_id, SUM(CASE WHEN tipo = 'entrada' THEN quantidade ELSE -quantidade END) AS estoque_atual FROM movimentacoes GROUP BY produto_id) "
            "SELECT p.codigo, p.nome, p.categoria, p.fabricante, p.preco, COALESCE(s.estoque_atual, 0) AS estoque_atual, p.estoque_minimo "
            "FROM produtos p LEFT JOIN saldo s ON s.produto_id = p.id "
            "WHERE p.ativo = 1 AND (LOWER(p.nome) LIKE LOWER(:termo) ESCAPE '!' OR LOWER(p.codigo) LIKE LOWER(:termo) ESCAPE '!') ORDER BY p.nome LIMIT :limite",
            {"termo": filtro, "limite": limite},
        ),
        "consultar_estoque_baixo": (
            "WITH saldo AS (SELECT produto_id, SUM(CASE WHEN tipo = 'entrada' THEN quantidade ELSE -quantidade END) AS estoque_atual FROM movimentacoes GROUP BY produto_id) "
            "SELECT p.codigo, p.nome, p.categoria, COALESCE(s.estoque_atual, 0) AS estoque_atual, p.estoque_minimo "
            "FROM produtos p LEFT JOIN saldo s ON s.produto_id = p.id "
            "WHERE p.ativo = 1 AND COALESCE(s.estoque_atual, 0) <= p.estoque_minimo "
            "ORDER BY (p.estoque_minimo - COALESCE(s.estoque_atual, 0)) DESC LIMIT :limite",
            {"limite": limite},
        ),
        "historico_movimentacoes": (
            "SELECT m.id AS movimentacao_id, p.codigo, p.nome, m.tipo, m.quantidade, m.motivo, m.data_hora "
            "FROM movimentacoes m JOIN produtos p ON p.id = m.produto_id "
            "WHERE (:termo = '%%' OR LOWER(p.nome) LIKE LOWER(:termo) ESCAPE '!' OR LOWER(p.codigo) LIKE LOWER(:termo) ESCAPE '!') "
            "ORDER BY m.data_hora DESC, m.id DESC LIMIT :limite",
            {"termo": filtro if termo else "%%", "limite": limite},
        ),
        "resumo_estoque": (
            "WITH saldo AS (SELECT produto_id, SUM(CASE WHEN tipo = 'entrada' THEN quantidade ELSE -quantidade END) AS estoque_atual FROM movimentacoes GROUP BY produto_id) "
            "SELECT COUNT(p.id) AS total_produtos, COALESCE(SUM(COALESCE(s.estoque_atual, 0)), 0) AS unidades_em_estoque, "
            "ROUND(COALESCE(SUM(COALESCE(s.estoque_atual, 0) * p.preco), 0), 2) AS valor_estimado_estoque, "
            "SUM(CASE WHEN COALESCE(s.estoque_atual, 0) <= p.estoque_minimo THEN 1 ELSE 0 END) AS produtos_abaixo_minimo "
            "FROM produtos p LEFT JOIN saldo s ON s.produto_id = p.id WHERE p.ativo = 1",
            {},
        ),
    }
    consulta_parametros = consultas.get(operacao)
    if consulta_parametros is None:
        raise ValueError("Operacao de consulta nao permitida.")
    consulta, parametros = consulta_parametros
    with engine.connect() as conexao:
        return pd.read_sql(text(consulta), conexao, params=parametros)


def consultar_banco(operacao, termo="", limite=10):
    quadro = executar_consulta(operacao, termo, limite)
    if quadro.empty:
        return "Nenhum registro encontrado para os criterios informados."
    return json.dumps(quadro.to_dict(orient="records"), ensure_ascii=False, default=str)


def obter_produto_por_codigo(codigo):
    if not isinstance(codigo, str):
        raise ValueError("O codigo do produto deve ser texto.")
    codigo = codigo.strip().upper()
    if not re.fullmatch(r"[A-Z0-9_-]{2,30}", codigo):
        raise ValueError("Codigo do produto invalido.")
    consulta = text(
        "SELECT p.id, p.codigo, p.nome, p.ativo, "
        "COALESCE((SELECT SUM(CASE WHEN m.tipo = 'entrada' THEN m.quantidade ELSE -m.quantidade END) "
        "FROM movimentacoes m WHERE m.produto_id = p.id), 0) AS estoque_atual "
        "FROM produtos p WHERE p.codigo = :codigo"
    )
    with engine.connect() as conexao:
        produto = conexao.execute(consulta, {"codigo": codigo}).mappings().first()
    if produto is None or produto["ativo"] != 1:
        raise ValueError(f"Produto ativo com codigo {codigo} nao encontrado.")
    return dict(produto)


def registrar_movimentacao(codigo, tipo, quantidade, motivo):
    if not isinstance(codigo, str):
        raise ValueError("O codigo do produto deve ser texto.")
    codigo = codigo.strip().upper()
    if not re.fullmatch(r"[A-Z0-9_-]{2,30}", codigo):
        raise ValueError("Codigo do produto invalido.")
    if not isinstance(tipo, str) or tipo.strip().lower() not in ("entrada", "saida"):
        raise ValueError("O tipo deve ser entrada ou saida.")
    tipo = tipo.strip().lower()
    if isinstance(quantidade, bool) or type(quantidade) is not int or quantidade < 1 or quantidade > 1000000:
        raise ValueError("A quantidade deve ser um numero inteiro entre 1 e 1.000.000.")
    if not isinstance(motivo, str):
        raise ValueError("O motivo deve ser texto.")
    motivo = " ".join(motivo.split())
    if len(motivo) < 3 or len(motivo) > 200:
        raise ValueError("O motivo deve ter entre 3 e 200 caracteres.")

    conexao = engine.connect()
    try:
        conexao.exec_driver_sql("BEGIN IMMEDIATE")
        produto = conexao.execute(
            text("SELECT id, codigo, nome FROM produtos WHERE codigo = :codigo AND ativo = 1"),
            {"codigo": codigo},
        ).mappings().first()
        if produto is None:
            raise ValueError(f"Produto ativo com codigo {codigo} nao encontrado.")

        estoque_anterior = conexao.execute(
            text(
                "SELECT COALESCE(SUM(CASE WHEN tipo = 'entrada' THEN quantidade ELSE -quantidade END), 0) "
                "FROM movimentacoes WHERE produto_id = :produto_id"
            ),
            {"produto_id": produto["id"]},
        ).scalar_one()

        if tipo == "saida" and quantidade > estoque_anterior:
            raise ValueError(
                f"Estoque insuficiente para {produto['nome']}. Disponivel: {estoque_anterior}; solicitado: {quantidade}."
            )

        data_hora = datetime.now().isoformat(timespec="microseconds")
        resultado = conexao.execute(
            text(
                "INSERT INTO movimentacoes (produto_id, tipo, quantidade, motivo, data_hora) "
                "VALUES (:produto_id, :tipo, :quantidade, :motivo, :data_hora)"
            ),
            {
                "produto_id": produto["id"],
                "tipo": tipo,
                "quantidade": quantidade,
                "motivo": motivo,
                "data_hora": data_hora,
            },
        )
        conexao.commit()
        estoque_atual = estoque_anterior + quantidade if tipo == "entrada" else estoque_anterior - quantidade
        return {
            "status": "sucesso",
            "movimentacao_id": resultado.lastrowid,
            "codigo": produto["codigo"],
            "produto": produto["nome"],
            "tipo": tipo,
            "quantidade": quantidade,
            "estoque_anterior": estoque_anterior,
            "estoque_atual": estoque_atual,
            "motivo": motivo,
            "data_hora": data_hora,
        }
    except IntegrityError as erro:
        conexao.rollback()
        mensagem = str(erro.orig)
        if "Estoque insuficiente" in mensagem:
            raise ValueError("Estoque insuficiente. A movimentacao foi bloqueada pelo banco de dados.") from erro
        if "Produto inexistente ou inativo" in mensagem:
            raise ValueError("O produto nao existe ou esta inativo.") from erro
        raise ValueError("O banco recusou a movimentacao por uma regra de integridade.") from erro
    except Exception:
        conexao.rollback()
        raise
    finally:
        conexao.close()


def auditar_integridade():
    with engine.connect() as conexao:
        integridade = conexao.execute(text("PRAGMA integrity_check")).scalar_one()
        chaves_estrangeiras = conexao.execute(text("PRAGMA foreign_key_check")).all()
        saldos_negativos = conexao.execute(
            text(
                "SELECT p.codigo, p.nome, "
                "SUM(CASE WHEN m.tipo = 'entrada' THEN m.quantidade ELSE -m.quantidade END) AS saldo "
                "FROM produtos p JOIN movimentacoes m ON m.produto_id = p.id "
                "GROUP BY p.id, p.codigo, p.nome "
                "HAVING saldo < 0"
            )
        ).mappings().all()
        total_produtos = conexao.execute(text("SELECT COUNT(*) FROM produtos WHERE ativo = 1")).scalar_one()
        total_movimentacoes = conexao.execute(text("SELECT COUNT(*) FROM movimentacoes")).scalar_one()
        triggers_existentes = {
            linha[0]
            for linha in conexao.execute(
                text("SELECT name FROM sqlite_master WHERE type = 'trigger'")
            ).all()
        }
    triggers_necessarios = {
        "trg_movimentacao_produto_ativo",
        "trg_movimentacao_sem_estoque_negativo",
        "trg_validar_movimentacao",
        "trg_movimentacoes_sem_edicao",
        "trg_movimentacoes_sem_exclusao",
    }
    triggers_ausentes = sorted(triggers_necessarios - triggers_existentes)
    return {
        "integridade_sqlite": integridade,
        "violacoes_chave_estrangeira": len(chaves_estrangeiras),
        "saldos_negativos": [dict(item) for item in saldos_negativos],
        "triggers_ausentes": triggers_ausentes,
        "produtos_ativos": total_produtos,
        "movimentacoes": total_movimentacoes,
        "status": "ok" if integridade == "ok" and not chaves_estrangeiras and not saldos_negativos and not triggers_ausentes else "erro",
    }


def banco_tem_dados():
    if not CAMINHO_BANCO.exists():
        return False
    try:
        with engine.connect() as conexao:
            quantidade = conexao.execute(text("SELECT COUNT(*) FROM produtos")).scalar_one()
        return quantidade > 0
    except Exception:
        return False
