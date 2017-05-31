import sys

from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import QString, SIGNAL
from PyQt4.QtGui import QTableWidgetItem, QTableWidget, QTextEdit, QLineEdit

from LC3main import to_hex_string
from LC3main import to_bin_string
import LC3main

import instruction_parser as parser
from storage import Registers
from storage import *


class Window(QtGui.QMainWindow):
    def __init__(self):
        super(Window, self).__init__()
        self.setGeometry(100, 100, 1000, 1000)
        self.setWindowTitle("LC3 Simulator")
        # self.setWindowIcon(QtGui.Icon('logo.png'))
        self.setupFileMenu()
        self.console = Console()
        self.console_thread = None
        self.worker = RunHandler(self)

        self.mem_table = MemoryTable(65536, 5)
        self.reg_table = RegisterTable(4, 3)
        self.search_bar = SearchBar(self.mem_table)
        self.buttons = ButtonRow(self)
        self.grid = QtGui.QGridLayout()

        self.home()

    def __del__(self):
        # Restore sys.stdout
        sys.stdout = sys.__stdout__

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
        loadProgramAction.triggered.connect(self.load_program)

        reinitializeAction = QtGui.QAction("&Reinitialize machine", self)
        reinitializeAction.setShortcut("Ctrl+R")
        reinitializeAction.setStatusTip('Clear the machine except for the operating system')
        reinitializeAction.triggered.connect(self.reinitialize_machine)

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
        runAction.triggered.connect(lambda: self.run(False))

        self.statusBar()

        mainMenu = self.menuBar()
        fileMenu = mainMenu.addMenu('&File')
        fileMenu.addAction(loadProgramAction)
        fileMenu.addAction(reinitializeAction)
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
    def updateSimTables(self):
        self.reg_table.setData()

    def load_program(self):
        self.file_diag = FileDialog()
        self.file_diag.file_open(self)

    def clear_console(self):
        self.console.clear()

    def reinitialize_machine(self):
        memory.load_os("operating_sys_lc3.txt", 65536)
        self.mem_table.setData()

    @staticmethod
    def exit_app():
        sys.exit(0)

    @staticmethod
    def suspend_process():
        self.mem_table.verticalScrollBar().setValue(registers.PC)
        memory.paused = True

    def set_pc(self):
        row = int(to_hex_string(registers.PC)[1:], 16)
        self.mem_table.item(row, 0).setBackground(QtGui.QColor(240, 240, 240))

        index = self.mem_table.selectedIndexes()[0]
        registers.PC = index.row()

        row = int(to_hex_string(registers.PC)[1:], 16)
        self.mem_table.item(row, 0).setBackground(QtGui.QColor(110, 120, 255))
        self.reg_table.setData()
        self.mem_table.setFocus()

    def on_data_ready(self, data):
        self.appendText(data)

    def run(self, step):
        self.thread = QtCore.QThread()
        self.console_thread = self.thread
        self.worker = RunHandler(self)

        self.worker.moveToThread(self.thread)
        self.worker.finished.connect(self.thread.quit)
        self.worker.update_regs.connect(self.updateSimTables)
        self.worker.updated.connect(self.appendText)

        if not step:
            self.thread.started.connect(self.worker.run_app)
        else:
            self.thread.started.connect(self.worker.step_app)

        self.thread.finished.connect(self.thread.quit)
        self.thread.start()

class Console(QTextEdit):
    def __init__(self):
        super(QTextEdit, self).__init__()
        self.setReadOnly(True)
        self.current_key = None
        font = QtGui.QFont()
        font.setPointSize(10)
        self.setFont(font)

    def keyPressEvent(self, event):
        if isinstance(event, QtGui.QKeyEvent):
            key = ord(str(event.text()))
            KBSR = -512  # 0xFE00
            KBDR = -510  # 0xFE02
            memory[KBSR] = 0x8000
            if key == 0x0D:
                key = 0x0A
            memory[KBDR] = key
        QTextEdit.keyPressEvent(self, event)

