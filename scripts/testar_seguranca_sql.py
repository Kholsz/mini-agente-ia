import ast
import sqlite3
import tempfile
from pathlib import Path

from sqlalchemy import text

from estoque_database import CAMINHO_BANCO, engine, executar_consulta

RAIZ = Path(__file__).resolve().parents[1]
CAMINHO_AGENTE = RAIZ / "aulas" / "projeto_final_faq_rag" / "05_agente_consulta_estoque_sql_seguro.py"

resultados = []


def registrar(nome, aprovado, detalhe=""):
    resultados.append((nome, bool(aprovado), detalhe))
    estado = "APROVADO" if aprovado else "FALHOU"
    sufixo = f" — {detalhe}" if detalhe else ""
    print(f"[{estado}] {nome}{sufixo}")


def operacao_bloqueada(conexao, comando, parametros=()):
    try:
        conexao.execute(comando, parametros)
        conexao.commit()
        return False
    except sqlite3.DatabaseError:
        conexao.rollback()
        return True


def obter_chaves_dicionario(caminho, nome_variavel):
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if isinstance(no, ast.Assign):
            for alvo in no.targets:
                if isinstance(alvo, ast.Name) and alvo.id == nome_variavel:
                    if isinstance(no.value, ast.Dict):
                        try:
                            return {ast.literal_eval(chave) for chave in no.value.keys}
                        except Exception:
                            return None
    return None


