import sys

from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import QString, SIGNAL
from PyQt4.QtGui import QTableWidgetItem, QTableWidget, QTextEdit, QLineEdit

from LC3main import to_hex_string
from LC3main import to_bin_string
import LC3main

import instruction_parser as parser
from storage import Registers


class Window(QtGui.QMainWindow):
    def __init__(self, memory, registers):
        super(Window, self).__init__()
        self.setGeometry(100, 100, 1000, 1000)
        self.setWindowTitle("LC3 Simulator")
        # self.setWindowIcon(QtGui.Icon('logo.png'))
        self.setupFileMenu()
        self.console = Console()
        self.console_thread = None
        self.worker = None

        self.mem_table = MemoryTable(memory, 65536, 5)
        self.reg_table = RegisterTable(registers, 4, 3)
        self.buttons = ButtonRow()
        self.grid = QtGui.QGridLayout()
        self.search_bar = SearchBar(self.mem_table)

        self.home()

    def __del__(self):
        # Restore sys.stdout
        sys.stdout = sys.__stdout__

    def run(self):
        RunHandler.run_app(self)

    def home(self):
        centralWidget = QtGui.QWidget()

        self.grid.addWidget(self.reg_table, 0, 0)
        self.grid.addWidget(self.buttons, 1, 0)
        self.grid.addWidget(self.search_bar, 2, 0)
        self.grid.addWidget(self.mem_table, 3, 0)
        self.grid.addWidget(self.console, 3, 1)
        self.grid.setRowStretch(0, 3)
        self.grid.setRowStretch(1, 1)
        self.grid.setRowStretch(2, 1)
        self.grid.setRowStretch(3, 17)

        centralWidget.setLayout(self.grid)
        self.setCentralWidget(centralWidget)

        self.show()

    def setupFileMenu(self):
        loadProgramAction = QtGui.QAction("&Load Program", self)
        loadProgramAction.setShortcut("Ctrl+O")
        loadProgramAction.setStatusTip('Load a .obj file into the simulator')
        loadProgramAction.triggered.connect(self.load_program) \

        clearConsoleAction = QtGui.QAction("&Clear Console", self)
        clearConsoleAction.setShortcut("Ctrl+D")
        clearConsoleAction.setStatusTip('Clear the output of the console')
        clearConsoleAction.triggered.connect(self.clear_console)

        exitAction = QtGui.QAction("&Exit Simulator", self)
        exitAction.setShortcut("Ctrl+Q")
        exitAction.setStatusTip('Exit out of the simulator')
        exitAction.triggered.connect(self.exit_app)

        runAction = QtGui.QAction("&Run", self)
        runAction.setShortcut("Ctrl+R")
        runAction.setStatusTip('Run the simulation from the current PC')
        runAction.triggered.connect(self.run)

        self.statusBar()

        mainMenu = self.menuBar()
        fileMenu = mainMenu.addMenu('&File')
        fileMenu.addAction(loadProgramAction)
        fileMenu.addAction(clearConsoleAction)
        fileMenu.addAction(exitAction)

        executeMenu = mainMenu.addMenu('&Execute')
        executeMenu.addAction(runAction)

    @QtCore.pyqtSlot(str)
    def appendText(self, text):
        """Append text to the QTextEdit."""
        # Maybe QTextEdit.append() works as well, but this is how I do it:
        cursor = self.console.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.insertText(text)
        self.console.setTextCursor(cursor)
        self.console.ensureCursorVisible()

    @QtCore.pyqtSlot(Registers)
    def updateRegTable(self, registers):
        self.regTable.setData(registers)

    def load_program(self):
        self.file_diag = FileDialog()
        self.file_diag.file_open()

    def clear_console(self):
        self.console.clear()

    @staticmethod
    def exit_app():
        sys.exit(0)

    def on_data_ready(self, data):
        self.appendText(data)

    def run(self):
        thread = QtCore.QThread()
        self.console_thread = thread
        self.worker = RunHandler(self)

        self.worker.moveToThread(thread)
        self.worker.finished.connect(thread.quit)
        self.worker.update_regs.connect(self.updateRegTable)
        self.worker.updated.connect(self.appendText)
        self.worker.getkey.connect(LC3main.kbhit)

        thread.started.connect(self.worker.run_app)
        thread.finished.connect(self.exit_app)

        thread.start()

        #self.console_thread = QtCore.QMetaObject.invokeMethod(self.worker, 'run_app', Qt.QueuedConnection)

class Console(QTextEdit):

    def __init__(self):
        super(QTextEdit, self).__init__()
        self.setReadOnly(True)
        self.current_key = None

    def keyPressEvent(self, event):
        key = None
        if isinstance(event, QtGui.QKeyEvent):
            key = ord(str(event.text()))
            self.current_key = key
        QTextEdit.keyPressEvent(self, event)

class RunHandler(QtCore.QObject):
    finished = QtCore.pyqtSignal()
    updated = QtCore.pyqtSignal(str)
    update_regs = QtCore.pyqtSignal(Registers)
    getkey = QtCore.pyqtSignal(int)
    started = QtCore.pyqtSignal()

    def __init__(self, main):
        super(QtCore.QObject, self).__init__()
        self.main = main

    def run_app(self):
        LC3main.run_instructions(self)

    @QtCore.pyqtSlot(Registers)
    def sendRegTable(self, registers):
        self.update_regs.emit(registers)

    @QtCore.pyqtSlot(str)
    def sendAppend(self, char):
        self.updated.emit(char)

    @QtCore.pyqtSlot()
    def sendKey(self):
        key = self.main.console.current_key
        if key:
            self.main.console.current_key = None
            self.getkey.emit(key)


