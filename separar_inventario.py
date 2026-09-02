"""
Separador de Inventário - Dofus Venda Bot
==========================================
Tira um print do inventário, detecta os slots ocupados
e salva cada ícone de recurso individualmente em fotos/.

COMO USAR:
  1. Abra o Dofus com o inventário visível
  2. Execute: python separar_inventario.py
  3. Marque a região do inventário quando solicitado
  4. Nomeie cada item detectado
"""

import pyautogui as py
import json
import time
import os
import sys

import cv2
import numpy as np
from PIL import Image

# ==============================================================================
# CONFIGURAÇÃO
# ==============================================================================

PASTA_FOTOS    = 'fotos'
CONFIG_GRADE   = 'config_inventario.json'  # Salva layout da grade para reusar
LIMIAR_VAZIO   = 15   # Variância mínima de pixel para considerar slot ocupado
PREVIEW_ESCALA = 3    # Fator de zoom no preview de cada ícone

os.makedirs(PASTA_FOTOS, exist_ok=True)


# ==============================================================================
# UTILITÁRIOS DE TELA
# ==============================================================================

def aguardar_enter(mensagem=''):
    if mensagem:
        print(mensagem)
    input('  >> Pressione ENTER quando estiver pronto...')


def capturar_ponto(descricao):
    """Pede ao usuário que posicione o mouse e captura a posição."""
    print(f'  Posicione o mouse {descricao}')
    aguardar_enter()
    x, y = py.position()
    print(f'     Capturado: ({x}, {y})')
    return x, y


def capturar_screenshot_regiao(x, y, w, h):
    """Captura região da tela e retorna como array numpy (BGR)."""
    img_pil = py.screenshot(region=(x, y, w, h))
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


# ==============================================================================
# DEFINIÇÃO DA GRADE DO INVENTÁRIO
# ==============================================================================

COLUNAS_GRADE = 5
LINHAS_GRADE  = 8