def executar():
    print("=" * 64)
    print("TESTES DE SEGURANCA E INTEGRIDADE SQL")
    print("Nenhuma alteracao sera feita no banco original.")
    print("=" * 64)

    if not CAMINHO_BANCO.exists():
        raise SystemExit(f"Banco nao encontrado: {CAMINHO_BANCO}")

    if not CAMINHO_AGENTE.exists():
        registrar("Arquivo do agente seguro encontrado", False, str(CAMINHO_AGENTE))
    else:
        permitidas = obter_chaves_dicionario(CAMINHO_AGENTE, "funcoes_disponiveis")
        esperadas = {
            "consultar_estoque",
            "movimentar_estoque",
            "gerar_relatorio_estoque",
            "verificar_integridade_banco",
        }
        registrar(
            "Agente usa lista fechada de ferramentas",
            permitidas == esperadas,
            ", ".join(sorted(permitidas or [])),
        )
        texto_agente = CAMINHO_AGENTE.read_text(encoding="utf-8")
        registrar(
            "Ferramentas desconhecidas sao rejeitadas",
            "funcoes_disponiveis.get(nome_funcao)" in texto_agente and "Ferramenta nao permitida." in texto_agente,
        )

    with engine.connect() as conexao:
        foreign_keys = conexao.execute(text("PRAGMA foreign_keys")).scalar_one()
        quantidade_antes = conexao.execute(text("SELECT COUNT(*) FROM produtos")).scalar_one()
        movimentos_antes = conexao.execute(text("SELECT COUNT(*) FROM movimentacoes")).scalar_one()

    registrar("Chaves estrangeiras ativadas na conexao SQLAlchemy", foreign_keys == 1, f"PRAGMA foreign_keys={foreign_keys}")

    try:
        executar_consulta("listar_produtos; DROP TABLE produtos;--")
        lista_bloqueada = False
    except ValueError:
        lista_bloqueada = True
    registrar("Operacao SQL fora da lista permitida e rejeitada", lista_bloqueada)

    try:
        resultado_injecao = executar_consulta("consultar_produto", "MED001' OR '1'='1", 50)
        injecao_bloqueada = len(resultado_injecao.index) == 0
    except Exception:
        injecao_bloqueada = True
    registrar("Texto semelhante a SQL injection tratado como dado", injecao_bloqueada)

    limites_bloqueados = True
    for limite in (0, 51, True, "1; DROP TABLE produtos"):
        try:
            executar_consulta("listar_produtos", limite=limite)
            limites_bloqueados = False
            break
        except ValueError:
            pass
    registrar("Limites invalidos de consulta rejeitados", limites_bloqueados)

    with engine.connect() as conexao:
        quantidade_depois = conexao.execute(text("SELECT COUNT(*) FROM produtos")).scalar_one()
        movimentos_depois = conexao.execute(text("SELECT COUNT(*) FROM movimentacoes")).scalar_one()
        tabela_produtos_existe = conexao.execute(
            text("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='produtos'")
        ).scalar_one() == 1

    registrar(
        "Consultas de teste nao alteraram os dados originais",
        quantidade_antes == quantidade_depois and movimentos_antes == movimentos_depois and tabela_produtos_existe,
        f"produtos={quantidade_depois}, movimentacoes={movimentos_depois}",
    )

    with tempfile.TemporaryDirectory(prefix="teste_seguranca_sql_") as pasta_temporaria:
        copia_banco = Path(pasta_temporaria) / "estoque_teste.db"
        origem = sqlite3.connect(f"file:{CAMINHO_BANCO.as_posix()}?mode=ro", uri=True)
        destino = sqlite3.connect(copia_banco)
        origem.backup(destino)
        origem.close()
        destino.execute("PRAGMA foreign_keys = ON")

        linha = destino.execute(
            "SELECT id, produto_id FROM movimentacoes ORDER BY id LIMIT 1"
        ).fetchone()
        if linha:
            id_movimentacao, produto_id = linha
            update_bloqueado = operacao_bloqueada(
                destino,
                "UPDATE movimentacoes SET motivo = 'alteracao indevida' WHERE id = ?",
                (id_movimentacao,),
            )
            delete_bloqueado = operacao_bloqueada(
                destino,
                "DELETE FROM movimentacoes WHERE id = ?",
                (id_movimentacao,),
            )
        else:
            update_bloqueado = False
            delete_bloqueado = False
            produto_id = None

        registrar("Edicao direta do historico bloqueada por trigger", update_bloqueado)
        registrar("Exclusao direta do historico bloqueada por trigger", delete_bloqueado)

        if produto_id is not None:
            saldo = destino.execute(
                "SELECT COALESCE(SUM(CASE WHEN tipo='entrada' THEN quantidade ELSE -quantidade END), 0) "
                "FROM movimentacoes WHERE produto_id = ?",
                (produto_id,),
            ).fetchone()[0]
            data_hora = "2099-01-01T00:00:00"
            saida_excessiva_bloqueada = operacao_bloqueada(
                destino,
                "INSERT INTO movimentacoes (produto_id, tipo, quantidade, motivo, data_hora) VALUES (?, 'saida', ?, 'teste excedente', ?)",
                (produto_id, saldo + 1, data_hora),
            )
            quantidade_zero_bloqueada = operacao_bloqueada(
                destino,
                "INSERT INTO movimentacoes (produto_id, tipo, quantidade, motivo, data_hora) VALUES (?, 'entrada', 0, 'teste invalido', ?)",
                (produto_id, data_hora),
            )
        else:
            saida_excessiva_bloqueada = False
            quantidade_zero_bloqueada = False

        registrar("Saida acima do saldo bloqueada pelo banco", saida_excessiva_bloqueada)
        registrar("Movimentacao com quantidade zero bloqueada", quantidade_zero_bloqueada)

        destino.execute("DROP TRIGGER IF EXISTS trg_movimentacao_produto_ativo")
        fk_bloqueada = operacao_bloqueada(
            destino,
            "INSERT INTO movimentacoes (produto_id, tipo, quantidade, motivo, data_hora) VALUES (999999, 'entrada', 1, 'teste fk', ?)",
            (data_hora,),
        )
        registrar("Chave estrangeira invalida bloqueada pelo SQLite", fk_bloqueada)

        destino.close()

    print("=" * 64)
    aprovados = sum(1 for _, aprovado, _ in resultados if aprovado)
    total = len(resultados)
    print(f"RESULTADO: {aprovados}/{total} testes aprovados")
    print("Banco original preservado.")
    print("=" * 64)

    if aprovados != total:
        raise SystemExit(1)


if __name__ == "__main__":
    executar()
