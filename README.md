♟️ Analisador de Xadrez Pro (IA + Stockfish)

Uma ferramenta interativa de revisão de partidas inspirada no Chess.com, que utiliza o motor Stockfish para análise técnica e a IA Llama 3 (Groq Cloud) para explicações estratégicas em português brasileiro.

🚀 Funcionalidades

Análise Técnica: Avaliação de lances em tempo real com profundidade ajustável via Stockfish.

Interface Interativa: Tabuleiro visual com setas dinâmicas (Azul para o lance feito, Verde para a melhor sugestão).

Coach de IA: Explicações curtas, táticas e com personalidade para erros (Blunders) e acertos (Brilhantes).

Gráfico de Vantagem: Evolução da partida em um gráfico de linha (Evaluation Chart).

Navegação por Lances: Tabela de movimentos clicável e botões de navegação (Próximo/Anterior).

Precisão: Cálculo de precisão (0-100%) para cada jogador com base na perda de centipawns.

🛠️ Pré-requisitos
Antes de começar, você precisará ter instalado em sua máquina:

Python 3.10+.

Stockfish Engine:

No Linux: sudo apt install stockfish.

No Windows/Mac: Baixe o executável oficial e adicione-o ao PATH do sistema.

📦 Instalação
Clone o repositório:

Bash
git clone https://github.com/SEU_USUARIO/analisador-xadrez-ia.git
cd analisador-xadrez-ia
Crie e ative um ambiente virtual:

Bash
python -m venv .venv
source .venv/bin/activate  # No Windows: .venv\Scripts\activate
Instale as dependências:

Bash
pip install -r requirements.txt
Configure sua Chave API:
Crie o arquivo .streamlit/secrets.toml e adicione sua chave do Groq:

Ini, TOML
GROQ_API_KEY = "sua_chave_aqui"
🖥️ Como Usar
Para rodar a aplicação, execute o comando abaixo no terminal:

Bash
streamlit run app.py
📂 Estrutura do Projeto
app.py: Código principal da aplicação Streamlit.

requirements.txt: Lista de bibliotecas Python necessárias.

.streamlit/: Configurações e segredos (não incluídos no Git).

.gitignore: Proteção para não subir arquivos desnecessários ou sensíveis.