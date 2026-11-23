import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts"))

from relatorios_estoque import gerar_relatorio

print("=" * 60)
print("RELATORIOS DE ESTOQUE COM PANDAS")
print("=" * 60)

opcoes = {
    "1": ("estoque_completo", "Estoque completo"),
    "2": ("estoque_baixo", "Produtos no minimo ou abaixo"),
    "3": ("historico_movimentacoes", "Historico de movimentacoes"),
    "4": ("movimentacoes_periodo", "Movimentacoes por periodo"),
    "5": ("resumo_estoque", "Resumo do estoque"),
}

while True:
    print("\n1. Relatorio completo de estoque")
    print("2. Produtos no minimo ou abaixo")
    print("3. Historico de movimentacoes")
    print("4. Movimentacoes por periodo")
    print("5. Resumo do estoque")
    print("0. Sair")
    opcao = input("\nEscolha: ").strip()

    if opcao == "0":
        print("Ate logo!")
        break

    if opcao not in opcoes:
        print("Opcao invalida.")
        continue

    tipo, titulo = opcoes[opcao]
    data_inicio = None
    data_fim = None
    termo = ""

    if tipo == "historico_movimentacoes":
        data_inicio = input("Data inicial (AAAA-MM-DD, Enter para ignorar): ").strip() or None
        data_fim = input("Data final (AAAA-MM-DD, Enter para ignorar): ").strip() or None
        termo = input("Produto ou codigo (Enter para todos): ").strip()

    if tipo == "movimentacoes_periodo":
        data_inicio = input("Data inicial (AAAA-MM-DD): ").strip()
        data_fim = input("Data final (AAAA-MM-DD): ").strip()

    try:
        resultado = gerar_relatorio(tipo, data_inicio, data_fim, termo)
        print(f"\nRelatorio: {titulo}")
        print(f"Registros: {resultado['total_registros']}")
        print(f"Arquivo: {resultado['arquivo']}")
        if resultado["amostra"]:
            import pandas as pd
            quadro = pd.DataFrame(resultado["amostra"])
            print("\n" + quadro.to_string(index=False))
        else:
            print("\nNenhum registro encontrado.")
    except Exception as erro:
        print(f"\nNao foi possivel gerar o relatorio: {erro}")