class RegisterTable(QTableWidget):
    def __init__(self, registers, *args):
        QTableWidget.__init__(self, *args)
        self.setData(registers)
        self.setRowHeight(0, 29)
        self.setRowHeight(1, 29)
        self.setRowHeight(2, 30)
        self.setRowHeight(3, 30)
        self.setColumnWidth(0, 161)
        self.setColumnWidth(1, 161)
        self.setColumnWidth(2, 162)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setVisible(False)

    def setData(self, registers):
        reg_num0 = 0
        reg_num1 = 4
        index = 0
        for row in range(self.rowCount()):
            for col in range(self.columnCount()):
                if index % 3 < 2:
                    if index % 3 == 0:
                        reg_info = 'R' + str(reg_num0) + '      ' + to_hex_string(
                            registers[reg_num0]) + '     ' + str(registers[reg_num0])
                        reg_num0 += 1
                    else:
                        reg_info = 'R' + str(reg_num1) + '      ' + to_hex_string(
                            registers[reg_num1]) + '     ' + str(registers[reg_num1])
                        reg_num1 += 1
                    self.setItem(row, col, QTableWidgetItem(QString(reg_info)))
                index += 1

        self.setItem(0, 2, QTableWidgetItem(QString('PC        ' + to_hex_string(registers.PC))))
        self.setItem(1, 2, QTableWidgetItem(QString('IR         ' + to_hex_string(registers.IR))))
        self.setItem(2, 2, QTableWidgetItem(QString('PSR      ' + to_hex_string(registers.PSR))))
        self.setItem(3, 2, QTableWidgetItem(QString('CC        ' + '{:03b}'.format(registers.CC))))


class MemoryTable(QTableWidget):
    def __init__(self, memory, *args):
        QTableWidget.__init__(self, *args)
        self.setData(memory)
        self.setColumnWidth(0, 40)
        self.setColumnWidth(1, 50)
        self.setColumnWidth(2, 163)
        self.setColumnWidth(3, 70)
        self.setColumnWidth(4, 140)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setVisible(False)

    def setData(self, memory):
        for row in range(self.rowCount()):
            self.setItem(row, 0, QtGui.QTableWidgetItem())
            self.item(row, 0).setBackground(QtGui.QColor(240, 240, 240))

            # self.item.setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)

            self.setItem(row, 1, QTableWidgetItem(QString(to_hex_string(row))))

            inst = memory.memory[row]
            inst_bin = to_bin_string(inst)
            inst_hex = to_hex_string(inst)

            self.setItem(row, 2, QTableWidgetItem(QString(inst_bin)))
            self.setItem(row, 3, QTableWidgetItem(QString(inst_hex)))

            inst_list = parser.parse_any(inst)
            self.setItem(row, 4, QTableWidgetItem(QString(', '.join(str(e) for e in inst_list))))


class FileDialog(QtGui.QFileDialog):
    def file_open(self):
        name = QtGui.QFileDialog.getOpenFileName(self, 'Open File')
        f = open(name, 'r')

        # TODO: read file

class SearchBar(QtGui.QLineEdit):
    def __init__(self, mem_table, *args):
        QtGui.QLineEdit.__init__(self, *args)
        self.mem_table = mem_table
        self.connect(self, SIGNAL("returnPressed()"), self.goto_line)

    def goto_line(self):
        line = str(self.text())
        if line[0] == 'x':
            line = line[1:]
        self.mem_table.verticalScrollBar().setValue(int(line, 16))
        self.clear()


class ButtonRow(QtGui.QWidget):
    def __init__(self, *args):
        QtGui.QWidget.__init__(self, *args)
        self.grid = QtGui.QGridLayout()
        self.run_button = QtGui.QPushButton('Run', self)
        self.run_button.setMinimumHeight(40)

        self.step_button = QtGui.QPushButton('Step', self)
        self.step_button.setMinimumHeight(40)

        self.stop_button = QtGui.QPushButton('Stop', self)
        self.stop_button.setMinimumHeight(40)

        self.pc_button = QtGui.QPushButton('Set PC', self)
        self.pc_button.setMinimumHeight(40)

        self.list_buttons()

    def list_buttons(self):
        self.grid.addWidget(self.run_button, 0, 0)
        self.grid.addWidget(self.step_button, 0, 1)
        self.grid.addWidget(self.stop_button, 0, 2)
        self.grid.addWidget(self.pc_button, 0, 3)
        self.setLayout(self.grid)



class Thread(QtCore.QThread):
    """Need for PyQt4 <= 4.6 only"""
    def __init__(self, parent=None):
        QtCore.QThread.__init__(self, parent)

     # this class is solely needed for these two methods, there
     # appears to be a bug in PyQt 4.6 that requires you to
     # explicitly call run and start from the subclass in order
     # to get the thread to actually start an event loop

    def start(self):
        QtCore.QThread.start(self)

    def run(self):
        QtCore.QThread.run(self)
