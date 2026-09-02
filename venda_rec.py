"""
Bot de automação de vendas - Dofus
===================================
Detecta recursos no inventário ao vivo, lê quantidades via OCR e vende
automaticamente no Hôtel des Ventes (HDV).

ANTES DE USAR:
  1. Instale o Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki
  2. Execute calibrar.py para mapear as regiões da tela
  3. Execute separar_inventario.py para salvar os ícones em fotos/
"""

import pyautogui as py
import pytesseract
import cv2
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance
import time
import re
import json
import os
import subprocess
from collections import namedtuple

Box = namedtuple('Box', ['left', 'top', 'width', 'height'])

def _box_center(box):
    return (box.left + box.width // 2, box.top + box.height // 2)

# ==============================================================================
# CONFIGURAÇÃO
# ==============================================================================

TESSERACT_PATH      = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
CONFIG_FILE         = 'config.json'
CONFIG_GRADE        = 'config_inventario.json'
PASTA_FOTOS         = 'fotos'

DELAY_ACAO          = 0.5   # Segundos entre ações
DELAY_CAMPO         = 0.4   # Espera após preencher campo / clicar no seletor de lote
DELAY_VENDA         = 0.7   # Espera após confirmar venda
DELAY_INICIO        = 5     # Contagem regressiva antes de começar

CONFIDENCE          = 0.9  # Confiança mínima para reconhecimento de ícone na tela
UNDERCUTTING        = 1     # Kamas a subtrair do menor preço encontrado
QUANTIDADE_ZONA_PCT = 0.35  # Fração inferior do ícone reservada para OCR de quantidade
LOTES               = [100, 10, 1]
LIMIAR_INVENTARIO   = 0.80  # Score mínimo para aceitar match no scan do inventário
PRECO_MAXIMO        = 150_000  # Cap de sanidade para leitura de preço via OCR
DEBUG_OCR           = False       # Salva imagem e texto OCR em debug_ocr/ para diagnóstico

PREFIXOS_SISTEMA = ('calibracao_', '_', 'campo_', 'btn_', 'vendaon', 'vendaoff')

REGIOES_PADRAO = {
    'preco_100':   (0, 0, 150, 30),
    'preco_10':    (0, 0, 150, 30),
    'preco_1':     (0, 0, 150, 30),
    'campo_preco': (0, 0, 150, 30),
    'btn_lote_1':  (0, 0, 60, 30),
    'btn_lote_10': (0, 0, 60, 30),
    'btn_lote_100':(0, 0, 60, 30),
    'btn_vender':  (0, 0, 100, 40),
}


# ==============================================================================
# BOT
# ==============================================================================

class DofusVendaBot:

    def __init__(self):
        self._configurar_tesseract()
        self.regioes = self._carregar_config()
        py.FAILSAFE = True

    # ── Inicialização ──────────────────────────────────────────────────────────

    def _configurar_tesseract(self):
        if not os.path.exists(TESSERACT_PATH):
            print(f'[AVISO] Tesseract não encontrado em: {TESSERACT_PATH}')
            print('         Baixe em: https://github.com/UB-Mannheim/tesseract/wiki')
        else:
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

    def _carregar_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8-sig') as f:
                dados = json.load(f)
            print(f'[OK] Configuração carregada de {CONFIG_FILE}')
            return dados.get('regioes', REGIOES_PADRAO)
        print(f'[AVISO] {CONFIG_FILE} não encontrado. Usando regiões padrão.')
        print('         Execute calibrar.py para mapear sua tela.')
        return REGIOES_PADRAO

    # ── OCR ────────────────────────────────────────────────────────────────────

    def _capturar_regiao(self, regiao):
        x, y, w, h = regiao
        return py.screenshot(region=(x, y, w, h))

    def _preprocessar_imagem(self, img):
        # Apaga o símbolo de kamas (dourado/âmbar) antes de converter p/ cinza,
        # impedindo que o Tesseract leia o glifo como "4" ou "5".
        arr = np.array(img.convert('RGB'))
        hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV)
        mask_kamas = cv2.inRange(hsv, np.array([15, 80, 80]), np.array([40, 255, 255]))
        arr[mask_kamas > 0] = [0, 0, 0]
        img = Image.fromarray(arr).convert('L')
        resample = getattr(Image, 'Resampling', Image).LANCZOS
        img = img.resize((img.width * 3, img.height * 3), resample)
        img = ImageEnhance.Contrast(img).enhance(2.5)
        img = img.filter(ImageFilter.SHARPEN)
        return img

    def _ocr_numero(self, img_pil):
        """
        OCR com bounding boxes por palavra.
        O preço está sempre alinhado à DIREITA do campo; ruídos da UI
        (ícone de kamas, indicador de lote) ficam à ESQUERDA com gaps grandes.
        Estratégia: constrói o preço da direita para a esquerda, incluindo
        tokens consecutivos cujo gap seja ≤ threshold de separador de milhar,
        parando ao encontrar um gap grande (fronteira de ruído).
        Fallback para image_to_string se image_to_data não retornar tokens.
        """
        cfg = '--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789'
        img = self._preprocessar_imagem(img_pil)

        # ── Tentativa 1: bounding boxes por palavra ────────────────────────
        data = pytesseract.image_to_data(
            img, config=cfg, output_type=pytesseract.Output.DICT
        )
        words = []
        for i, nivel in enumerate(data['level']):
            if nivel != 5:          # nível de palavra
                continue
            t = data['text'][i].strip()
            if not t:
                continue
            words.append({
                'text':  t,
                'left':  data['left'][i],
                'right': data['left'][i] + data['width'][i],
                'width': data['width'][i],
            })

        if words:
            words.sort(key=lambda w: w['left'])

            if len(words) == 1:
                try:
                    n = int(words[0]['text'])
                    return n if 1 <= n <= PRECO_MAXIMO else None
                except ValueError:
                    return None

            # Limiar de separador de milhar = 2,5× largura média de caractere
            avg_cw = sum(w['width'] / max(len(w['text']), 1) for w in words) / len(words)
            sep_thr = avg_cw * 2.5

            if DEBUG_OCR:
                gaps = [words[i+1]['left'] - words[i]['right'] for i in range(len(words)-1)]
                print(f'  [DEBUG] tokens={[w["text"] for w in words]} '
                      f'gaps={[round(g) for g in gaps]} sep_thr={round(sep_thr)}')

            # Constrói preço da direita para a esquerda
            price_tokens = [words[-1]]
            for i in range(len(words) - 2, -1, -1):
                gap = words[i + 1]['left'] - words[i]['right']
                if gap <= sep_thr:
                    price_tokens.insert(0, words[i])
                else:
                    break   # gap grande = fronteira UI / preço

            price_text = ''.join(t['text'] for t in price_tokens)
            try:
                n = int(price_text)
                if 1 <= n <= PRECO_MAXIMO:
                    return n
            except ValueError:
                pass

        # ── Fallback: image_to_string + max() ─────────────────────────────
        texto = pytesseract.image_to_string(img, config=cfg)
        numeros = [int(m) for m in re.findall(r'\d+', texto)
                   if 1 <= int(m) <= PRECO_MAXIMO]
        return max(numeros) if numeros else None

    def ler_preco(self, lote):
        """
        Lê o preço de mercado para um lote via OCR.
        Realiza 3 leituras e usa a mediana para filtrar leituras espúrias.
        Descarta valores fora do intervalo 1 – PRECO_MAXIMO.
        """
        regiao = self.regioes.get(f'preco_{lote}')
        if regiao is None:
            print(f'  [AVISO] Região "preco_{lote}" não configurada.')
            return None

        leituras = []
        ultimo_v = None
        for tentativa in range(3):
            try:
                img_cap = self._capturar_regiao(regiao)

                if DEBUG_OCR:
                    os.makedirs('debug_ocr', exist_ok=True)
                    img_pre = self._preprocessar_imagem(img_cap)
                    img_pre.save(f'debug_ocr/preco_{lote}_t{tentativa}.png')
                    texto_raw = pytesseract.image_to_string(
                        img_pre,
                        config='--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789'
                    ).strip()
                    print(f'  [DEBUG] OCR raw lote {lote} t{tentativa}: "{texto_raw}"')

                v = self._ocr_numero(img_cap)
                if v is not None and 1 <= v <= PRECO_MAXIMO:
                    leituras.append(v)
                    if v == ultimo_v:   # duas leituras consecutivas iguais → suficiente
                        break
                    ultimo_v = v
            except Exception as e:
                print(f'  [DEBUG] Exceção OCR: {e}')
            if tentativa < 2:
                time.sleep(0.05)

        if not leituras:
            print(f'  [AVISO] Não foi possível ler preço do lote {lote}.')
            return None

        leituras.sort()
        preco = leituras[len(leituras) // 2]
        print(f'  Preço mercado (lote {lote}): {preco:,} kamas')
        return preco

    # ── Detecção de ícones ─────────────────────────────────────────────────────

    def encontrar_recurso(self, caminho_imagem, regiao_busca=None):
        """
        Localiza um ícone de recurso na tela usando máscara que ignora
        a zona de quantidade (inferior).
        regiao_busca: (x, y, w, h) para limitar a busca a uma área da tela.
        Retorna Box ou None.
        """
        if not os.path.exists(caminho_imagem):
            print(f'[ERRO] Imagem não encontrada: {caminho_imagem}')
            return None
        try:
            template = cv2.imread(caminho_imagem)
            if template is None:
                return None
            th, tw = template.shape[:2]
            mask = np.ones((th, tw), dtype=np.uint8) * 255
            mask[int(th * (1 - QUANTIDADE_ZONA_PCT)):, :] = 0

            if regiao_busca:
                rx, ry, rw, rh = regiao_busca
                img_pil = py.screenshot(region=(rx, ry, rw, rh))
                screen = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
                offset_x, offset_y = rx, ry
            else:
                screen = cv2.cvtColor(np.array(py.screenshot()), cv2.COLOR_RGB2BGR)
                offset_x, offset_y = 0, 0

            result = cv2.matchTemplate(screen, template, cv2.TM_CCORR_NORMED, mask=mask)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val >= CONFIDENCE:
                x, y = max_loc
                return Box(left=x + offset_x, top=y + offset_y, width=tw, height=th)
        except Exception as e:
            print(f'[ERRO] {caminho_imagem}: {e}')
        return None

    def _score_ui(self, caminho_imagem):
        """Retorna o score de match (0.0–1.0) de um elemento de UI na tela atual."""
        if not os.path.exists(caminho_imagem):
            return 0.0
        try:
            template = cv2.imread(caminho_imagem)
            if template is None:
                return 0.0
            screen = cv2.cvtColor(np.array(py.screenshot()), cv2.COLOR_RGB2BGR)
            result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
            return float(cv2.minMaxLoc(result)[1])
        except Exception:
            return 0.0

    def encontrar_ui(self, caminho_imagem, confidence=0.7):
        """
        Localiza um elemento de interface (botão, campo) sem máscara.
        Retorna Box ou None.
        """
        if not os.path.exists(caminho_imagem):
            return None
        try:
            template = cv2.imread(caminho_imagem)
            if template is None:
                return None
            th, tw = template.shape[:2]
            screen = cv2.cvtColor(np.array(py.screenshot()), cv2.COLOR_RGB2BGR)
            result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val >= confidence:
                x, y = max_loc
                return Box(left=x, top=y, width=tw, height=th)
        except Exception as e:
            print(f'[ERRO UI] {caminho_imagem}: {e}')
        return None

    def verificar_slot_venda_ativo(self):
        return self.encontrar_ui(os.path.join(PASTA_FOTOS, 'vendaon.png')) is not None

    # ── Ações de interface ─────────────────────────────────────────────────────

    def _clicar_centro(self, box, delay=None):
        cx, cy = _box_center(box)
        py.click(cx, cy)
        time.sleep(delay if delay is not None else DELAY_ACAO)

    def definir_lote(self, quantidade):
        """Abre o seletor de lote e clica no botão do lote desejado."""
        for img_campo in ('campo_lote.png', 'campo_lote2.png'):
            box = self.encontrar_ui(os.path.join(PASTA_FOTOS, img_campo))
            if box:
                self._clicar_centro(box, delay=DELAY_CAMPO)
                break
        else:
            print('[AVISO] Campo de lote não encontrado na tela.')
            return False

        img_lote = os.path.join(PASTA_FOTOS, f'btn_lote_{quantidade}.png')
        box_lote = self.encontrar_ui(img_lote)
        if box_lote is None:
            print(f'[AVISO] {img_lote} não encontrado na tela.')
            return False
        self._clicar_centro(box_lote, delay=DELAY_CAMPO)
        return True

    def definir_preco(self, preco):
        """Preenche o campo de preço com o valor desejado."""
        regiao = self.regioes.get('campo_preco')
        if regiao is None:
            print('[AVISO] Região campo_preco não configurada.')
            return False
        # Coloca o preço na área de transferência para colar instantaneamente
        subprocess.run('clip', input=str(preco).encode('ascii'), check=True)
        x = regiao[0] + regiao[2] // 2
        y = regiao[1] + regiao[3] // 2
        py.click(x, y)
        time.sleep(DELAY_CAMPO)
        py.hotkey('ctrl', 'a')
        time.sleep(0.05)
        py.hotkey('ctrl', 'v')
        time.sleep(0.2)
        return True

    def clicar_vender(self):
        """Clica no botão Vender (por coordenada ou por imagem)."""
        regiao = self.regioes.get('btn_vender')
        if regiao:
            py.click(regiao[0] + regiao[2] // 2, regiao[1] + regiao[3] // 2)
            time.sleep(DELAY_VENDA)
            return True
        box = self.encontrar_recurso(os.path.join(PASTA_FOTOS, 'btn_vender.png'))
        if box:
            self._clicar_centro(box, delay=DELAY_VENDA)
            return True
        print('[AVISO] Botão Vender não encontrado.')
        return False

    # ── Lógica de venda ────────────────────────────────────────────────────────

    def calcular_preco_venda(self, lote):
        preco = self.ler_preco(lote)
        if preco and preco > UNDERCUTTING:
            return preco - UNDERCUTTING
        return preco

    def _detectar_lote_disponivel(self):
        """
        Aguarda e detecta qual campo de lote apareceu após clicar no recurso.
        Otimizado: tira UMA screenshot por tentativa e compara os três templates.
          - campo_lote3.png (≥100 itens) → retorna 100
          - campo_lote.png  (≥10 itens)  → retorna 10
          - campo_lote2.png (<10 itens)  → retorna 1
        Tenta por até ~2.5s antes de desistir.
        """
        cam100 = os.path.join(PASTA_FOTOS, 'campo_lote3.png')
        cam10  = os.path.join(PASTA_FOTOS, 'campo_lote.png')
        cam1   = os.path.join(PASTA_FOTOS, 'campo_lote2.png')
        tmpl100 = cv2.imread(cam100)   # pode ser None se não capturado ainda
        tmpl10  = cv2.imread(cam10)
        tmpl1   = cv2.imread(cam1)
        if tmpl10 is None or tmpl1 is None:
            print('[AVISO] Imagens campo_lote não encontradas.')
            return None
        LIMIAR = 0.75

        for _ in range(7):  # verifica imediatamente + 6 × 0.35s ≈ 2.1s
            screen = cv2.cvtColor(np.array(py.screenshot()), cv2.COLOR_RGB2BGR)
            s100 = float(cv2.minMaxLoc(
                cv2.matchTemplate(screen, tmpl100, cv2.TM_CCOEFF_NORMED))[1]) \
                if tmpl100 is not None else 0.0
            s10  = float(cv2.minMaxLoc(
                cv2.matchTemplate(screen, tmpl10, cv2.TM_CCOEFF_NORMED))[1])
            s1   = float(cv2.minMaxLoc(
                cv2.matchTemplate(screen, tmpl1,  cv2.TM_CCOEFF_NORMED))[1])
            melhor = max(s100, s10, s1)
            if melhor >= LIMIAR:
                if s100 >= s10 and s100 >= s1:
                    lote, nome = 100, 'campo_lote3'
                elif s10 >= s1:
                    lote, nome = 10, 'campo_lote'
                else:
                    lote, nome = 1, 'campo_lote2'
                print(f'  Campo detectado: {nome}  (score={melhor:.2f})')
                return lote
            time.sleep(0.35)
        return None

    def vender_recurso(self, caminho_imagem, nome, regiao_inv):
        """
        Vende um recurso até ele sumir do inventário.
        regiao_inv: (x, y, w, h) da grade do inventário — a busca é limitada
        a essa área para evitar falsos positivos no slot do HDV.
        """
        print(f'\n[BOT] {nome}')

        vendidas = 0
        falhas_seguidas = 0
        MAX_FALHAS = 5

        while falhas_seguidas < MAX_FALHAS:
            box = self.encontrar_recurso(caminho_imagem, regiao_busca=regiao_inv)
            if box is None:
                print(f'  Recurso esgotado no inventário.')
                break

            self._clicar_centro(box, delay=DELAY_ACAO)
            # Pequena pausa para o HDV processar o clique
            time.sleep(0.3)

            lote = self._detectar_lote_disponivel()
            if lote is None:
                print(f'  [AVISO] Campo de lote não detectado ({falhas_seguidas+1}/{MAX_FALHAS}).')
                falhas_seguidas += 1
                continue

            preco = self.calcular_preco_venda(lote)
            if not preco or preco <= 0:
                print(f'  Sem preço para lote {lote}. Tentativa {falhas_seguidas+1}/{MAX_FALHAS}.')
                falhas_seguidas += 1
                continue

            print(f'  Lote {lote} × {preco:,} kamas...')
            if self.definir_lote(lote) and self.definir_preco(preco) and self.clicar_vender():
                vendidas += lote
                falhas_seguidas = 0
                print(f'  [OK] Total vendido: {vendidas}')
            else:
                falhas_seguidas += 1

        print(f'  Concluído: {vendidas} unidade(s) de {nome}.')
        return vendidas > 0

    # ── Scan do inventário ─────────────────────────────────────────────────────

    def escanear_inventario(self):
        """
        Captura o inventário ao vivo e identifica quais recursos estão presentes.
        Retorna dict {caminho_icone: nome} ou None se config_inventario.json não existir.
        """
        if not os.path.exists(CONFIG_GRADE):
            print(f'[ERRO] {CONFIG_GRADE} não encontrado.')
            print('       Execute separar_inventario.py para calibrar a grade.')
            return None

        with open(CONFIG_GRADE, 'r', encoding='utf-8-sig') as f:
            grade = json.load(f)

        # Carregar todos os ícones de recursos (excluindo arquivos de sistema)
        icones = {}
        for arq in os.listdir(PASTA_FOTOS):
            if not arq.endswith('.png') or any(arq.startswith(p) for p in PREFIXOS_SISTEMA):
                continue
            caminho = os.path.join(PASTA_FOTOS, arq)
            img = cv2.imread(caminho)
            if img is not None:
                nome = os.path.splitext(arq)[0].replace('_', ' ')
                icones[caminho] = (nome, img)

        if not icones:
            print('[AVISO] Nenhum ícone de recurso encontrado em fotos/')
            return {}

        x0, y0    = grade['x_inicio'], grade['y_inicio']
        lw, lh    = grade['largura_slot'], grade['altura_slot']
        cols, rows = grade['colunas'], grade['linhas']
        regiao_inv = (x0, y0, lw * cols, lh * rows)
        y_qtd     = int(lh * (1 - QUANTIDADE_ZONA_PCT))

        mask = np.ones((lh, lw), dtype=np.uint8) * 255
        mask[y_qtd:, :] = 0

        print(f'  Escaneando inventário ({cols}×{rows} slots)...')
        img_pil = py.screenshot(region=(x0, y0, lw * cols, lh * rows))
        inv = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

        encontrados = {}
        for row in range(rows):
            for col in range(cols):
                slot = inv[row * lh:(row + 1) * lh, col * lw:(col + 1) * lw]

                # Pular slots vazios (baixa variância de pixel)
                if float(np.var(cv2.cvtColor(slot, cv2.COLOR_BGR2GRAY))) <= 15:
                    continue

                melhor_score, melhor_cam, melhor_nome = 0.0, None, None
                for caminho, (nome, tmpl) in icones.items():
                    t = cv2.resize(tmpl, (lw, lh)) if tmpl.shape[:2] != (lh, lw) else tmpl
                    score = float(cv2.matchTemplate(slot, t, cv2.TM_CCORR_NORMED, mask=mask)[0][0])
                    if score > melhor_score:
                        melhor_score, melhor_cam, melhor_nome = score, caminho, nome

                if melhor_score >= LIMIAR_INVENTARIO and melhor_cam and melhor_cam not in encontrados:
                    encontrados[melhor_cam] = (melhor_nome, regiao_inv)
                    print(f'  L{row}C{col} → {melhor_nome}  score={melhor_score:.2f}')

        print(f'  {len(encontrados)} recurso(s) identificado(s).')
        return encontrados

    # ── Loop principal ─────────────────────────────────────────────────────────

    def executar(self):
        """
        Fluxo principal:
        1. Pede ao usuário para abrir o inventário no Dofus.
        2. Escaneia o inventário e lê quantidades via OCR.
        3. Pede ao usuário para abrir o HDV.
        4. Vende todos os recursos encontrados.
        """
        print('=' * 60)
        print('  BOT DE VENDAS DOFUS')
        print('  Ctrl+C ou mova o mouse ao canto superior esquerdo para parar')
        print('=' * 60)

        if not os.path.exists(CONFIG_GRADE):
            print(f'\n[ERRO] {CONFIG_GRADE} não encontrado.')
            print('       Execute separar_inventario.py para criar a grade do inventário.')
            return

        # Passo 1: Escanear inventário
        print(f'\n  Abra o INVENTÁRIO no Dofus agora.')
        print(f'  Você tem {DELAY_INICIO}s...')
        for i in range(DELAY_INICIO, 0, -1):
            print(f'    {i}...')
            time.sleep(1)

        recursos = self.escanear_inventario()
        if not recursos:
            print('[AVISO] Nenhum recurso identificado no inventário.')
            return

        print('\n  Recursos detectados:')
        for nome, _ in recursos.values():
            print(f'  • {nome}')

        # Passo 2: Ir para o HDV
        print(f'\n  {len(recursos)} recurso(s) a vender. Abra o HDV agora.')
        print(f'  Você tem {DELAY_INICIO}s...')
        for i in range(DELAY_INICIO, 0, -1):
            print(f'    {i}...')
            time.sleep(1)

        # Passo 3: Vender — cada recurso até esgotar
        ok, falha = 0, 0
        for caminho, (nome, regiao_inv) in recursos.items():
            try:
                if self.vender_recurso(caminho, nome, regiao_inv):
                    ok += 1
                else:
                    falha += 1
            except py.FailSafeException:
                print('\n[BOT] Parado pelo FailSafe (canto superior esquerdo).')
                break
            except KeyboardInterrupt:
                print('\n[BOT] Parado pelo usuário (Ctrl+C).')
                break

        print('\n' + '=' * 60)
        print(f'  Sucesso: {ok}   Falha: {falha}')
        print('=' * 60)


# ==============================================================================
# ENTRADA PRINCIPAL
# ==============================================================================

if __name__ == '__main__':
    DofusVendaBot().executar()
