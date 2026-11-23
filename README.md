# Mini-Agente de IA

Esse projeto foi desenvolvido durante o mini curso **Construindo um Mini-Agente com IA**. A ideia foi aprender, na prática, como funciona a criação de um agente de inteligência artificial utilizando Python e ferramentas que permitem que ele interprete perguntas, consulte informações e execute determinadas tarefas.

Durante o desenvolvimento, fui trabalhando com diferentes conceitos e tecnologias até chegar à construção de um agente capaz de utilizar ferramentas para ajudar no atendimento de clientes.

## O que desenvolvi

Ao longo do projeto, trabalhei com:

- **Integração com IA:** conexão com um modelo de linguagem através da API da Groq.
- **System Prompts:** criação de instruções para definir o comportamento e as respostas do agente.
- **Memória:** implementação de uma memória que permite armazenar informações e recuperar o histórico de conversas.
- **Embeddings:** utilização de embeddings para transformar textos em representações que podem ser comparadas semanticamente.
- **ChromaDB:** armazenamento e pesquisa de informações em um banco vetorial.
- **RAG:** desenvolvimento de um chatbot que consulta documentos antes de formular suas respostas.
- **Function Calling:** integração de ferramentas para que o agente consiga realizar tarefas além de apenas conversar.

## Projeto final

Como parte do desenvolvimento, construí um agente de atendimento baseado nas informações de uma loja fictícia chamada TechStore Eletrônicos.

O agente consegue:

- Consultar informações no FAQ da loja.
- Responder dúvidas sobre produtos, pagamentos, garantias e outras regras.
- Calcular descontos para pagamentos via PIX.
- Registrar chamados quando o cliente precisa de atendimento humano.

Também desenvolvi uma extensão utilizando banco de dados SQLite, na qual o agente consegue consultar informações de estoque, registrar movimentações e gerar relatórios.

## Tecnologias utilizadas

- Python
- Groq API
- OpenAI SDK
- ChromaDB
- Sentence Transformers
- SQLite
- Pandas
- SQLAlchemy

## Como executar

Primeiro, é necessário ter o Python instalado e clonar este repositório:

```bash
git clone https://github.com/Kholsz/mini-agente-ia.git
cd mini-agente-ia
```

Depois, criar e ativar o ambiente virtual:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Instalar as dependências:

```bash
pip install -r requirements.txt
```

Criar o arquivo `.env` a partir do modelo disponibilizado:

```bash
copy .env.example .env
```

Depois, inserir a chave da API da Groq no arquivo `.env` e executar a verificação do ambiente:

```bash
python scripts/verificar_ambiente.py
```

Com o ambiente configurado, já é possível executar os exercícios e o agente.

## Objetivo

Meu principal objetivo com esse projeto foi entender como um agente de IA funciona na prática, desde uma simples conversa com um modelo de linguagem até a utilização de memória, consulta a documentos e execução de ferramentas.

Foi também uma oportunidade de colocar em prática os conhecimentos adquiridos durante o curso e aprofundar meus estudos em Python e inteligência artificial.