def _calibrar_na_imagem(caminho_imagem):
    """
    Abre a imagem numa janela OpenCV e pede ao usuário que clique em:
      1. Canto superior esquerdo do slot 1
      2. Canto inferior direito do slot 1
    Retorna (x0, y0, largura_slot, altura_slot) em pixels da imagem.
    """
    img = cv2.imread(caminho_imagem)
    if img is None:
        print(f'[ERRO] Não foi possível abrir {caminho_imagem}')
        return None

    # Reduzir para caber na tela mantendo proporção (sem deformar)
    h, w = img.shape[:2]
    screen_w, screen_h = py.size()
    max_w = int(screen_w * 0.90)
    max_h = int(screen_h * 0.90)
    escala = min(1.0, max_w / w, max_h / h)
    ew = int(w * escala)
    eh = int(h * escala)
    exibir = cv2.resize(img, (ew, eh), interpolation=cv2.INTER_AREA) if escala < 1.0 else img.copy()

    cliques = []
    labels  = [
        'Clique no CANTO SUPERIOR ESQUERDO do 1o slot',
        'Clique no CANTO INFERIOR DIREITO do 1o slot',
    ]

    def on_mouse(event, mx, my, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            cliques.append((mx, my))

    win = 'Calibrar grade — clique nos 2 cantos do 1o slot  |  Q=cancelar'
    cv2.namedWindow(win, cv2.WINDOW_AUTOSIZE)  # sem redimensionamento livre
    cv2.setMouseCallback(win, on_mouse)

    instrucao_idx = 0
    while instrucao_idx < 2:
        frame = exibir.copy()
        # Desenhar cliques já feitos
        for i, (cx, cy) in enumerate(cliques):
            cv2.circle(frame, (cx, cy), 6, (0, 255, 0), -1)
            cv2.putText(frame, str(i + 1), (cx + 8, cy - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        # Instruçao atual
        cv2.putText(frame, labels[instrucao_idx], (10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 200, 255), 2)
        cv2.imshow(win, frame)
        key = cv2.waitKey(30) & 0xFF
        if key == ord('q'):
            cv2.destroyAllWindows()
            return None
        if len(cliques) > instrucao_idx:
            instrucao_idx += 1

    # Mostrar prévia da grade antes de confirmar
    cx1, cy1 = cliques[0]
    cx2, cy2 = cliques[1]
    lw_img = abs(cx2 - cx1)
    lh_img = abs(cy2 - cy1)
    x0_img = min(cx1, cx2)
    y0_img = min(cy1, cy2)

    preview = exibir.copy()
    for r in range(LINHAS_GRADE):
        for c in range(COLUNAS_GRADE):
            px = x0_img + c * lw_img
            py_ = y0_img + r * lh_img
            cv2.rectangle(preview, (px, py_), (px + lw_img, py_ + lh_img), (0, 255, 0), 1)
    cv2.putText(preview, f'Grade {COLUNAS_GRADE}x{LINHAS_GRADE} — pressione S p/ salvar, R p/ refazer',
                (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 200, 255), 2)
    cv2.imshow(win, preview)

    while True:
        key = cv2.waitKey(0) & 0xFF
        if key == ord('s'):
            break
        if key == ord('r'):
            cv2.destroyAllWindows()
            return _calibrar_na_imagem(caminho_imagem)  # recomeçar

    cv2.destroyAllWindows()

    # Converter coordenadas de exibição para coordenadas reais da imagem
    fator = 1.0 / escala
    return (
        int(round(x0_img * fator)),
        int(round(y0_img * fator)),
        int(round(lw_img * fator)),
        int(round(lh_img * fator)),
    )


def definir_grade_na_tela():
    """
    Calibração clássica: usuário posiciona o mouse na tela do jogo.
    Usado apenas no modo de captura automática.
    """
    print('\n' + '=' * 60)
    print('  MAPEAMENTO DA GRADE DO INVENTÁRIO  (5 colunas x 8 linhas)')
    print('=' * 60)
    print()
    print('  Você vai marcar apenas o PRIMEIRO slot:')
    print('  1. CANTO SUPERIOR ESQUERDO do slot 1')
    print('  2. CANTO INFERIOR DIREITO do slot 1')
    print()
    print('  Vá para a janela do Dofus. Você tem 3 segundos...')
    for i in range(3, 0, -1):
        print(f'    {i}...')
        time.sleep(1)

    x1_slot, y1_slot = capturar_ponto('no CANTO SUPERIOR ESQUERDO do 1º slot')
    x2_slot, y2_slot = capturar_ponto('no CANTO INFERIOR DIREITO do 1º slot')

    largura_slot = abs(x2_slot - x1_slot)
    altura_slot  = abs(y2_slot - y1_slot)
    print(f'     Tamanho do slot: {largura_slot}x{altura_slot} px')

    confirma = input('  Está correto? (s/n): ').strip().lower()
    if confirma != 's':
        return definir_grade_na_tela()

    grade = {
        'x_inicio':     x1_slot,
        'y_inicio':     y1_slot,
        'largura_slot': largura_slot,
        'altura_slot':  altura_slot,
        'colunas':      COLUNAS_GRADE,
        'linhas':       LINHAS_GRADE,
        '_origem':      'tela',
    }
    with open(CONFIG_GRADE, 'w', encoding='utf-8') as f:
        json.dump(grade, f, indent=4)
    print(f'  Grade salva em {CONFIG_GRADE}')
    return grade


def definir_grade_na_imagem(caminho_imagem):
    """
    Calibração a partir de um arquivo PNG: o usuário clica na imagem.
    As coordenadas ficam em pixels do arquivo, sem problema de DPI.
    """
    print('\n  Abrindo imagem para calibrar a grade...')
    print('  Clique nos 2 cantos do PRIMEIRO slot. Pressione S para salvar.')
    resultado = _calibrar_na_imagem(caminho_imagem)
    if resultado is None:
        print('[CANCELADO]')
        return None

    x0, y0, lw, lh = resultado
    grade = {
        'x_inicio':     x0,
        'y_inicio':     y0,
        'largura_slot': lw,
        'altura_slot':  lh,
        'colunas':      COLUNAS_GRADE,
        'linhas':       LINHAS_GRADE,
        '_origem':      'imagem',
    }
    with open(CONFIG_GRADE, 'w', encoding='utf-8') as f:
        json.dump(grade, f, indent=4)
    print(f'  Grade salva em {CONFIG_GRADE}  ({lw}x{lh} px por slot)')
    return grade


def carregar_grade(caminho_imagem=None):
    """Carrega grade existente ou solicita nova calibração."""
    if os.path.exists(CONFIG_GRADE):
        with open(CONFIG_GRADE, 'r', encoding='utf-8-sig') as f:
            grade = json.load(f)
        origem = grade.get('_origem', 'tela')
        print(f'[OK] Grade carregada: {grade["colunas"]}x{grade["linhas"]} slots (origem: {origem})')
        reuso = input('  Usar esta grade? (s/n): ').strip().lower()
        if reuso == 's':
            return grade
    # Nova calibração
    if caminho_imagem and os.path.exists(caminho_imagem):
        return definir_grade_na_imagem(caminho_imagem)
    return definir_grade_na_tela()


# ==============================================================================
# DETECÇÃO DE SLOTS OCUPADOS
# ==============================================================================

def slot_esta_ocupado(img_slot):
    """
    Retorna True se o slot contém um item.
    Slots vazios têm cor quase uniforme; slots com item têm variação de pixels.
    """
    cinza = cv2.cvtColor(img_slot, cv2.COLOR_BGR2GRAY)
    variancia = float(np.var(cinza))
    return variancia > LIMIAR_VAZIO


def extrair_slots(grade, caminho_imagem=None):
    """
    Extrai slots ocupados do inventário.
    Se caminho_imagem for fornecido, carrega a imagem desse arquivo
    (print manual da tela inteira). Caso contrário captura a tela automaticamente.
    Retorna lista de (linha, coluna, imagem_numpy) apenas para slots ocupados.
    """
    x0 = grade['x_inicio']
    y0 = grade['y_inicio']
    lw = grade['largura_slot']
    lh = grade['altura_slot']
    cols = grade['colunas']
    rows = grade['linhas']

    if caminho_imagem:
        print(f'\n  Carregando imagem: {caminho_imagem}')
        tela = cv2.imread(caminho_imagem)
        if tela is None:
            print(f'[ERRO] Não foi possível carregar {caminho_imagem}')
            return []

        # Coordenadas já são da imagem (calibração feita clicando na imagem)
        total_w = lw * cols
        total_h = lh * rows
        inventario = tela[y0:y0 + total_h, x0:x0 + total_w]

        if inventario.size == 0 or inventario.shape[0] == 0 or inventario.shape[1] == 0:
            img_h, img_w = tela.shape[:2]
            print(f'[ERRO] Recorte vazio. Refaça a calibração clicando na imagem.')
            print(f'       Imagem: {img_w}x{img_h}  |  Recorte: x={x0} y={y0} w={total_w} h={total_h}')
            return []

        print(f'  Área recortada: {inventario.shape[1]}x{inventario.shape[0]} px')
    else:
        total_w = lw * cols
        total_h = lh * rows
        print(f'\n  Capturando inventário ({total_w}x{total_h} px)...')
        inventario = capturar_screenshot_regiao(x0, y0, total_w, total_h)

    # Salvar print completo para referência
    caminho_print = os.path.join(PASTA_FOTOS, '_inventario_completo.png')
    cv2.imwrite(caminho_print, inventario)
    print(f'  Print da grade salvo em: {caminho_print}')

    slots_ocupados = []
    for row in range(rows):
        for col in range(cols):
            px = col * lw
            py_  = row * lh
            slot = inventario[py_:py_ + lh, px:px + lw]
            if slot_esta_ocupado(slot):
                slots_ocupados.append((row + 1, col + 1, slot))

    print(f'  Slots ocupados encontrados: {len(slots_ocupados)}')
    return slots_ocupados


LIMIAR_JA_CONHECIDO = 0.92  # score mínimo para considerar que o slot já existe em fotos/

PREFIXOS_SISTEMA = (
    'calibracao_', '_', 'campo_', 'btn_', 'vendaon', 'vendaoff',
)


def filtrar_slots_novos(slots, lw, lh):
    """
    Remove da lista os slots que já têm correspondência em fotos/.
    Retorna (slots_novos, slots_ja_conhecidos) onde cada item é (row, col, img).
    """
    # Carregar ícones existentes (apenas recursos, sem arquivos de sistema)
    icones = []
    for arq in os.listdir(PASTA_FOTOS):
        if not arq.endswith('.png'):
            continue
        if any(arq.startswith(p) for p in PREFIXOS_SISTEMA):
            continue
        caminho = os.path.join(PASTA_FOTOS, arq)
        tmpl = cv2.imread(caminho)
        if tmpl is None:
            continue
        if tmpl.shape[:2] != (lh, lw):
            tmpl = cv2.resize(tmpl, (lw, lh))
        icones.append((arq, tmpl))

    if not icones:
        return slots, []

    # Máscara que ignora zona de quantidade (30% inferior)
    mask = np.ones((lh, lw), dtype=np.uint8) * 255
    y_ignorar = int(lh * 0.70)
    mask[y_ignorar:, :] = 0

    novos = []
    ja_conhecidos = []

    for row, col, img in slots:
        melhor = 0.0
        melhor_arq = None
        for arq, tmpl in icones:
            result = cv2.matchTemplate(img, tmpl, cv2.TM_CCORR_NORMED, mask=mask)
            score = float(result[0][0])
            if score > melhor:
                melhor = score
                melhor_arq = arq
        if melhor >= LIMIAR_JA_CONHECIDO:
            ja_conhecidos.append((row, col, img, melhor_arq, melhor))
        else:
            novos.append((row, col, img))

    return novos, ja_conhecidos


# ==============================================================================
# PREVIEW E NOMEAÇÃO
# ==============================================================================

def mostrar_preview(img_bgr, nome_janela='Item'):
    """Exibe preview ampliado do ícone numa janela OpenCV."""
    h, w = img_bgr.shape[:2]
    ampliado = cv2.resize(
        img_bgr,
        (w * PREVIEW_ESCALA, h * PREVIEW_ESCALA),
        interpolation=cv2.INTER_NEAREST
    )
    cv2.imshow(nome_janela, ampliado)
    cv2.waitKey(1)


def salvar_icone(img_bgr, nome_arquivo):
    """
    Salva o ícone em fotos/ como PNG.
    A zona inferior (onde fica o número de quantidade) é zerada antes de salvar,
    assim o template nunca muda independente da quantidade do item.
    """
    if not nome_arquivo.endswith('.png'):
        nome_arquivo += '.png'

    # Zerar a zona de quantidade (30% inferior do ícone)
    h, w = img_bgr.shape[:2]
    y_ignorar = int(h * 0.70)
    icone = img_bgr.copy()
    icone[y_ignorar:, :] = 0  # preenche de preto a zona do número

    caminho = os.path.join(PASTA_FOTOS, nome_arquivo)
    cv2.imwrite(caminho, icone)
    return caminho


def construir_grade_visual(slots, colunas_grade=8):
    """
    Monta uma imagem com todos os ícones em grade, com número no canto.
    Retorna a imagem BGR.
    """
    if not slots:
        return None

    # Tamanho de cada célula na grade de preview
    lh, lw = slots[0][2].shape[:2]
    escala  = PREVIEW_ESCALA
    cw = lw * escala + 2   # largura da célula com borda
    ch = lh * escala + 14  # altura da célula com espaço para o número

    total   = len(slots)
    colunas = min(colunas_grade, total)
    linhas  = (total + colunas - 1) // colunas

    canvas = np.zeros((linhas * ch, colunas * cw, 3), dtype=np.uint8)
    canvas[:] = 40  # fundo cinza escuro

    for idx, (_, _, img) in enumerate(slots):
        r = idx // colunas
        c = idx % colunas
        x = c * cw + 1
        y = r * ch + 1

        cell = cv2.resize(img, (lw * escala, lh * escala), interpolation=cv2.INTER_NEAREST)
        canvas[y:y + lh * escala, x:x + lw * escala] = cell

        # Número do slot sobre a célula
        cv2.putText(
            canvas, str(idx + 1),
            (x + 2, y + 12),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA
        )

    return canvas


def _proximo_numero():
    """Retorna o próximo número sequencial disponível em fotos/ (ex: 41 se 1-40 existem)."""
    existentes = set()
    for arq in os.listdir(PASTA_FOTOS):
        nome, ext = os.path.splitext(arq)
        if ext == '.png' and nome.isdigit():
            existentes.add(int(nome))
    n = 1
    while n in existentes:
        n += 1
    return n


def nomear_e_salvar_slots(slots):
    """
    Exibe grade visual com todos os ícones numerados.
    Os ícones são salvos automaticamente com números sequenciais
    a partir do próximo disponível em fotos/ (ex: 41, 42...).
    ENTER em branco ou '-' pula o item. 'fim' encerra antes do último.
    Retorna dicionário {caminho_imagem: nome_recurso} para o bot.
    """
    total = len(slots)
    if total == 0:
        print('  Nenhum slot ocupado encontrado.')
        return {}

    proximo_num = _proximo_numero()
    print()
    print('=' * 60)
    print('  NOMEAÇÃO EM LOTE DOS RECURSOS')
    print('=' * 60)
    print(f'\n  {total} item(s) detectado(s).')
    print(f'  Numeração automática a partir de: {proximo_num}')
    print('  ENTER em branco ou "-" pula o item. "fim" encerra.\n')

    # ---- Mostrar grade ------------------------------------------------
    grade_img = construir_grade_visual(slots)
    cv2.imshow('Grade de Itens - numeros correspondem ao terminal', grade_img)
    cv2.waitKey(1)

    salvar_indices = []  # índices que o usuário não pulou

    for idx in range(total):
        row, col, img = slots[idx]

        # Destacar item atual na janela
        grade_img2 = grade_img.copy()
        lh, lw = img.shape[:2]
        escala = PREVIEW_ESCALA
        colunas_grade = 8
        colunas = min(colunas_grade, total)
        cw = lw * escala + 2
        ch = lh * escala + 14
        r = idx // colunas
        c = idx % colunas
        x1 = c * cw
        y1 = r * ch
        cv2.rectangle(grade_img2, (x1, y1), (x1 + cw - 1, y1 + ch - 1), (0, 200, 0), 2)
        cv2.imshow('Grade de Itens - numeros correspondem ao terminal', grade_img2)
        cv2.waitKey(1)

        num_destino = proximo_num + len(salvar_indices)
        try:
            resposta = input(f'  [{idx + 1:>2}/{total}] Salvar como {num_destino}.png? (ENTER=sim / -=pular / fim=encerrar): ').strip()
        except (KeyboardInterrupt, EOFError):
            print('\n  Encerrado.')
            break

        if resposta.lower() == 'fim':
            break
        if resposta == '-':
            print(f'  Pulado.')
            continue

        salvar_indices.append(idx)

    cv2.destroyAllWindows()

    # ---- Salvar com numeração sequencial --------------------------------
    recursos_salvos = {}
    for i, idx in enumerate(salvar_indices):
        _, _, img = slots[idx]
        numero = proximo_num + i
        nome_arquivo = str(numero)
        caminho = salvar_icone(img, nome_arquivo)
        recursos_salvos[f'fotos/{nome_arquivo}.png'] = nome_arquivo
        print(f'  Salvo [{idx + 1}]: {caminho}')

    print(f'\n  {len(recursos_salvos)} recurso(s) salvo(s). (numerados de {proximo_num} a {proximo_num + len(recursos_salvos) - 1})')
    return recursos_salvos


# ==============================================================================
# GERAÇÃO DO TRECHO DE CÓDIGO
# ==============================================================================

def gerar_codigo_recursos(recursos):
    """Imprime o bloco RECURSOS pronto para colar em venda_rec.py."""
    if not recursos:
        return

    print('\n' + '=' * 60)
    print('  Copie e cole este bloco em venda_rec.py (substitua RECURSOS):')
    print('=' * 60)
    print()
    print('RECURSOS = {')
    for caminho, nome in recursos.items():
        print(f"    '{caminho}': '{nome}',")
    print('}')
    print()

    # Salvar também em arquivo para facilitar
    saida = os.path.join(PASTA_FOTOS, '_recursos_gerados.txt')
    with open(saida, 'w', encoding='utf-8') as f:
        f.write('RECURSOS = {\n')
        for caminho, nome in recursos.items():
            f.write(f"    '{caminho}': '{nome}',\n")
        f.write('}\n')
    print(f'  (Também salvo em {saida})')


# ==============================================================================
# ATUALIZAÇÃO AUTOMÁTICA DO venda_rec.py
# ==============================================================================

def atualizar_venda_rec(recursos):
    """Substitui automaticamente o bloco RECURSOS em venda_rec.py."""
    caminho_bot = 'venda_rec.py'
    if not os.path.exists(caminho_bot):
        print(f'[AVISO] {caminho_bot} não encontrado. Atualização manual necessária.')
        return

    with open(caminho_bot, 'r', encoding='utf-8') as f:
        conteudo = f.read()

    # Montar novo bloco
    linhas_recursos = ['RECURSOS = {\n']
    for caminho, nome in recursos.items():
        linhas_recursos.append(f"    '{caminho}': '{nome}',\n")
    linhas_recursos.append('}\n')
    novo_bloco = ''.join(linhas_recursos)

    # Substituir bloco existente entre "RECURSOS = {" e o "}" de fechamento
    import re
    padrao = r'RECURSOS\s*=\s*\{[^}]*\}'
    if re.search(padrao, conteudo, re.DOTALL):
        conteudo_novo = re.sub(padrao, novo_bloco.rstrip(), conteudo, flags=re.DOTALL)
        with open(caminho_bot, 'w', encoding='utf-8') as f:
            f.write(conteudo_novo)
        print(f'[OK] {caminho_bot} atualizado automaticamente com {len(recursos)} recursos.')
    else:
        print(f'[AVISO] Bloco RECURSOS não encontrado em {caminho_bot}.')
        print('        Faça a atualização manualmente usando o bloco acima.')


# ==============================================================================
# ENTRADA PRINCIPAL
# ==============================================================================

def main():
    print('=' * 60)
    print('  SEPARADOR DE INVENTÁRIO - Dofus Venda Bot')
    print('=' * 60)
    print()

    # 1. Obter imagem do inventário
    print()
    print('  Como fornecer a imagem do inventário?')
    print('  [1] Print manual (recomendado — sem distorção de DPI)')
    print('  [2] Captura automática da tela')
    modo = input('  Opção (1 ou 2): ').strip()

    caminho_imagem = None
    if modo == '1':
        print()
        print('  Instruções:')
        print('  1. Abra o Dofus com o inventário visível')
        print('  2. Pressione  Win + PrintScreen  (salva em Imagens\\Capturas de tela)')
        print('     OU use o Recorte e Esboço (Win + Shift + S) e salve como PNG')
        print('  3. Copie o arquivo para esta pasta com o nome  inventario.png')
        print(f'     Caminho: {os.path.abspath("inventario.png")}')
        print()
        input('  Pressione ENTER quando o arquivo inventario.png estiver pronto...')
        caminho_imagem = 'inventario.png'
        if not os.path.exists(caminho_imagem):
            print(f'[ERRO] Arquivo "{caminho_imagem}" não encontrado.')
            return

    # 2. Carregar ou calibrar grade
    # No modo imagem, a calibração é feita clicando diretamente na imagem PNG
    grade = carregar_grade(caminho_imagem=caminho_imagem if modo == '1' else None)
    if grade is None:
        return

    if modo == '2':
        print()
        print('  Abra o INVENTÁRIO no Dofus agora.')
        print('  Você tem 5 segundos...')
        for i in range(5, 0, -1):
            print(f'    {i}...')
            time.sleep(1)

    # 3. Extrair slots ocupados
    slots = extrair_slots(grade, caminho_imagem=caminho_imagem)

    if not slots:
        print('\n[AVISO] Nenhum slot ocupado detectado.')
        print('  Tente ajustar LIMIAR_VAZIO no topo do script.')
        return

    # 4. Filtrar slots que já temos em fotos/
    lw = grade['largura_slot']
    lh = grade['altura_slot']
    slots_novos, ja_conhecidos = filtrar_slots_novos(slots, lw, lh)

    if ja_conhecidos:
        print(f'\n  {len(ja_conhecidos)} slot(s) já reconhecido(s) em fotos/ — ignorados:')
        for row, col, _, arq, score in ja_conhecidos:
            print(f'    L{row}C{col} → {arq}  (score={score:.2f})')

    if not slots_novos:
        print('\n  Nenhum recurso novo encontrado. Todos já estão em fotos/.')
        return

    print(f'\n  {len(slots_novos)} recurso(s) novo(s) para salvar.')

    # 5. Nomear e salvar cada ícone
    recursos = nomear_e_salvar_slots(slots_novos)

    if not recursos:
        print('\nNenhum recurso salvo.')
        return

    # 6. Mostrar bloco de código e atualizar venda_rec.py
    gerar_codigo_recursos(recursos)

    atualizar = input('\n  Atualizar venda_rec.py automaticamente? (s/n): ').strip().lower()
    if atualizar == 's':
        atualizar_venda_rec(recursos)

    print('\n[OK] Concluído!')
    print(f'  {len(recursos)} recurso(s) salvo(s) em fotos/')


if __name__ == '__main__':
    main()
