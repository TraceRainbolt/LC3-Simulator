import sys

from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt
from PyQt4.QtCore import QString, SIGNAL
from PyQt4.QtGui import QTableWidgetItem, QTableWidget, QTextEdit, QLineEdit

from lc3_logic import to_hex_string
from lc3_logic import to_bin_string
import lc3_logic

import instruction_parser as parser
from storage import Registers
from storage import *


KBSR = -512  # 0xFE00
KBDR = -510  # 0xFE02
DSR = -508  # 0xFE04
DDR = -506  # 0xFE06
MCR = -2  # 0xFFFE

default_origin = 0x3000

bit_mask = 0xFFFF  # bit mask to 'convert' signed int to unsigned, 0xFFFF = 16 bit

pc_color = QtGui.QColor(10, 206, 101)
default_color = QtGui.QColor(240, 240, 240)

class Window(QtGui.QMainWindow):
    def __init__(self):
        super(Window, self).__init__()
        self.thread = QtCore.QThread()
        self.file_dialog = FileDialog()
        self.setGeometry(100, 100, 1000, 1000)
        self.setWindowTitle("LC3 Simulator")
        self.setWindowIcon(QtGui.QIcon('LC3_logo.png'))
        self.setupFileMenu()
        self.console = Console(self)
        self.console_thread = None
        self.speed_slider = SpeedSlider(self)
        self.worker = RunHandler(self)

        self.modified_data = []

        self.mem_table = MemoryTable(65536, 5)
        self.reg_table = RegisterTable(4, 3)
        self.search_bar = SearchBar(self.mem_table)
        self.buttons = ButtonRow(self)

        self.grid = QtGui.QGridLayout()

        self.home()
        self.reinitialize_machine()

    def __del__(self):
        # Restore sys.stdout
        sys.stdout = sys.__stdout__

    def home(self):
        # Setup the general layout of the UI
        centralWidget = QtGui.QWidget()

        self.grid.addWidget(self.reg_table, 0, 0)
        self.grid.addWidget(self.buttons, 1, 0)
        self.grid.addWidget(self.search_bar, 2, 0)
        self.grid.addWidget(self.mem_table, 3, 0)
        # self.grid.addWidget(self.speed_slider, 0, 1)
        self.grid.addWidget(self.console, 3, 1)
        self.grid.setRowStretch(0, 3)
        self.grid.setRowStretch(1, 1)
        self.grid.setRowStretch(2, 1)
        self.grid.setRowStretch(3, 17)

        centralWidget.setLayout(self.grid)
        self.setCentralWidget(centralWidget)
        self.show()

    def setupFileMenu(self):
        # Create the actions for the menu bar drop down
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

        stepAction = QtGui.QAction("&Step", self)
        stepAction.setShortcut("Ctrl+T")
        stepAction.setStatusTip('Step one instruction forward from the current PC')
        stepAction.triggered.connect(lambda: self.run(True))

        stopAction = QtGui.QAction("&Stop", self)
        stopAction.setShortcut("Ctrl+P")
        stopAction.setStatusTip('Pause the simulation')
        stopAction.triggered.connect(self.suspend_process)

        # Show the status bar tips
        self.statusBar()

        # File menu setup
        mainMenu = self.menuBar()
        fileMenu = mainMenu.addMenu('&File')
        fileMenu.addAction(loadProgramAction)
        fileMenu.addAction(reinitializeAction)
        fileMenu.addAction(clearConsoleAction)
        fileMenu.addAction(exitAction)

        # Execute menu setup
        executeMenu = mainMenu.addMenu('&Execute')
        executeMenu.addAction(runAction)
        executeMenu.addAction(stepAction)
        executeMenu.addAction(stopAction)

    @QtCore.pyqtSlot(str)
    def append_text(self, text):
        """Append text to the QTextEdit."""
        # Maybe QTextEdit.append() works as well, but this is how I do it:
        cursor = self.console.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.insertText(text)
        self.console.setTextCursor(cursor)
        self.console.ensureCursorVisible()

    # Slot for receiving table updates
    @QtCore.pyqtSlot()
    def update_gui_tables(self):
        self.reg_table.setData()

    # Open the file dialog to select program to load
    def load_program(self):
        self.file_dialog.file_open(self)

    # Clear the console
    def clear_console(self):
        self.console.clear()

    # Reinitialize machine
    def reinitialize_machine(self):
        for i, register in enumerate(registers):
            registers[i] = 0
        self.set_pc(0x3000)
        registers.IR = 0
        registers.CC = 0b010
        registers.PSR = 0x8000 + registers.CC
        self.reg_table.setData()

        memory.load_os()
        for address in memory.modified_data:
            if 0x514 <= address <= 0xFA00:          # If address is not in OS segment of memory, clear it to 0
                self.mem_table.clearData(address)
            else:                                   # Else set it to the correct OS data
                self.mem_table.setDataRange(address, address)
        memory.reset_modified()
        self.console.clear()
        self.console.clear()
        self.mem_table.verticalScrollBar().setValue(registers.PC & bit_mask)


    # Exit the entire application safely
    @staticmethod
    def exit_app():
        sys.exit(0)

    # Used for stopping in the middle of an execution, activated by the STOP button
    def suspend_process(self):
        self.mem_table.verticalScrollBar().setValue(registers.PC & bit_mask)
        memory.paused = True

    # Set the current PC pointer (blue box) to the correct instruction
    # TODO: make methods for moving the PC pointer
    def set_pc(self, place=None):
        row = registers.PC & bit_mask
        self.mem_table.item(row, 0).setBackground(default_color)

        if not place:
            index = self.mem_table.selectedIndexes()[0]
            registers.PC = index.row()
            row = registers.PC & bit_mask
        else:
            row = place
            registers.PC = place

        self.mem_table.item(row, 0).setBackground(pc_color)
        self.reg_table.setData()
        self.mem_table.setFocus()
        self.mem_table.clearSelection()

    def jump_to_pc(self):
        self.mem_table.verticalScrollBar().setValue(registers.PC & bit_mask)

    # Called when ready to append to console
    def on_data_ready(self, data):
        self.append_text(data)

    # This initializes a worker (RunHandler) to take care of moving signals into slots
    # Also starts up thread and makes all proper connections
    def run(self, step):
        memory[MCR] = 0xFFFF
        self.console_thread = self.thread
        self.worker = RunHandler(self)

        self.worker.moveToThread(self.thread)
        self.worker.finished.connect(self.thread.quit)
        self.worker.update_regs.connect(self.update_gui_tables)
        self.worker.updated.connect(self.append_text)

        if not step:
            self.thread.started.connect(self.worker.run_app)
        else:
            self.thread.started.connect(self.worker.step_app)

        self.thread.finished.connect(self.thread.quit)
        self.thread.start()


