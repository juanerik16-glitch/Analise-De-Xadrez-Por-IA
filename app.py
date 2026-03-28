import streamlit as st
import chess
import chess.engine
import chess.pgn
import chess.svg
import io
import pandas as pd
import base64
import os  # Adicionado para corrigir o erro de 'os is not defined'
import shutil
from groq import Groq

# --- CONFIGURAÇÕES DE API E ENGINE ---
if "GROQ_API_KEY" in st.secrets:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
else:
    GROQ_API_KEY = "SUA_CHAVE_AQUI" # Ou configure no .streamlit/secrets.toml

client = Groq(api_key=GROQ_API_KEY)

def _resolve_stockfish_path():
    """Busca o executável do Stockfish no sistema."""
    # Tenta encontrar o 'stockfish' instalado globalmente no Linux (PATH)
    which = shutil.which("stockfish")
    if which:
        return which # Removido o caractere estranho aqui
        
    # Fallback para caminhos comuns se o 'which' falhar
    candidates = ["/usr/games/stockfish", "/usr/bin/stockfish"]
    for p in candidates:
        if os.path.exists(p): # Agora o 'os' está importado corretamente
            return p
            
    return None

STOCKFISH_PATH = _resolve_stockfish_path()

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Revisão da Partida - IA", layout="wide")

