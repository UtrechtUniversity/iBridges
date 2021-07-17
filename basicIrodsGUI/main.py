import os
from pathlib import Path
import sys
from cryptography.fernet import Fernet
import subprocess

from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QDialog, QApplication
from PyQt5.uic import loadUi
from PyQt5 import QtCore
from PyQt5 import QtGui

from irodsConnector import irodsConnector
from irodsConnectorIcommands import irodsConnectorIcommands
from irods.exception import CAT_INVALID_AUTHENTICATION

class irodsLogin(QDialog):
    def __init__(self):
        super(irodsLogin, self).__init__()
        loadUi("irodsLogin.ui", self)
        self.selectIcommandsButton.toggled.connect(self.setupIcommands)
        self.standardButton.toggled.connect(self.setupStandard)
        self.connectButton.clicked.connect(self.loginfunction)
        self.passwordField.setEchoMode(QtWidgets.QLineEdit.Password)
        self.icommands = False

    def __encryption(self):
        salt = Fernet.generate_key()
        return Fernet(salt)
    
    def __irodsLogin(self, envFile, password, cipher):
        if self.icommands:
            ic = irodsConnectorIcommands(cipher.decrypt(password).decode())
        else:
            ic = irodsConnector(envFile, cipher.decrypt(password).decode())
        return ic

    def setupStandard(self):
        if self.standardButton.isChecked():
            self.envFileField.setEnabled(True)

    def setupIcommands(self):
        if self.selectIcommandsButton.isChecked():
            icommandsExist = False
            self.icommandsError.setText("")
            try:
                print("setupIcommands")
                icommandsExist = subprocess.call(["which", "iinit"]) == 0
                if icommandsExist == False:
                    self.icommandsError.setText("ERROR: no icommands installed")
                    self.standardButton.setChecked(True)
                else:
                    self.envFileField.setText(os.environ['HOME']+"/.irods/irods_environment.json")
                    self.envFileField.setEnabled(False)
                    self.icommands = True
            except Exception:
                self.icommandsError.setText("ERROR: no icommands installed")
                self.standardButton.setChecked(True)
    
    def loginfunction(self):
        cipher = self.__encryption()
        envFile = self.envFileField.text()
        password = cipher.encrypt(bytes(self.passwordField.text(), 'utf-8'))
        self.passError.setText("")
        self.envError.setText("")
        try:
            ic = self.__irodsLogin(envFile, password, cipher)
            browser = irodsBrowser(ic)
            widget.addWidget(browser)
            widget.setCurrentIndex(widget.currentIndex()+1)
        except CAT_INVALID_AUTHENTICATION:
            self.passError.setText("ERROR: Wrong password.")
        except ConnectionRefusedError:
            self.passError.setText("ERROR: Wrong password.")
        except FileNotFoundError:
            self.envError.setText("ERROR: iRODS environment file not found.")