class RunHandler(QtCore.QObject):

    # Below are all signals associated with this worker

    finished = QtCore.pyqtSignal()
    updated = QtCore.pyqtSignal(str)
    update_regs = QtCore.pyqtSignal(Registers)
    get_key = QtCore.pyqtSignal(int)
    started = QtCore.pyqtSignal()
    force_stop = QtCore.pyqtSignal()

    def __init__(self, main,):
        super(QtCore.QObject, self).__init__()
        self.main = main
        self.is_running = False

    def run_app(self):
        row = int(to_hex_string(registers.PC)[1:], 16)
        self.main.mem_table.item(row, 0).setBackground(QtGui.QColor(240, 240, 240))
        LC3main.run_instructions(self)
        self.emit_done()

    def step_app(self):
        row = int(to_hex_string(registers.PC)[1:], 16)
        self.main.mem_table.item(row, 0).setBackground(QtGui.QColor(240, 240, 240))
        LC3main.step_instruction(self)
        self.emit_done()

    @QtCore.pyqtSlot()
    def emit_done(self):
        self.finished.emit()

    @QtCore.pyqtSlot(Registers)
    def sendRegTable(self):
        self.update_regs.emit(registers)
        row = int(to_hex_string(registers.PC)[1:], 16)
        self.main.mem_table.item(row, 0).setBackground(QtGui.QColor(110, 120, 255))

    @QtCore.pyqtSlot(str)
    def sendAppend(self, char):
        self.updated.emit(char)


class RegisterTable(QTableWidget):
    def __init__(self, *args):
        QTableWidget.__init__(self, *args)
        self.setData()
        self.setRowHeight(0, 29)
        self.setRowHeight(1, 29)
        self.setRowHeight(2, 30)
        self.setRowHeight(3, 30)
        self.setColumnWidth(0, 161)
        self.setColumnWidth(1, 161)
        self.setColumnWidth(2, 162)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setVisible(False)

    def setData(self):
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
    def __init__(self, *args):
        QTableWidget.__init__(self, *args)
        self.setData()
        self.setColumnWidth(0, 40)
        self.setColumnWidth(1, 50)
        self.setColumnWidth(2, 163)
        self.setColumnWidth(3, 70)
        self.setColumnWidth(4, 140)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setVisible(False)
        self.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)

    def setData(self):
        for row in range(self.rowCount()):
            inst = memory.memory[row]
            inst_bin = to_bin_string(inst)
            inst_hex = to_hex_string(inst)

            self.setItem(row, 0, QtGui.QTableWidgetItem())
            self.item(row, 0).setBackground(QtGui.QColor(240, 240, 240))
            if row == registers.PC:
                self.item(row, 0).setBackground(QtGui.QColor(110, 120, 255))

            self.setItem(row, 1, QTableWidgetItem(QString(to_hex_string(row))))
            self.setItem(row, 2, QTableWidgetItem(QString(inst_bin)))
            self.setItem(row, 3, QTableWidgetItem(QString(inst_hex)))
            inst_list = parser.parse_any(inst)
            self.setItem(row, 4, QTableWidgetItem(QString(', '.join(str(e) for e in inst_list))))

    def setDataRange(self, start, stop):
        for row in range(start, stop, 1):
            inst = memory.memory[row]
            inst_bin = to_bin_string(inst)
            inst_hex = to_hex_string(inst)

            self.setItem(row, 0, QtGui.QTableWidgetItem())
            self.item(row, 0).setBackground(QtGui.QColor(240, 240, 240))

            if row == registers.PC:
                self.item(row, 0).setBackground(QtGui.QColor(110, 120, 255))

            self.setItem(row, 1, QTableWidgetItem(QString(to_hex_string(row))))
            self.setItem(row, 2, QTableWidgetItem(QString(inst_bin)))
            self.setItem(row, 3, QTableWidgetItem(QString(inst_hex)))
            inst_list = parser.parse_any(inst)
            self.setItem(row, 4, QTableWidgetItem(QString(', '.join(str(e) for e in inst_list))))


class FileDialog(QtGui.QFileDialog):
    def file_open(self, main):
        name = QtGui.QFileDialog.getOpenFileName(self, 'Open File')

        main.mem_table.setItem(registers.PC, 0, QtGui.QTableWidgetItem())
        main.mem_table.item(registers.PC, 0).setBackground(QtGui.QColor(240, 240, 240))

        interval = memory.load_instructions(name)

        main.mem_table.setDataRange(interval[0], interval[1])
        main.mem_table.verticalScrollBar().setValue(interval[0])

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
    def __init__(self, window, *args):
        QtGui.QWidget.__init__(self, *args)
        self.grid = QtGui.QGridLayout()
        self.run_button = QtGui.QPushButton('Run', self)
        self.run_button.setMinimumHeight(40)
        self.run_button.clicked.connect(lambda: window.run(False))

        self.step_button = QtGui.QPushButton('Step', self)
        self.step_button.setMinimumHeight(40)
        self.step_button.clicked.connect(lambda: window.run(True))

        self.stop_button = QtGui.QPushButton('Stop', self)
        self.stop_button.setMinimumHeight(40)
        self.stop_button.clicked.connect(window.suspend_process)

        self.pc_button = QtGui.QPushButton('Set PC', self)
        self.pc_button.setMinimumHeight(40)
        self.pc_button.clicked.connect(window.set_pc)

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
