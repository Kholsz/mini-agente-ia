import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts"))

from estoque_database import banco_tem_dados, executar_consulta, inicializar_banco, registrar_movimentacao

inicializar_banco()
if not banco_tem_dados():
    raise SystemExit("Execute primeiro: python scripts\\criar_banco_estoque.py")

print("=" * 60)
print("MOVIMENTACOES DE ESTOQUE")
print("=" * 60)

while True:
    print("\n1. Registrar entrada")
    print("2. Registrar saida")
    print("3. Consultar estoque do produto")
    print("4. Consultar historico de movimentacoes")
    print("0. Sair")
    opcao = input("\nEscolha: ").strip()

    if opcao == "0":
        print("Ate logo!")
        break

    if opcao not in ("1", "2", "3", "4"):
        print("Opcao invalida.")
        continue

    if opcao in ("1", "2"):
        codigo = input("Codigo do produto: ").strip()
        quantidade_texto = input("Quantidade: ").strip()
        motivo = input("Motivo da movimentacao: ").strip()
        try:
            quantidade = int(quantidade_texto)
            tipo = "entrada" if opcao == "1" else "saida"
            print("\nCONFIRMACAO DE MOVIMENTACAO")
            print(f"Codigo: {codigo.upper()}")
            print(f"Tipo: {tipo}")
            print(f"Quantidade: {quantidade}")
            print(f"Motivo: {motivo}")
            confirmacao = input("Confirma esta movimentacao? Digite S para confirmar: ").strip().casefold()
            if confirmacao not in ("s", "sim"):
                print("Movimentacao cancelada. Nenhum dado foi alterado.")
                continue
            resultado = registrar_movimentacao(
                codigo=codigo,
                tipo=tipo,
                quantidade=quantidade,
                motivo=motivo,
            )
            print("\nMovimentacao registrada com sucesso.")
            print(f"Produto: {resultado['produto']} ({resultado['codigo']})")
            print(f"Tipo: {resultado['tipo']}")
            print(f"Quantidade: {resultado['quantidade']}")
            print(f"Estoque anterior: {resultado['estoque_anterior']}")
            print(f"Estoque atual: {resultado['estoque_atual']}")
            print(f"Movimentacao: {resultado['movimentacao_id']}")
        except (ValueError, TypeError) as erro:
            print(f"\nNao foi possivel registrar: {erro}")
        continue

    if opcao == "3":
        termo = input("Nome ou codigo do produto: ").strip()
        quadro = executar_consulta("consultar_produto", termo, 20)
    else:
        termo = input("Nome ou codigo do produto (Enter para todos): ").strip()
        quadro = executar_consulta("historico_movimentacoes", termo, 50)

    if quadro.empty:
        print("Nenhum registro encontrado.")
    else:
        print(quadro.to_string(index=False))