# Class for the console that the machine prints to
class Console(QTextEdit):
    def __init__(self, main):
        super(QTextEdit, self).__init__()
        self.setReadOnly(True)
        self.current_key = None
        font = QtGui.QFont()
        font.setPointSize(10)
        self.setFont(font)
        self.main = main

    # Override default keyPressEvent, update machine with correct information
    # TODO: enable keyboard interrupts, should be easy now that this is its own thread
    def keyPressEvent(self, event):
        if isinstance(event, QtGui.QKeyEvent):
            key = ord(str(event.text()))
            memory[KBSR] = memory[KBSR] + 0x8000  # Set first bit of KBSR to 1, rest 0
            if key == 0x0D:
                key = 0x0A
            memory[KBDR] = key  # Put key in KBDR
            if (memory[KBSR] >> 14) & 1 == 1:
                self.initiate_service_routine(self.main, 0x80)
        QTextEdit.keyPressEvent(self, event)

    @staticmethod
    def initiate_service_routine(main, vector):
        old_PSR = registers.PSR
        old_PC = registers.PC
        main.mem_table.item(old_PC, 0).setBackground(default_color)

        registers.PSR = registers.PSR & 0x7FFF       # Enter Supervisor Mode
        registers.PSR = registers.PSR | 0x0400       # Set priority level to PL4
        SSP = registers.registers[6]                 # Set SSP to R6
        memory[SSP] = old_PSR                        # Place PSR on top of Supervisor Stack
        registers.registers[6] -= 1                  # Increment stack pointer
        SSP = registers.registers[6]                 # Set SSP again
        memory[SSP] = old_PC                         # Place PC on top of Supervisor Stack
        registers.PC = memory[vector + 0x100] - 1    # Jump to interrupt vector table location (always 0x0180)


