import streamlit as st
import chess
import chess.engine
import chess.pgn
import chess.svg
import io
import shutil
from pathlib import Path
from groq import Groq
import base64

# --- CONFIGURAÇÕES ---
# Coloque sua chave API aqui ou use st.secrets para deploy
GROQ_API_KEY = st.secrets["GROQ_API_KEY"] if "GROQ_API_KEY" in st.secrets else "SUA_CHAVE_GROQ_AQUI"
EPD_FILE_PATH = "Aberturas.epd" # Nome do seu arquivo .epd (opcional para o visual funcionar)
DEPTH_LIMIT = 14 # Reduzido levemente para maior velocidade na web

# Título da Página
st.set_page_config(page_title="Analisador de Xadrez IA", layout="wide")

# Initialize Groq client
try:
    client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    st.error(f"Erro ao inicializar Groq Client. Verifique sua chave API. Erro: {e}")
    st.stop()

# --- FUNÇÕES DE APOIO ---

def _resolve_stockfish_path() -> str:
    """Busca o executável do Stockfish."""
    root = Path(__file__).resolve().parent
    candidates = [
        root / "stockfish" / "src" / "stockfish",
        root / "stockfish" / "stockfish-ubuntu-x86-64",
        root / "stockfish" / "stockfish-ubuntu-x86-64-sse41-popcnt",
        root / "stockfish" / "stockfish-ubuntu-x86-64-avx2",
        root / "stockfish.exe", # Candidato para Windows na raiz
    ]
    for p in candidates:
        if p.is_file():
            return str(p)
    which = shutil.which("stockfish")
    if which:
        return which
    return None # Retorna None em vez de erro para tratar no Streamlit

STOCKFISH_PATH = _resolve_stockfish_path()

def render_svg(svg):
    """Renderiza um SVG no Streamlit."""
    b64 = base64.b64encode(svg.encode('utf-8')).decode("utf-8")
    html = rf'<img src="data:image/svg+xml;base64,{b64}" style="max-width: 100%; height: auto;"/>'
    st.write(html, unsafe_allow_html=True)

