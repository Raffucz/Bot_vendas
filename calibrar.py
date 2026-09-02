"""
Calibrador de Regiões - Dofus Venda Bot
=========================================
Execute este script UMA VEZ para mapear as regiões da sua tela.
Os dados são salvos em config.json e usados automaticamente pelo bot.

COMO USAR:
  1. Abra o Dofus e acesse o Hôtel des Ventes (HDV)
  2. Execute: python calibrar.py
  3. Siga as instruções no terminal
  4. As coordenadas são salvas em config.json
"""

import pyautogui as py
import json
import time
import os


# Regiões a calibrar: (chave, descrição do que selecionar)
REGIOES_PARA_CALIBRAR = [
    ('preco_100',   'a área onde aparece o PREÇO do lote de 100'),
    ('preco_10',    'a área onde aparece o PREÇO do lote de 10'),
    ('preco_1',     'a área onde aparece o PREÇO do lote de 1'),
    ('campo_preco', 'o CAMPO DE ENTRADA de preço (caixa de texto)'),
    ('campo_lote',  'o CAMPO DE ENTRADA de quantidade/lote'),
    ('btn_vender',  'o BOTÃO "Vender"'),
]

# Templates de imagem a capturar: (nome_arquivo, descrição)
TEMPLATES_PARA_CAPTURAR = [
    ('campo_lote3',  'o CAMPO DE LOTE quando há ≥100 unidades (aparece "100" no campo)'),
    ('btn_lote_100', 'o BOTÃO "100" no dropdown de lote'),
]

CONFIG_FILE = 'config.json'


def aguardar_enter(mensagem=''):
    if mensagem:
        print(mensagem)
    input('  >> Pressione ENTER quando estiver pronto...')


def capturar_regiao_interativa(descricao):
    """
    Guia o usuário a selecionar uma região da tela.
    Retorna (x, y, largura, altura).
    """
    print(f'\n  ETAPA: Selecione {descricao}')
    print('  1. Posicione o mouse no CANTO SUPERIOR ESQUERDO da região')
    aguardar_enter()
    x1, y1 = py.position()
    print(f'     Ponto 1 capturado: ({x1}, {y1})')

    print('  2. Posicione o mouse no CANTO INFERIOR DIREITO da região')
    aguardar_enter()
    x2, y2 = py.position()
    print(f'     Ponto 2 capturado: ({x2}, {y2})')

    x = min(x1, x2)
    y = min(y1, y2)
    w = abs(x2 - x1)
    h = abs(y2 - y1)

    if w < 5 or h < 5:
        print('  [AVISO] Região muito pequena, tente novamente.')
        return capturar_regiao_interativa(descricao)

    print(f'     Região definida: x={x}, y={y}, largura={w}, altura={h}')
    return [x, y, w, h]


def tirar_screenshot_regiao(regiao, nome_arquivo):
    """Tira screenshot de uma região para verificação visual."""
    x, y, w, h = regiao
    img = py.screenshot(region=(x, y, w, h))
    caminho = os.path.join('fotos', f'calibracao_{nome_arquivo}.png')
    os.makedirs('fotos', exist_ok=True)
    img.save(caminho)
    print(f'     Screenshot salvo em: {caminho}')