# Class for RunHandler, which handles all connections from GUI to logic
# TODO: Rename the variables so that their names make sense
class RunHandler(QtCore.QObject):
    #
    # Below are all signals associated with this worker
    #
    finished = QtCore.pyqtSignal()     # Used when done
    updated = QtCore.pyqtSignal(str)   # Used when console is updated
    update_regs = QtCore.pyqtSignal()  # Used when registers/memory is updated
    started = QtCore.pyqtSignal()      # Used when started

    def __init__(self, main,):
        super(QtCore.QObject, self).__init__()
        self.main = main
        self.is_running = False

    # Start running the the code
    def run_app(self):
        row = registers.PC & bit_mask
        self.main.mem_table.item(row, 0).setBackground(default_color)
        lc3_logic.run_instructions(self)
        self.main.mem_table.verticalScrollBar().setValue(registers.PC & bit_mask)  # If we step, make sure to follow
        self.emit_done()

    # Step through the code
    def step_app(self):
        row = registers.PC & bit_mask
        self.main.mem_table.item(row, 0).setBackground(default_color)
        lc3_logic.step_instruction(self)
        if registers.PC & bit_mask - row > 16:
            self.main.mem_table.verticalScrollBar().setValue(registers.PC & bit_mask)  # If we step, make sure to follow
        self.emit_done()

    # Slot for ending the current instruction run and closing the thread
    @QtCore.pyqtSlot()
    def emit_done(self):
        self.finished.emit()

    # Slot for updating the Register/Memory tables
    @QtCore.pyqtSlot()
    def send_update_gui_tables(self):
        self.update_regs.emit()
        row = registers.PC & bit_mask
        self.main.mem_table.item(row, 0).setBackground(pc_color)

    # Slot for sending output to console
    @QtCore.pyqtSlot(str)
    def send_append_text(self, char):
        self.updated.emit(char)


# Class for the GUI element displaying the Register Table
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

    # Set the visual data to be the same as the underlying registers
    def setData(self):
        reg_num0 = 0
        reg_num1 = 4
        index = 0

        # This basically just makes sure the registers go from 0 to 7 down the columns
        # TODO: make this less weird
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

        # Manually set the rest of the register info
        self.setItem(0, 2, QTableWidgetItem(QString('PC        ' + to_hex_string(registers.PC))))
        self.setItem(1, 2, QTableWidgetItem(QString('IR         ' + to_hex_string(registers.IR))))
        self.setItem(2, 2, QTableWidgetItem(QString('PSR      ' + to_hex_string(registers.PSR))))
        self.setItem(3, 2, QTableWidgetItem(QString('CC        ' + '{:03b}'.format(registers.CC))))

# Class for the memory table GUI element
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

    # Same as register setData, although there might be a way to make this faster
    def setData(self):
        for row in range(self.rowCount()):
            inst = memory.memory[row]
            inst_bin = to_bin_string(inst)
            inst_hex = to_hex_string(inst)

            self.setItem(row, 0, QtGui.QTableWidgetItem())
            self.item(row, 0).setBackground(default_color)
            if row == registers.PC:
                self.item(row, 0).setBackground(pc_color)

            self.setItem(row, 1, QTableWidgetItem(QString(to_hex_string(row))))
            self.setItem(row, 2, QTableWidgetItem(QString(inst_bin)))
            self.setItem(row, 3, QTableWidgetItem(QString(inst_hex)))
            inst_list = parser.parse_any(inst)
            self.setItem(row, 4, QTableWidgetItem(QString(', '.join(str(e) for e in inst_list))))

    # Used when we know the range of the data to update, so that we don't have to update the entire table
    def setDataRange(self, start, stop):
        for row in range(start, stop, 1):
            inst = memory.memory[row]
            inst_bin = to_bin_string(inst)
            inst_hex = to_hex_string(inst)

            self.setItem(row, 0, QtGui.QTableWidgetItem())
            self.item(row, 0).setBackground(default_color)

            if row == registers.PC:
                self.item(row, 0).setBackground(pc_color)

            self.setItem(row, 1, QTableWidgetItem(QString(to_hex_string(row))))
            self.setItem(row, 2, QTableWidgetItem(QString(inst_bin)))
            self.setItem(row, 3, QTableWidgetItem(QString(inst_hex)))
            inst_list = parser.parse_any(inst)
            self.setItem(row, 4, QTableWidgetItem(QString(', '.join(str(e) for e in inst_list))))

    def clearData(self, address):
        self.setItem(address, 2, QTableWidgetItem(QString("0"*16)))
        self.setItem(address, 3, QTableWidgetItem(QString("x0000")))
        self.setItem(address, 4, QTableWidgetItem(QString("NOP")))

