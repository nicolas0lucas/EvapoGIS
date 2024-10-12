# -*- coding: utf-8 -*-
import os
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QMessageBox, QInputDialog
from .processing_functions import run_processing  # Importe a função run_processing

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'EvapoGIS.ui'))


class EvapoGISDialog(QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        super(EvapoGISDialog, self).__init__(parent)
        self.setupUi(self)

        # Conectar botões a funções
        self.selectMTLButton.clicked.connect(self.select_mtl_file)
        self.selectMDEButton.clicked.connect(self.select_mde_file)
        self.selectBandasButton.clicked.connect(self.select_bandas_directory)
        self.selectShapefileButton.clicked.connect(self.select_shapefile)
        self.selectOutputDirButton.clicked.connect(self.select_output_directory)
        self.selectRasterReferenciaButton.clicked.connect(self.select_raster_referencia)

        self.runButton.clicked.connect(self.run_processing)

    # Funções para selecionar arquivos/diretórios
    def select_mtl_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select MTL File", "", "MTL files (*.txt);;All files (*)")
        self.caminhoMTL.setText(filename)

    def select_mde_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Selecione o arquivo MDE", "", "Arquivos MDE (*.tif *.TIF *.tiff *.TIFF)")
        if file_name:
            self.caminhoMDE.setText(file_name)

    def select_bandas_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Bandas Directory")
        self.caminhoBandas.setText(directory)

    def select_shapefile(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select Shapefile", "", "Shapefiles (*.shp);;All files (*)")
        self.shapefilePath.setText(filename)

    def select_output_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        self.outputDir.setText(directory)

    def select_raster_referencia(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select Raster Referencia", "", "TIF files (*.tif);;All files (*)")
        self.rasterReferencia.setText(filename)

    def run_processing(self):
        # Obter os valores dos campos de entrada
        caminho_mtl = self.caminhoMTL.text()
        caminho_mdt = self.caminhoMDE.text()
        caminho_bandas = self.caminhoBandas.text()
        shapefile_path = self.shapefilePath.text()
        output_dir = self.outputDir.text()
        raster_referencia_path = self.rasterReferencia.text()
        try:
            u_2m = float(self.u2m.text())
            EToi = float(self.EToi.text())
            ETo = float(self.ETo.text())
        except ValueError:
            QMessageBox.warning(self, "Entrada Inválida", "Por favor, insira valores numéricos para os campos de entrada.")
            return

        # Chamar a função de processamento
        run_processing(
            caminho_mtl,
            caminho_mdt,
            caminho_bandas,
            shapefile_path,
            output_dir,
            raster_referencia_path,
            u_2m,
            EToi,
            ETo,
            self  # Passar a instância do diálogo para interagir dentro do processamento
        )
