import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))

from estoque_database import auditar_integridade, inicializar_banco

inicializar_banco()
resultado = auditar_integridade()
print(json.dumps(resultado, ensure_ascii=False, indent=2))
if resultado["status"] != "ok":
    raise SystemExit(1)
print("Integridade do banco aprovada.")