# Class for the file dialog
class FileDialog(QtGui.QFileDialog):
    def file_open(self, main):
        self.setNameFilters(["OBJ Files (*.obj)"])
        self.selectNameFilter("OBJ Files (*.obj)")
        file_names = self.getOpenFileNames(self, "Open files")

        # main.mem_table.setItem(registers.PC, 0, QtGui.QTableWidgetItem())

        found_default = False

        if len(file_names) == 0:
            return
        main.mem_table.item(registers.PC, 0).setBackground(default_color)

        for name in file_names:
            interval = memory.load_instructions(name)
            if interval[0] == default_origin:
                found_default = True
            # Interval that we updated, used so that load times are faster
            main.mem_table.setDataRange(interval[0], interval[1])
            main.mem_table.verticalScrollBar().setValue(interval[0])
            main.modified_data.append(interval)

        # In place so that the default_origin (probably 0x3000) is used instead of most recent
        # Only used if at least 1 file is found to start at default_origin
        if found_default:
            main.mem_table.item(registers.PC, 0).setBackground(default_color)
            registers.set_origin(default_origin)
            main.mem_table.item(registers.PC, 0).setBackground(pc_color)
            main.mem_table.verticalScrollBar().setValue(default_origin)


# Class for the search bar
# TODO: add drop-down of recent searches
class SearchBar(QtGui.QLineEdit):
    def __init__(self, mem_table, *args):
        QtGui.QLineEdit.__init__(self, *args)
        self.mem_table = mem_table
        self.connect(self, SIGNAL("returnPressed()"), self.goto_line)

    # Submit the search result and hop to that line
    def goto_line(self):
        line = str(self.text())
        if line[0] == 'x':
            line = line[1:]
        self.mem_table.verticalScrollBar().setValue(int(line, 16))
        self.clear()

# Class for the row of buttons under the register table
class ButtonRow(QtGui.QWidget):
    def __init__(self, window, *args):
        QtGui.QWidget.__init__(self, *args)
        # Set layout to grid, then add all the buttons and their functions
        self.grid = QtGui.QGridLayout()
        self.run_button = QtGui.QPushButton('Run', self)
        self.run_button.setMaximumSize(70, 120)
        self.run_button.clicked.connect(lambda: window.run(False))

        self.step_button = QtGui.QPushButton('Step', self)
        self.step_button.setMaximumSize(70, 120)
        self.step_button.clicked.connect(lambda: window.run(True))

        self.step_over_button = QtGui.QPushButton('Step Over', self)
        self.step_over_button.setMaximumSize(70, 120)
        self.step_over_button.clicked.connect(lambda: window.run(True))

        self.stop_button = QtGui.QPushButton('Stop', self)
        self.stop_button.setMaximumSize(70, 120)
        self.stop_button.clicked.connect(window.suspend_process)

        self.pc_button = QtGui.QPushButton('Set PC', self)
        self.pc_button.setMaximumSize(70, 120)
        self.pc_button.clicked.connect(window.set_pc)

        self.jump_button = QtGui.QPushButton('Go to PC', self)
        self.jump_button.setMaximumSize(70, 120)
        self.jump_button.clicked.connect(window.jump_to_pc)

        self.list_buttons()

    # Put the buttons in the GUI
    def list_buttons(self):
        self.grid.addWidget(self.run_button, 0, 0)
        self.grid.addWidget(self.step_button, 0, 1)
        self.grid.addWidget(self.step_over_button, 0, 2)
        self.grid.addWidget(self.stop_button, 0, 4)
        self.grid.addWidget(self.pc_button, 0, 5)
        self.grid.addWidget(self.jump_button, 0, 6)
        self.setLayout(self.grid)

class SpeedSlider(QtGui.QWidget):
    def __init__(self, window, *args):
        QtGui.QWidget.__init__(self, *args)
        self.grid = QtGui.QGridLayout()

        self.label = QtGui.QLabel("Simulator Speed: ", self)

        self.slider = QtGui.QSlider(Qt.Horizontal, self)
        self.slider.setMinimum(-1)
        self.slider.setMaximum(101)
        self.slider.setValue(0)
        self.slider.setTickPosition(QtGui.QSlider.TicksBelow)
        self.slider.setTickInterval(10)
        self.slider.setMinimumWidth(200)
        self.slider.sliderMoved.connect(self.handle_move)

        self.speed = QtGui.QLabel(str(self.slider.value()), self)

        self.place_slider()

    def place_slider(self):
        self.grid.addWidget(self.label, 0, 0)
        self.grid.addWidget(self.slider, 0, 1)
        self.grid.addWidget(self.speed, 0, 2)
        self.setLayout(self.grid)

    def handle_move(self):
        self.speed.setText(str(self.slider.value()))
        memory.speed = self.slider.value()


# Found this on SO, it works so I leave it
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
