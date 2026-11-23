# Revisão técnica — Mini Curso: Construindo um Mini-Agente com IA

Data da revisão: 23/11/2026

## 1. Escopo e evidências

A revisão foi feita com base nos arquivos enviados pelo aluno (PRIMEIROS_PASSOS.pdf, requirements.txt, FAQ da TechStore e blocos de código colados), no pacote organizado e nas saídas de terminal compartilhadas durante os testes.

Os resultados abaixo classificados como **testados** foram observados nas saídas fornecidas pelo aluno. A revisão estática do código não equivale a um novo teste de integração com a chave Groq do aluno.

## 2. Funcionalidades já testadas

- Chamada ao modelo Groq usando o cliente `openai` e `base_url` compatível.
- Quatro respostas com diferentes System Prompts.
- Restrição de assunto por System Prompt e demonstração de prompt injection.
- Primeira chamada de apresentação do usuário (isso não implementa memória persistente).
- Extração do PDF e indexação de 15 chunks no ChromaDB.
- Consulta RAG para garantia, devolução e pergunta fora do FAQ.
- Ferramenta de consulta ao FAQ.
- Ferramenta de cálculo de desconto PIX (10% produto; 5% serviço).
- Ferramenta de abertura de chamado, com dois registros confirmados em `dados/chamados_suporte.csv`.

## 3. Achados e riscos

### 3.1. Arquivos de aulas ausentes

O `requirements.txt` menciona conteúdos das aulas 2, 6, 7 e 8. O material-fonte enviado não continha os respectivos scripts completos. Também foi recebida apenas a Parte I da aula de memória. Não se deve criar conteúdo e apresentá-lo como se fosse o código original do professor.

### 3.2. Embeddings não correspondem exatamente ao comentário de dependências

O código de criação do banco não configura explicitamente uma função de embeddings. Portanto, o ChromaDB usa seu embedding padrão local `all-MiniLM-L6-v2`. O `sentence-transformers` listado em `requirements.txt` não é chamado diretamente pelos scripts entregues.

A documentação do ChromaDB identifica `all-MiniLM-L6-v2` como sua função padrão. A listagem de modelos Sentence Transformers classifica `all-MiniLM-L6-v2` como inglês e oferece `paraphrase-multilingual-MiniLM-L12-v2` para uso multilíngue. Como o FAQ e as perguntas estão em português, vale testar um modelo multilíngue numa etapa posterior. A troca exige reprocessar todos os documentos com o mesmo modelo usado nas consultas; não se devem misturar vetores de modelos diferentes.

Referências:
- https://github.com/chroma-core/docs/blob/main/docs/embeddings.md
- https://github.com/huggingface/sentence-transformers/blob/main/docs/_static/html/models_en_sentence_embeddings.html
- https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

### 3.3. Divisão do PDF em chunks

O código divide o texto por quantidade fixa de caracteres (450, com sobreposição de 80). Isso pode cortar uma frase ou palavra no meio, como observado no trecho de teste que terminou em `Para co`. Para um FAQ, uma divisão por parágrafos/perguntas e respostas tende a preservar melhor o contexto.

### 3.4. Reindexação do ChromaDB

O uso de `upsert` atualiza ou insere IDs, mas não remove automaticamente chunks antigos que tenham deixado de existir se o PDF ficar menor ou mudar de estrutura. Numa rotina de reindexação, a coleção deve ser limpa/recriada ou os IDs obsoletos devem ser removidos.

### 3.5. Recuperação RAG sem limite de relevância

O chatbot busca sempre os dois resultados mais próximos, sem validar se a distância é suficientemente boa. Uma pesquisa fora do tema ainda pode retornar trechos pouco relacionados. O modelo pode então responder com contexto fraco. Recomenda-se avaliar `distances` e recusar a resposta quando os resultados não forem relevantes, depois de calibrar um limite com perguntas de teste.

### 3.6. Histórico de conversa

O chatbot mantém as mensagens na memória do processo e inclui contextos recuperados no histórico. Isso não é memória persistente entre execuções e pode acumular contexto antigo ou irrelevante durante conversas longas. Deve-se limitar o histórico e separar o contexto recuperado para cada pergunta.

### 3.7. System Prompt não valida fatos

No teste da secretaria acadêmica, o modelo inventou uma data de rematrícula embora nenhuma data tivesse sido fornecida. Um System Prompt ajuda a orientar, mas não é uma fonte de verdade nem uma trava de segurança. Para perguntas factuais, o sistema deve consultar uma fonte confiável e declarar quando não houver informação.

### 3.8. Abertura de chamados

O CSV registra os chamados localmente; isso não envia o chamado para uma empresa nem cria um protocolo num sistema remoto. O primeiro código também usava ID com precisão de um segundo, o que poderia colidir se dois chamados fossem criados no mesmo segundo. A versão revisada usa microssegundos e melhora a limpeza do assunto.

## 4. Correção incluída nesta revisão

O arquivo `aulas/projeto_final_faq_rag/04_agente_multiplas_ferramentas.py` foi atualizado para:

- corrigir a limpeza do assunto, removendo a frase de solicitação de abertura do chamado;
- aceitar nome informado junto com o pedido ou numa resposta seguinte;
- obrigar a seleção da ferramenta de suporte quando houver pedido explícito;
- não fazer uma segunda chamada à IA apenas para confirmar um chamado que já foi gravado;
- gerar identificadores com microssegundos;
- validar valor e tipo no cálculo de desconto;
- limitar o histórico em memória;
- verificar se o banco vetorial existe antes de iniciar.

A versão passou por compilação sintática e testes locais das funções de extração/limpeza do nome e assunto e do cálculo. Ainda precisa ser executada no computador do aluno com a conta Groq dele para validar integração ponta a ponta.

## 5. Ordem de melhorias recomendada

1. Substituir o script final pelo arquivo atualizado e testar a abertura de chamado com uma frase curta e outra com nome informado numa mensagem seguinte.
2. Melhorar a criação de chunks para preservar cada pergunta/resposta do FAQ.
3. Testar embeddings multilíngues e reindexar a coleção, caso a comparação de resultados mostre melhoria em português.
4. Adicionar limite de relevância ao RAG e conjunto de perguntas de avaliação.
5. Implementar memória de conversa persistente apenas quando o material/objetivo dessa aula estiver definido.
6. Completar as aulas de banco de dados quando os scripts originais do professor estiverem disponíveis.

## 6. Segurança e custo

- O `.env` deve permanecer fora do Git; o `.gitignore` do pacote já o exclui.
- Não compartilhar a chave Groq nem incluí-la em ZIPs ou capturas de tela.
- O CSV contém dados de clientes de teste e deve ser tratado como dado privado.
- O agente atual é demonstrativo/local. Não deve ser usado como sistema de atendimento real sem autenticação, controle de acesso, validação adicional, backup, prevenção de duplicidade e armazenamento adequado.


## Atualização de embeddings multilíngues

Os scripts de criação do índice, chatbot RAG e agente final agora utilizam `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` em CPU, com embeddings normalizados. A nova coleção é `faq_colecao_multilingual`, para preservar a coleção anterior e evitar misturar vetores de modelos diferentes.

Depois de substituir os arquivos, execute primeiro `python aulas\aula_04_embeddings_chromadb\04_criar_banco_vetorial.py`. A primeira execução baixa os arquivos do modelo e cria a nova coleção. Em seguida, execute o chatbot RAG ou o agente final. Não apague a coleção antiga durante a validação.