class irodsBrowser(QDialog):
    def __init__(self, ic):
        super(irodsBrowser, self).__init__()
        loadUi("irodsBrowser.ui", self)
        self.ic = ic

        #Main widget --> browser
        self.irodsRoot = self.ic.session.collections.get("/"+ic.session.zone+"/home")
        self.collTable.setColumnWidth(0,399)
        self.collTable.setColumnWidth(1,199)
        self.collTable.setColumnWidth(2,399)
        self.collTable.setColumnWidth(3,199)
        self.collTable.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.collTable.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.resetPath() 

        #Home button
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("home.png"))
        self.homeButton.setIcon(icon)

        #Metadata table
        self.metadataTable.setColumnWidth(0,199)
        self.metadataTable.setColumnWidth(1,199)
        self.metadataTable.setColumnWidth(2,199)
        self.metadataTable.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.metadataTable.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.metadataTable.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        #ACL table
        self.aclTable.setColumnWidth(0,299)
        self.aclTable.setColumnWidth(1,299)
        self.aclTable.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.aclTable.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.metadataTable.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        #Resource table
        self.resourceTable.setColumnWidth(0,500)
        self.resourceTable.setColumnWidth(1,90)
        self.resourceTable.setEditTriggers(
                QtWidgets.QAbstractItemView.NoEditTriggers)
        self.resourceTable.setSelectionMode(
                QtWidgets.QAbstractItemView.SingleSelection)

        self.browse()

    def browse(self):
        self.pathInput.returnPressed.connect(self.loadTable)
        self.homeButton.clicked.connect(self.resetPath)
        self.collTable.doubleClicked.connect(self.updatePath)
        self.collTable.clicked.connect(self.fillInfo)


    def resetPath(self):
        self.pathInput.setText(self.irodsRoot.path)
        self.loadTable()


    @QtCore.pyqtSlot(QtCore.QModelIndex)
    def fillInfo(self, index):
        self.previewBrowser.clear()
        self.metadataTable.setRowCount(0);
        self.aclTable.setRowCount(0);
        self.resourceTable.setRowCount(0);
        col = index.column()
        row = index.row()
        value = self.collTable.item(row, col).text()
        if col == 0:
            self.__fillPreview(value)
            self.__fillMetadata(value)
            self.__fillACLs(value)
            self.__fillResc(value)

    def __fillResc(self, value):
        if not value.endswith("/"):
            resources = self.ic.listResources()
            self.resourceTable.setRowCount(len(resources))
            obj = self.ic.session.data_objects.get(
                    "/"+self.pathInput.text().strip("/")+"/"+value.strip("/")
                    )
            replicas = [resc.resource_name for resc in obj.replicas]
            for i in range(len(resources)):
                self.resourceTable.setItem(i, 0, 
                        QtWidgets.QTableWidgetItem(resources[i]))
                if resources[i] in replicas:
                    item = QtWidgets.QTableWidgetItem()
                    item.setCheckState(QtCore.Qt.Checked)
                    item.setFlags(QtCore.Qt.ItemIsEnabled)
                    self.resourceTable.setItem(i, 1, item)


    def __fillACLs(self, value):
        if value.endswith("/"):
            item = self.ic.session.collections.get(
                        "/"+self.pathInput.text().strip("/")+"/"+value.strip("/")
                        )
        else:
            item = self.ic.session.data_objects.get(
                    "/"+self.pathInput.text().strip("/")+"/"+value.strip("/")
                    )
        self.aclTable.setRowCount(len(self.ic.session.permissions.get(item)))
        row = 0
        for acl in self.ic.session.permissions.get(item):
            self.aclTable.setItem(row, 0,
                        QtWidgets.QTableWidgetItem(acl.user_name))
            self.aclTable.setItem(row, 1,
                        QtWidgets.QTableWidgetItem(acl.access_name))
            row = row+1


    def __fillMetadata(self, value):
        if value.endswith("/"):
            coll = self.ic.session.collections.get(
                        "/"+self.pathInput.text().strip("/")+"/"+value.strip("/")
                        )
            metadata = coll.metadata.items()
        else:
            obj = self.ic.session.data_objects.get(
                    "/"+self.pathInput.text().strip("/")+"/"+value.strip("/")
                    )
            metadata = obj.metadata.items()
        self.metadataTable.setRowCount(len(metadata))
        row = 0
        for item in metadata:
            self.metadataTable.setItem(row, 0,
                    QtWidgets.QTableWidgetItem(item.name))
            self.metadataTable.setItem(row, 1,
                    QtWidgets.QTableWidgetItem(item.value))
            self.metadataTable.setItem(row, 2,
                    QtWidgets.QTableWidgetItem(item.units))
            row = row+1


    def __fillPreview(self, value):
        if value.endswith("/"): # collection
            coll = self.ic.session.collections.get(
                        "/"+self.pathInput.text().strip("/")+"/"+value.strip("/")
                        )
            content = [c.name+'/' for c in coll.subcollections] + \
                      [o.name for o in coll.data_objects]

            previewString = '\n'.join(content)
            self.previewBrowser.append(previewString)
        else: # object
            # get mimetype
            mimetype = value.split(".")[len(value.split("."))-1]
            if mimetype in ['txt', 'json', 'csv']:
                obj = self.ic.session.data_objects.get(
                        "/"+self.pathInput.text().strip("/")+"/"+value.strip("/")
                        )
                with obj.open('r') as readObj:
                    out = readObj.readlines()
                previewString = ''.join([line.decode('utf-8') for line in out][:20])
                self.previewBrowser.append(previewString)
                
    
    @QtCore.pyqtSlot(QtCore.QModelIndex)
    def updatePath(self, index):
        col = index.column()
        row = index.row()
        parent = self.pathInput.text()
        if col == 0:
            value = self.collTable.item(row, col).text()
            if value.endswith("/"): #collection
                self.pathInput.setText("/"+parent.strip("/")+"/"+value.strip("/"))
                self.loadTable()

    def loadTable(self):
        coll = self.ic.session.collections.get("/"+self.pathInput.text().strip("/"))
        self.collTable.setRowCount(len(coll.data_objects)+len(coll.subcollections))
        row = 0
        for subcoll in coll.subcollections:
            self.collTable.setItem(row, 0, QtWidgets.QTableWidgetItem(subcoll.name+"/"))
            self.collTable.setItem(row, 1, QtWidgets.QTableWidgetItem(""))
            self.collTable.setItem(row, 2, QtWidgets.QTableWidgetItem(""))
            self.collTable.setItem(row, 3, QtWidgets.QTableWidgetItem(""))
            row = row+1
        for obj in coll.data_objects:
            self.collTable.setItem(row, 0, QtWidgets.QTableWidgetItem(obj.name))
            self.collTable.setItem(row, 1, QtWidgets.QTableWidgetItem(str(obj.size)))
            self.collTable.setItem(row, 2, QtWidgets.QTableWidgetItem(str(obj.checksum)))
            self.collTable.setItem(row, 3, QtWidgets.QTableWidgetItem(""))
            row = row+1

if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWindow = irodsLogin()
    widget = QtWidgets.QStackedWidget()
    widget.addWidget(mainWindow)
    #widget.setFixedHeight(300)
    #widget.setFixedWidth()
    widget.show()
    app.exec_()