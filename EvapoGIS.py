from PyQt5.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction
import os.path
from .EvapoGIS_dialog import EvapoGISDialog

class EvapoGIS:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = 'EvapoGIS'
        self.toolbar = self.iface.addToolBar('EvapoGIS')
        self.toolbar.setObjectName('EvapoGIS')
 
    def initGui(self):
        icon_path = ':/resources/icon.png'  # Caminho conforme prefixo no resources.qrc
        self.add_action(
            icon_path,
            text='EvapoGIS',
            callback=self.run,
            parent=self.iface.mainWindow()
        )
 
    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu('EvapoGIS', action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar
 
    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None
    ):
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        if add_to_toolbar:
            self.toolbar.addAction(action)
        if add_to_menu:
            self.iface.addPluginToMenu('EvapoGIS', action)
        self.actions.append(action)
        return action
 
    def run(self):
        self.dlg = EvapoGISDialog()
        self.dlg.show()