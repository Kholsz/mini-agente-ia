from estoque_database import CAMINHO_BANCO, inicializar_banco, popular_dados_exemplo

inicializar_banco()
popular_dados_exemplo()

print("Banco de dados de estoque preparado com sucesso.")
print(f"Arquivo: {CAMINHO_BANCO}")
