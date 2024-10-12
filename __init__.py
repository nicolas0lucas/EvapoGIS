from .resources import *
import os

def classFactory(iface):
    from .EvapoGIS import EvapoGIS
    return EvapoGIS(iface)

class EvapoGIS:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)

    def initGui(self):
        icon_path = ':/plugins/EvapoGIS/icon.png'
        self.add_action(
            icon_path,
            text='EvapoGIS',
        )

