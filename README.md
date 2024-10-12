# EvapoGIS 🌿💧

[![Release](https://img.shields.io/github/release/SeuUsuario/EvapoGIS.svg)](https://github.com/SeuUsuario/EvapoGIS/releases)
[![License](https://img.shields.io/github/license/SeuUsuario/EvapoGIS.svg)](https://github.com/SeuUsuario/EvapoGIS/blob/main/LICENSE)
[![QGIS](https://img.shields.io/badge/QGIS-3.0%2B-brightgreen.svg)](https://qgis.org)

![EvapoGIS Banner](https://raw.githubusercontent.com/SeuUsuario/EvapoGIS/main/docs/banner.png)

## 📖 Índice

- [Sobre](#-sobre)
- [Características](#-características)
- [Instalação](#-instalação)
- [Uso](#-uso)
- [Capturas de Tela](#-capturas-de-tela)
- [Dependências](#-dependências)
- [Contribuição](#-contribuição)
- [Licença](#-licença)
- [Contato](#-contato)

## 🌟 Sobre

**EvapoGIS** é um plugin para [QGIS](https://qgis.org) que facilita o processamento e análise de dados geoespaciais relacionados à evapotranspiração. Integrando ferramentas avançadas de processamento raster e dados meteorológicos, o EvapoGIS permite que usuários:

- Processar arquivos MTL e MDE de forma eficiente.
- Integrar bandas raster para análises detalhadas.
- Realizar recortes geoespaciais com shapefiles personalizados.
- Calcular índices de evapotranspiração (ETo) instantâneos e diários.

Ideal para profissionais de geociências, agronomia e gestão ambiental que buscam otimizar seus fluxos de trabalho no QGIS.

## 🛠️ Características

- **Interface Intuitiva:** Facilita a seleção de arquivos e diretórios necessários para o processamento.
- **Processamento Eficiente:** Integra múltiplas etapas de processamento em uma única ação.
- **Feedback Visual:** Mensagens claras indicam o progresso e o status das operações.
- **Compatibilidade:** Funciona com diversas versões do QGIS (3.0+).

## 📥 Instalação

### 🚀 Via QGIS Plugin Manager

1. Abra o **QGIS**.
2. Navegue até `Plugins` > `Gerenciar e Instalar Plugins...`.
3. Na aba **Todos**, procure por **EvapoGIS**.
4. Clique em **Instalar**.
5. Após a instalação, o ícone do **EvapoGIS** aparecerá na barra de ferramentas.

### 🛠️ Instalação Manual

1. Baixe o repositório como um **ZIP**.
2. Extraia a pasta `EvapoGIS` para o diretório de plugins do QGIS:
   - **Windows:** `C:\Users\<SeuUsuário>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
   - **macOS/Linux:** `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
3. Abra o **QGIS** e ative o plugin via `Plugins` > `Gerenciar e Instalar Plugins...`.

## 🎛️ Uso

1. **Abrir o Plugin:**
   - Clique no ícone do **EvapoGIS** na barra de ferramentas do QGIS.
2. **Selecionar Arquivos:**
   - Utilize os botões **Selecionar** para escolher os arquivos MTL, MDE, bandas raster, shapefile de recorte e diretório de saída.
3. **Inserir Dados Meteorológicos:**
   - Preencha os campos de **Velocidade do Vento a 2m**, **ETo Instantâneo** e **ETo Diário**.
4. **Processar:**
   - Clique no botão **Processar** para iniciar o processamento.
   - A mensagem final confirmará a conclusão bem-sucedida do processo.

## 📸 Capturas de Tela

### Interface do EvapoGIS

![Interface do EvapoGIS](https://raw.githubusercontent.com/SeuUsuario/EvapoGIS/main/docs/screenshot.png)

### Resultado do Processamento

![Resultado](https://raw.githubusercontent.com/SeuUsuario/EvapoGIS/main/docs/result.png)

## 🔗 Dependências

O **EvapoGIS** depende das seguintes bibliotecas Python:

- [rasterio](https://rasterio.readthedocs.io/)
- [numpy](https://numpy.org/)
- [pandas](https://pandas.pydata.org/)
- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/)

### 📦 Instalando Dependências

As dependências devem ser instaladas no ambiente Python do QGIS. Siga os passos abaixo:

#### **Windows (usando OSGeo4W Shell):**

1. Abra o **OSGeo4W Shell** como administrador.
2. Atualize o `pip`:
   ```bash
   python -m pip install --upgrade pip
