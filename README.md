
# Bot de Automação de Vendas - Dofus 🎮

Este projeto contém dois scripts em Python desenvolvidos para automatizar a leitura do inventário e a venda de recursos no *Hôtel des Ventes* (HDV) do **Dofus** utilizando visão computacional (`OpenCV`), reconhecimento de texto (`Tesseract OCR`) e automação de mouse/teclado (`PyAutoGUI`).

---

## 📁 Estrutura do Projeto

Certifique-se de que os arquivos principais e a pasta de recursos estejam organizados na mesma pasta:

```text
📂 sua-pasta-do-bot/
├── 📄 venda_rec.py             # Bot principal de automação de vendas no HDV
├── 📄 separar_inventario.py    # Ferramenta para calibração de grade e captura de ícones
├── 📄 config_inventario.json   # (Gerado automaticamente) Configuração da grade
├── 📂 fotos/                   # Pasta contendo os ícones dos itens e imagens de UI
└── 📄 README.md                # Este manual de instruções

```

---

## ⚙️ Pré-requisitos e Instalação

### 1. Instalar o Python

Certifique-se de ter o [Python](https://www.google.com/search?q=https://www.python.org/) instalado em seu computador (versão 3.8 ou superior recomendada).

### 2. Instalar as Bibliotecas Necessárias

Abra o terminal (Prompt de Comando ou PowerShell) na pasta do projeto e instale as dependências executando:

```bash
pip install pyautogui pytesseract opencv-python numpy pillow

```

### 3. Instalar o Tesseract OCR

O bot precisa do Tesseract instalado para ler os preços na tela.

1. Baixe o instalador para Windows em: [UB-Mannheim Tesseract OCR Wiki](https://github.com/UB-Mannheim/tesseract/wiki)
2. Instale o programa no caminho padrão: `C:\Program Files\Tesseract-OCR\tesseract.exe`
3. *(Opcional)* Caso instale em outro diretório, atualize a variável `TESSERACT_PATH` no início do arquivo `venda_rec.py`.

---

## 🚀 Como Usar (Passo a Passo)

### Passo 1: Preparar as Imagens de Interface (UI)

Na pasta `fotos/`, o bot precisa de algumas imagens de referência da interface do jogo para funcionar corretamente (botões de lote, campos de preço, ícones de status, etc.). Certifique-se de que imagens como `vendaon.png`, `btn_vender.png`, `campo_lote.png`, etc., estejam devidamente salvas nessa pasta.

### Passo 2: Mapear o Inventário (`separar_inventario.py`)

Antes de vender qualquer coisa, o script auxiliar precisa saber onde fica o seu inventário na tela para recortar e salvar os ícones dos seus recursos.

1. Abra o Dofus e deixe o **Inventário visível**.
2. No terminal, execute o script de separação:
```bash
python separar_inventario.py

```


3. Escolha o modo de calibração desejado (Recomenda-se o **Print manual** para evitar distorções de escala/DPI).
4. Siga as instruções na tela para marcar a grade do inventário.
5. O programa detectará os itens novos, exibirá uma prévia e pedirá para você confirmar a adição deles. O script também atualizará o mapeamento automaticamente no arquivo principal se desejar.

### Passo 3: Executar o Bot de Vendas (`venda_rec.py`)

Com a grade calibrada e os ícones salvos:

1. Abra o jogo e vá até o **Hôtel des Ventes (HDV)**.
2. No terminal, execute o bot principal:
```bash
python venda_rec.py

```


3. O bot solicitará que você abra o inventário e fará a contagem regressiva. Em seguida, escaneará os recursos presentes.
4. Após o escaneamento, o bot pedirá para você abrir o HDV e iniciará o processo automatizado de undercutting e venda de lotes (1, 10 ou 100 unidades).

---

## 🛑 Segurança e Parada de Emergência (FailSafe)

* **Parada de Emergência:** Para interromper o bot imediatamente a qualquer momento, **jogue o cursor do mouse rapidamente para o canto superior esquerdo da tela** (ativando o *FailSafe* do PyAutoGUI) ou pressione `Ctrl + C` no terminal.
* **Resolução e DPI:** Recomenda-se jogar em tela cheia ou modo janela com escala de vídeo/interface em 100% para garantir que as coordenadas de OCR e captura de tela fiquem precisas.

```

```