def _carregar_config_existente():
    """Carrega config.json existente ou retorna dict vazio."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            dados = json.load(f)
            return dados.get('regioes', {})
    return {}


def _salvar_config(regioes):
    """Salva as regiões no config.json."""
    config = {'regioes': regioes}
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    print(f'  Configuração salva em: {CONFIG_FILE}')


def _calibrar_regiao_unica(chave):
    """Recalibra apenas uma região específica sem alterar as demais."""
    entrada = dict(REGIOES_PARA_CALIBRAR)
    if chave not in entrada:
        chaves_validas = ', '.join(entrada.keys())
        print(f'[ERRO] Região "{chave}" não reconhecida.')
        print(f'       Regiões válidas: {chaves_validas}')
        return

    descricao = entrada[chave]
    print('=' * 60)
    print(f'  Recalibrando: {chave}')
    print('=' * 60)
    print('  Deixe o Dofus aberto no HDV.')
    print('  Você tem 3 segundos para ir para a janela do Dofus...')

    aguardar_enter()
    for i in range(3, 0, -1):
        print(f'    {i}...')
        time.sleep(1)

    regiao = capturar_regiao_interativa(descricao)
    tirar_screenshot_regiao(regiao, chave)

    confirma = input('\n  Esta região está correta? (s/n): ').strip().lower()
    if confirma != 's':
        print('  Recalibrando...')
        regiao = capturar_regiao_interativa(descricao)
        tirar_screenshot_regiao(regiao, chave)

    # Atualiza apenas a chave recalibrada, mantendo as demais
    regioes = _carregar_config_existente()
    regioes[chave] = regiao
    _salvar_config(regioes)
    print(f'\n[OK] Região "{chave}" atualizada com sucesso!')


def calibrar():
    print('=' * 60)
    print('  CALIBRADOR - Bot de Vendas Dofus')
    print('=' * 60)
    print()
    print('  IMPORTANTE:')
    print('  - Deixe o Dofus aberto com o HDV visível')
    print('  - Você terá 3 segundos para trocar de janela em cada etapa')
    print('  - Leia cada instrução ANTES de pressionar ENTER')
    print()

    aguardar_enter('  Pressione ENTER para começar a calibração...')

    regioes = _carregar_config_existente()

    for chave, descricao in REGIOES_PARA_CALIBRAR:
        print(f'\n{"─" * 50}')
        print(f'  Configurando: {chave}')

        # Dar tempo para o usuário trocar para o Dofus
        print('  Você tem 3 segundos para ir para a janela do Dofus...')
        for i in range(3, 0, -1):
            print(f'    {i}...')
            time.sleep(1)

        regiao = capturar_regiao_interativa(descricao)
        regioes[chave] = regiao

        # Salvar screenshot para verificação
        tirar_screenshot_regiao(regiao, chave)

        confirma = input('\n  Esta região está correta? (s/n): ').strip().lower()
        if confirma != 's':
            print('  Recalibrando...')
            regiao = capturar_regiao_interativa(descricao)
            regioes[chave] = regiao

    _salvar_config(regioes)

    print(f'\n{"=" * 60}')
    print(f'  Calibração concluída! Configuração salva em: {CONFIG_FILE}')
    print(f'  Execute venda_rec.py para iniciar o bot.')
    print(f'{"=" * 60}')


def verificar_posicao():
    """Utilitário: mostra a posição atual do mouse em tempo real."""
    print('Monitorando posição do mouse (Ctrl+C para parar)...')
    try:
        while True:
            x, y = py.position()
            print(f'  Mouse: ({x:4d}, {y:4d})', end='\r')
            time.sleep(0.1)
    except KeyboardInterrupt:
        print('\nMonitoramento encerrado.')


def _capturar_template(nome):
    """
    Captura uma região da tela e salva como template em fotos/<nome>.png.
    Usado para capturar campo_lote3, btn_lote_100, etc.
    """
    entrada = dict(TEMPLATES_PARA_CAPTURAR)
    if nome not in entrada:
        nomes_validos = ', '.join(entrada.keys())
        print(f'[ERRO] Template "{nome}" não reconhecido.')
        print(f'       Templates disponíveis: {nomes_validos}')
        return

    descricao = entrada[nome]
    print('=' * 60)
    print(f'  Capturando template: {nome}.png')
    print(f'  → {descricao}')
    print('=' * 60)
    print()
    print('  IMPORTANTE: deixe o Dofus aberto com o HDV visível')
    print('  e o estado correto na tela (ex: arraste um recurso com')
    print('  ≥100 unidades para o slot de venda para campo_lote3).')
    print()

    aguardar_enter('  Pressione ENTER quando o elemento estiver visível...')
    for i in range(3, 0, -1):
        print(f'    {i}...')
        time.sleep(1)

    regiao = capturar_regiao_interativa(descricao)
    x, y, w, h = regiao
    img = py.screenshot(region=(x, y, w, h))
    os.makedirs('fotos', exist_ok=True)
    caminho = os.path.join('fotos', f'{nome}.png')
    img.save(caminho)
    print(f'\n[OK] Template salvo em: {caminho}  ({w}×{h} px)')
    print('     O bot usará este template automaticamente.')


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--posicao':
        verificar_posicao()
    elif len(sys.argv) > 1 and sys.argv[1] == '--fix':
        if len(sys.argv) < 3:
            print('Uso: python calibrar.py --fix <nome_da_regiao>')
            print('Regiões disponíveis:', ', '.join(c for c, _ in REGIOES_PARA_CALIBRAR))
        else:
            _calibrar_regiao_unica(sys.argv[2])
    elif len(sys.argv) > 1 and sys.argv[1] == '--template':
        if len(sys.argv) < 3:
            print('Uso: python calibrar.py --template <nome>')
            print('Templates disponíveis:', ', '.join(c for c, _ in TEMPLATES_PARA_CAPTURAR))
        else:
            _capturar_template(sys.argv[2])
    else:
        calibrar()