# CSS para o tema escuro e o Coach Card
st.markdown("""
    <style>
    .main { background-color: #262421; color: #ffffff; }
    [data-testid="stSidebar"] { background-color: #21201d; }
    .stDataFrame { background-color: #312e2b; border-radius: 5px; }
    .analysis-card {
        background-color: #312e2b; 
        padding: 20px; 
        border-radius: 10px; 
        border-left: 5px solid #81b64c;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE LÓGICA ---

def render_svg(svg):
    """Renderiza o tabuleiro SVG na tela."""
    b64 = base64.b64encode(svg.encode('utf-8')).decode("utf-8")
    html = f'<div style="display: flex; justify-content: center;"><img src="data:image/svg+xml;base64,{b64}" style="width:100%; max-width:550px; border-radius: 3px;"/></div>'
    st.write(html, unsafe_allow_html=True)

def get_ai_explanation(fen, move, best, cls):
    """Obtém análise sarcástica/curta da IA Groq."""
    prompt = f"GM de Xadrez Brasileiro: FEN {fen}, lance feito {move}, o melhor era {best}. Classificação: {cls}. Explique de forma breve, didática e técnica em PT-BR."
    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=150
        )
        return completion.choices[0].message.content.strip()
    except:
        return "A IA está recalculando as variantes de empate..."

def analyze_full_game(pgn_text):
    """Processa todo o PGN com Stockfish e gera tabuleiros com setas."""
    if not STOCKFISH_PATH:
        st.error("Stockfish não encontrado no sistema!")
        return None, None, None

    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if not game:
        st.error("PGN inválido!")
        engine.quit()
        return None, None, None
        
    board = game.board()
    
    # SVG inicial simples
    svg_inicio = chess.svg.board(board=board, size=600)
    history = [{"fen": board.fen(), "move": "Início", "class": "Teoria", "player": "Sistema", "acc": 100, "eval": 0.0, "svg": svg_inicio}]
    stats = {"Brancas": [], "Pretas": []}
    evals = [0.0]

    # Armazena lances para cálculo de mate
    mate_score = 10000

    while not board.is_game_over() and game.next():
        node = game.next()
        move = node.move
        
        # Análise antes do lance
        # Aumentamos ligeiramente a profundidade para melhores sugestões de lances (depth=14)
        info = engine.analyse(board, chess.engine.Limit(depth=14))
        score_before = info["score"].white().score(mate_score=mate_score)
        # Obtém o melhor lance sugerido (engine_best_move)
        engine_best_move = info["pv"][0] if "pv" in info else None
        best_move_san = board.san(engine_best_move) if engine_best_move else "N/A"
        
        player = "Brancas" if board.turn == chess.WHITE else "Pretas"
        san_move = board.san(move)
        fen_prev = board.fen()
        board_before = board.copy() # Cópia para gerar o SVG correto
        
        board.push(move)
        
        # Análise depois do lance
        post_info = engine.analyse(board, chess.engine.Limit(depth=14))
        score_after = post_info["score"].white().score(mate_score=mate_score)
        
        eval_decimal = score_after / 100.0
        # Normaliza o mate no gráfico para +/- 12
        if abs(score_after) >= mate_score:
            eval_clamped = 12 if score_after > 0 else -12
        else:
            eval_clamped = max(min(eval_decimal, 10), -10)
        evals.append(eval_clamped)

        loss = abs(score_before - score_after)
        acc_score = max(0, 100 - (loss / 1.8)) # Ajuste leve na precisão
        stats[player].append(acc_score)

        if loss <= 15: cls = "Melhor"
        elif loss <= 50: cls = "Excelente"
        elif loss <= 150: cls = "Imprecisão"
        else: cls = "Blunder"

        # --- GERAÇÃO DO SVG COM SETAS ---
        arrows = []
        # 1. Seta Azul (Transparente) para o lance que FOI JOGADO
        # Usamos uma cor azul transparente para não atrapalhar a visão
        arrows.append(chess.svg.Arrow(move.from_square, move.to_square, color="#0000cccc"))
        
        # 2. Seta Verde (Transparente) para o MELHOR LANCE, se o usuário errou
        if move != engine_best_move and engine_best_move and cls in ["Imprecisão", "Blunder"]:
            arrows.append(chess.svg.Arrow(engine_best_move.from_square, engine_best_move.to_square, color="#00cc00aa"))

        # Renderizamos o tabuleiro *antes* do lance, mas mostrando as setas do que vai acontecer/deveria acontecer
        # 'lastmove=move' destaca a casa de origem e destino em amarelo
        svg = chess.svg.board(board=board_before, lastmove=move, arrows=arrows, size=600)

        history.append({
            "fen": board.fen(), "move": san_move, "class": cls, "best": best_move_san,
            "fen_prev": fen_prev, "player": player, "acc": acc_score, "svg": svg, "eval": eval_decimal
        })
        game = node
        
    engine.quit()
    return history, stats, evals

# --- INTERFACE PRINCIPAL ---

# Inicialização de estados
if "current_step" not in st.session_state:
    st.session_state.current_step = 0

with st.sidebar:
    st.title("♟️ Configurações")
    pgn_input = st.text_area("Cole seu PGN:", height=150, placeholder="1. d4 d5 2. c4...")
    
    col1, col2 = st.columns(2)
    iniciar = col1.button("🚀 Iniciar Revisão")
    limpar = col2.button("🗑️ Limpar")
    
    if limpar:
        if "history" in st.session_state:
            del st.session_state.history
            st.session_state.current_step = 0
            st.rerun()

    if iniciar and pgn_input:
        with st.spinner("O motor está analisando sua partida com profundidade total..."):
            h, s, ev = analyze_full_game(pgn_input)
            if h:
                st.session_state.history = h
                st.session_state.stats = s
                st.session_state.evals = ev
                st.session_state.current_step = len(h)-1 # Pula para o último lance

# Distribuição do Layout (Proporções estilo Lichess/Chess.com)
col_tabuleiro, col_revisao = st.columns([1.6, 1])

if "history" in st.session_state:
    hist = st.session_state.history
    step = st.session_state.current_step
    curr = hist[step]

    with col_tabuleiro:
        # Informações Básicas
        opp_name = "Oponente" if curr['player'] == "Brancas" else "Você"
        st.markdown(f"👤 **{opp_name}**")
        
        # Renderização do tabuleiro dinâmico
        render_svg(curr["svg"])
        
        my_name = "Você" if curr['player'] == "Brancas" else "Oponente"
        st.markdown(f"👤 **{my_name}**")
        
        # Controles de navegação (Botões Compactos)
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        if c1.button("⏮️", use_container_width=True): st.session_state.current_step = 0
        if c2.button("⬅️", use_container_width=True): 
            if st.session_state.current_step > 0: st.session_state.current_step -= 1
        if c3.button("➡️", use_container_width=True): 
            if st.session_state.current_step < len(hist)-1: st.session_state.current_step += 1
        if c4.button("⏭️", use_container_width=True): st.session_state.current_step = len(hist)-1

    with col_revisao:
        st.subheader("⭐ Revisão da Partida")
        
        # Balão de Análise (Coach Card)
        color_map = {"Melhor": "#81b64c", "Excelente": "#96bc4b", "Imprecisão": "#f0c15c", "Blunder": "#ca3431", "Teoria": "#a88865"}
        border_color = color_map.get(curr['class'], "#81b64c")
        
        st.markdown(f"""
            <div class="analysis-card" style="border-left: 5px solid {border_color};">
                <h4 style="margin:0; color: white;">{curr['move']}</h4>
                <p style="margin:5px 0; color: #abaaa8;">É um lance de <b>{curr['class']}</b></p>
                <p style="font-size: 1.2em;">Avaliação: <b>{curr['eval']:.2f}</b></p>
            </div>
            """, unsafe_allow_html=True)
        
        # Botão de IA com Chave Única para evitar bugs ao navegar
        if st.button("💡 Por que este lance?", key=f"ai_explain_{step}", use_container_width=True):
            if step > 0:
                with st.spinner("Consultando o Grande Mestre..."):
                    expl = get_ai_explanation(curr['fen_prev'], curr['move'], curr['best'], curr['class'])
                    st.info(expl)
            else:
                st.write("Esta é a posição inicial.")

        st.divider()

        # Tabela de Lances Clicável (Pandas Groupby para melhor visualização)
        df_raw = pd.DataFrame(hist[1:])[["move", "player", "class"]]
        df_view = df_raw.copy()
        df_view.index = range(1, len(df_view) + 1) # Começa no lance 1
        
        st.write("**Lista Completa de Lances:**")
        selection = st.dataframe(
            df_view, use_container_width=True, hide_index=False,
            on_select="rerun", selection_mode="single-row"
        )
        # Se clicar na tabela, pula para o lance correspondente (+1 devido ao "Início")
        if selection and len(selection.selection.rows) > 0:
            st.session_state.current_step = selection.selection.rows[0] + 1

        # Minigráfico de Vantagem (Evaluation Chart)
        st.write("**Gráfico de Vantagem (Brancas + / Pretas -):**")
        # Gráfico centralizado no zero
        eval_data = pd.DataFrame({"Vantagem": st.session_state.evals, "Zero": [0]*len(st.session_state.evals)})
        st.line_chart(eval_data, height=120, color=["#1f77b4", "#555555"])

else:
    with col_tabuleiro:
        st.info("Insira um PGN na barra lateral e clique em 'Iniciar Revisão' para carregar a partida.")
        render_svg(chess.svg.board(size=600))