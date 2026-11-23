import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts"))

from estoque_database import banco_tem_dados, executar_consulta, inicializar_banco

inicializar_banco()

if not banco_tem_dados():
    raise SystemExit("Execute primeiro: python scripts\\criar_banco_estoque.py")

opcoes = {
    "1": ("listar_produtos", "Produtos cadastrados"),
    "2": ("consultar_produto", "Pesquisar produto"),
    "3": ("consultar_estoque_baixo", "Produtos com estoque baixo"),
    "4": ("historico_movimentacoes", "Historico de movimentacoes"),
    "5": ("resumo_estoque", "Resumo do estoque"),
}

print("=" * 60)
print("CONSULTAS SQL — ESTOQUE DA FARMACIA")
print("=" * 60)

while True:
    print("\n1. Listar produtos")
    print("2. Pesquisar produto")
    print("3. Ver produtos com estoque baixo")
    print("4. Consultar movimentacoes")
    print("5. Ver resumo do estoque")
    print("0. Sair")
    opcao = input("\nEscolha: ").strip()

    if opcao == "0":
        print("Ate logo!")
        break

    if opcao not in opcoes:
        print("Opcao invalida.")
        continue

    operacao, titulo = opcoes[opcao]
    termo = ""
    if operacao in ("consultar_produto", "historico_movimentacoes"):
        termo = input("Digite o nome ou codigo do produto: ").strip()

    quadro = executar_consulta(operacao, termo, 20)
    print(f"\n{titulo}")
    print("-" * 60)
    if quadro.empty:
        print("Nenhum registro encontrado.")
    else:
        print(quadro.to_string(index=False))