def carregar_livro_epd(caminho_epd):
    """Lê arquivo EPD (simplificado para não travar se não existir)."""
    fens_livro = set()
    if not caminho_epd: return fens_livro
    try:
        with open(caminho_epd, "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 4:
                    fen_base = " ".join(parts[:4])
                    fens_livro.add(fen_base)
    except FileNotFoundError:
        pass # Silencioso na interface web
    return fens_livro

def calcular_material(board):
    """Calcula o valor total de material no tabuleiro."""
    values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
    white_score = sum(len(board.pieces(pt, chess.WHITE)) * val for pt, val in values.items())
    black_score = sum(len(board.pieces(pt, chess.BLACK)) * val for pt, val in values.items())
    return white_score, black_score

def get_ai_explanation(fen, move_played_san, best_move_san, classification):
    """Obtém explicação do Groq em Português."""
    if GROQ_API_KEY == "SUA_CHAVE_GROQ_AQUI":
        return "Configure a chave API do Groq para ver a análise da IA."

    prompt = f"""
    Você é um Grande Mestre de Xadrez brasileiro experiente e analítico.
    Posição (FEN): {fen}
    Lance feito: {move_played_san}
    Classificação do motor: {classification}
    Melhor lance sugerido pelo motor: {best_move_san}

    Explique brevemente em português brasileiro:
    1. A ideia tática ou estratégica por trás do 'Lance feito' e por que ele recebeu a classificação '{classification}'.
    2. Se aplicável, por que o 'Melhor lance' era preferível.
    Seja direto, use termos de xadrez, mostre personalidade (sarcástico se Blunder, empolgado se Brilhante).
    Limita-se a no máximo 3 parágrafos curtos.
    """
    try:
        completion = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"IA indisponível no momento. Erro: {e}"

def get_classification_color(classification):
    """Retorna cor para o markdown baseado na classificação."""
    colors = {
        "Brilhante": "#15803d", # Verde escuro
        "Melhor Lance (Best)": "#22c55e", # Verde
        "Excelente": "#a3e635", # Verde lima
        "Ótimo (Great)": "#facc15", # Amarelo
        "Livro (Book)": "#a8a29e", # Cinza
        "Imprecisão": "#fb923c", # Laranja
        "Erro": "#ef4444", # Vermelho
        "Blunder (Erro Grave)": "#b91c1c" # Vermelho escuro
    }
    return colors.get(classification, "#ffffff")

# --- INTERFACE STREAMLIT ---

st.title("♟️ Analisador de Partidas com Stockfish & Groq IA")
st.markdown("Insira o PGN da sua partida abaixo para uma análise detalhada lance a lance.")

# Sidebar para inputs
with st.sidebar:
    st.header("Configurações")
    pgn_input = st.text_area("Cole o PGN aqui:", height=200, placeholder="1. e4 e5 2. Nf3 ...")
    depth = st.slider("Profundidade da Análise (Stockfish)", min_value=10, max_value=20, value=DEPTH_LIMIT)
    analisar_btn = st.button("Analisar Partida")

# Verificação do Stockfish
if STOCKFISH_PATH is None:
    st.error("⚠️ Stockfish não encontrado. Verifique se o executável está no PATH ou na pasta 'stockfish/'. A análise não funcionará.")
    st.stop()

# Área Principal
if analisar_btn and pgn_input:
    with st.spinner("Analisando partida... Isso pode demorar alguns minutos dependendo do tamanho do jogo."):
        
        # Inicializar Engine
        try:
            engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
        except Exception as e:
            st.error(f"Erro ao iniciar Stockfish: {e}")
            st.stop()

        # Ler PGN
        pgn_io = io.StringIO(pgn_input)
        game = chess.pgn.read_game(pgn_io)
        
        if game is None:
            st.error("PGN inválido.")
            engine.quit()
            st.stop()

        board = game.board()
        fens_livro = carregar_livro_epd(EPD_FILE_PATH)
        
        # Cabeçalho da partida
        white = game.headers.get("White", "Brancas")
        black = game.headers.get("Black", "Pretas")
        date = game.headers.get("Date", "?")
        result = game.headers.get("Result", "*")
        
        st.subheader(f"Análise: {white} vs {black}")
        st.caption(f"Data: {date} | Resultado: {result} | Profundidade: {depth}")
        st.divider()

        moves_data = []
        
        # Loop de análise da partida
        node = game
        while not board.is_game_over() and node.next():
            prev_node = node
            node = node.next()
            move = node.move

            # 1. Analisar posição ANTES do lance
            # (Usamos o board no estado anterior para pegar a FEN correta para o prompt da IA)
            fen_before = board.fen()
            info = engine.analyse(board, chess.engine.Limit(depth=depth))
            engine_best_move = info["pv"][0] if "pv" in info else None
            best_move_san = board.san(engine_best_move) if engine_best_move else "N/A"
            score_before = info["score"].white().score(mate_score=10000)
            mat_white_before, mat_black_before = calcular_material(board)

            # 2. Verificar Livro
            fen_parts = fen_before.split()
            fen_clean = " ".join(fen_parts[:4])
            is_book = fen_clean in fens_livro

            # 3. Executar e obter infos do lance feito
            san_played = board.san(move)
            is_white_turn = board.turn == chess.WHITE
            player_name = white if is_white_turn else black
            color_label = "Brancas" if is_white_turn else "Pretas"
            turn_num = board.fullmove_number
            
            board.push(move)

            # 4. Analisar DEPOIS do lance
            post_info = engine.analyse(board, chess.engine.Limit(depth=depth))
            score_after = post_info["score"].white().score(mate_score=10000)
            mat_white_after, mat_black_after = calcular_material(board)

            # 5. Classificação
            # A perda é calculada do ponto de vista de quem jogou
            raw_loss = score_before - score_after
            # Se forem as pretas jogando, um score white menor é bom para elas, então invertemos a perda
            loss = raw_loss if is_white_turn else -raw_loss 
            
            is_best = (move == engine_best_move)

            # Detectar Sacrifício (Se o valor do material de quem jogou diminuiu)
            if is_white_turn: 
                sacrificio = mat_white_after < mat_white_before
            else:
                sacrificio = mat_black_after < mat_black_before

            classification = "Bom"
            if is_book: classification = "Livro (Book)"
            elif is_best:
                if sacrificio and loss < 30: classification = "Brilhante" # Ganho material ou perda mínima com sacrifício
                else: classification = "Melhor Lance (Best)"
            elif loss <= 15: classification = "Excelente"
            elif loss <= 40: classification = "Ótimo (Great)"
            elif loss <= 90: classification = "Bom"
            elif loss <= 180: classification = "Imprecisão"
            elif loss <= 350: classification = "Erro"
            else: classification = "Blunder (Erro Grave)"

            # Gerar SVG do tabuleiro ANTES do lance com seta para o lance feito
            # Se for blunder/erro, destaca a casa
            lastmove_arrow = chess.svg.Arrow(move.from_square, move.to_square, color="#0000cccc")
            bestmove_arrow = None
            if not is_best and not is_book and engine_best_move:
                 bestmove_arrow = chess.svg.Arrow(engine_best_move.from_square, engine_best_move.to_square, color="#00cc00aa")

            arrows = [lastmove_arrow]
            if bestmove_arrow and classification in ["Imprecisão", "Erro", "Blunder (Erro Grave)"]:
                arrows.append(bestmove_arrow)

            board_svg = chess.svg.board(
                prev_node.board(), # Mostra posição antes
                arrows=arrows,
                size=400,
                lastmove=move,
                colors={'square light': '#f0d9b5', 'square dark': '#b58863'}
            )

            # Obter explicação da IA para lances críticos
            ai_text = None
            if classification in ["Brilhante", "Erro", "Blunder (Erro Grave)", "Imprecisão"]:
                ai_text = get_ai_explanation(fen_before, san_played, best_move_san, classification)

            # Armazenar dados para exibição
            moves_data.append({
                "turn": f"{turn_num}. {'...' if not is_white_turn else ''}",
                "player": f"{player_name} ({color_label})",
                "move": san_played,
                "class": classification,
                "eval": score_after / 100.0,
                "svg": board_svg,
                "ai_text": ai_text,
                "best_san": best_move_san
            })

        engine.quit()

        # --- EXIBIÇÃO DOS RESULTADOS ---
        st.success("Análise concluída!")
        
        for i, m in enumerate(moves_data):
            # Cria um container expander para cada lance
            class_color = get_classification_color(m['class'])
            header_text = f"{m['turn']} {m['move']} - {m['player']} -> :{class_color}[{m['class']}] (Eval: {m['eval']:.2f})"
            
            with st.expander(header_text, expanded=(m['class'] in ["Brilhante", "Blunder (Erro Grave)"])):
                col1, col2 = st.columns([1, 1.5])
                
                with col1:
                    render_svg(m['svg'])
                    if m['class'] not in ["Livro (Book)", "Melhor Lance (Best)"]:
                        st.caption(f"Seta Azul: Lance Feito | Seta Verde: Melhor Lance Stockfish ({m['best_san']})")
                
                with col2:
                    st.markdown(f"**Classificação:** :{class_color}[{m['class']}]")
                    st.markdown(f"**Avaliação Stockfish:** `{m['eval']:.2f}`")
                    
                    if m['ai_text']:
                        st.markdown("---")
                        st.markdown("**💡 Análise do Grande Mestre IA (Groq):**")
                        st.write(m['ai_text'])
                    elif m['class'] == "Livro (Book)":
                        st.info("Lance teórico de abertura.")
                    else:
                         st.write("Lance sólido. Sem comentários adicionais da IA.")

elif analisar_btn and not pgn_input:
    st.warning("Por favor, cole um PGN válido.")