from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QDialog
from PyQt5.uic import loadUi
from PyQt5 import QtCore
from PyQt5 import QtGui

import sys

class irodsCreateCollection(QDialog):
    def __init__(self, parent, ic):
        super(irodsCreateCollection, self).__init__()
        loadUi("ui-files/createCollection.ui", self)
        self.setWindowTitle("Create iRODS collection")
        self.ic = ic
        self.parent = parent
        self.label.setText(self.parent+"/")
        self.buttonBox.accepted.connect(self.accept)

    def accept(self):
        if self.collPathLine.text() != "":
            newCollPath = self.parent+"/"+self.collPathLine.text()
            try:
                self.ic.ensureColl(newCollPath)
                self.done(1)
            except Exception as error:
                if hasattr(error, 'message'):
                    self.errorLabel.setText(error.message)
                else:
                    self.errorLabel.setText("ERROR: insufficient rights.")


class irodsIndexPopup(QDialog):
    def __init__(self, irodsTarIndexFileList, tarFilePath, statusLabel):
        super(irodsIndexPopup, self).__init__()
        loadUi("ui-files/irodsIndexPopup.ui", self)
        self.setWindowTitle("iRODS Tar/Zip index.")
        self.indexLabel.setText("Index of " + tarFilePath + ":")
        self.closeButton.clicked.connect(self.closeWindow)
        self.textBrowser.clear()
        self.statusLabel = statusLabel
        for line in irodsTarIndexFileList:
            self.textBrowser.append(line)

    def closeWindow(self):
        self.statusLabel.clear()
        self.close()
