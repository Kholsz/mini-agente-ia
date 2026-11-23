MINI CURSO — CONSTRUINDO UM MINI-AGENTE COM IA

ESTRUTURA ORGANIZADA A PARTIR DOS MATERIAIS QUE VOCÊ ENVIOU

1. Extraia o conteúdo deste ZIP diretamente para a pasta CURSO MINI AGENTE.
   Escolha mesclar pastas, se o Windows perguntar. Este pacote NÃO contém .env nem .venv,
   portanto não substitui sua chave nem o ambiente virtual já criado.

2. Confirme que a pasta dados contém faq_projeto_exemplo.pdf.

3. Seu arquivo .env deve conter sua chave Groq e o modelo que já testamos:
   OPENAI_API_KEY=sua_chave_groq
   OPENAI_CHAT_MODEL=openai/gpt-oss-120b

4. Abra o CMD dentro da pasta do projeto, ative o ambiente virtual e rode:
   python scripts\verificar_ambiente.py

5. Primeira chamada:
   python aulas\aula_01_conversando_com_llm\01_primeira_chamada.py

ARQUIVOS INCLUÍDOS
- Aula 1: primeira chamada LLM e exemplos de System Prompt.
- Memória: somente a Parte I que você enviou. A Parte II não foi recebida.
- Embeddings/ChromaDB: criação do índice vetorial a partir do FAQ.
- RAG: chatbot que recupera trechos do FAQ antes de responder.
- Projeto final: agente com três ferramentas (buscar, calcular e abrir chamado), com correção técnica revisada.
- scripts/verificar_ambiente.py: verificação local de dependências e configuração.

IMPORTANTE SOBRE O MATERIAL RECEBIDO
O conteúdo enviado continha um trecho incompleto de tool calling isolado e a indicação
"FALTA A PARTE II" na memória. Não criei uma aula fictícia para preencher essas lacunas.
O agente com três ferramentas foi montado a partir do script final completo que você enviou.

GROQ
Os scripts que chamam o modelo usam a biblioteca openai com base_url da Groq,
porque o teste de conexão no seu computador já funcionou. A chave fica no .env local.
Nunca compartilhe esse arquivo. O pacote não inclui sua chave.

ORDEM SUGERIDA
1. python scripts\verificar_ambiente.py
2. python aulas\aula_01_conversando_com_llm\01_primeira_chamada.py
3. python aulas\aula_01_conversando_com_llm\02_system_prompt_personagens.py
4. python aulas\aula_01_conversando_com_llm\03_system_prompt_regras.py
5. python aulas\aula_03_memoria\03_memoria_parte1.py
6. python aulas\aula_04_embeddings_chromadb\04_criar_banco_vetorial.py
7. python aulas\aula_05_rag_pdf\05_chatbot_rag.py
8. python aulas\projeto_final_faq_rag\04_agente_multiplas_ferramentas.py

Antes de executar o RAG ou o agente final, rode primeiro o script 04 para criar o banco vetorial.


REVISAO TECNICA
Consulte REVISAO_TECNICA.md para limitações identificadas e a ordem recomendada de melhorias.
