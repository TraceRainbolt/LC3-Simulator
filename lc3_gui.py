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

from queue import *

KBSR = -512  # 0xFE00
KBDR = -510  # 0xFE02
DSR = -508  # 0xFE04
DDR = -506  # 0xFE06
MCR = -2  # 0xFFFE

default_origin = 0x3000

bit_mask = 0xFFFF  # bit mask to 'convert' signed int to unsigned, 0xFFFF = 16 bit

pc_color = QtGui.QColor(10, 206, 101)
breakpoint_color = QtGui.QColor(249, 14, 69)
default_color = QtGui.QColor(240, 240, 240)

key_queue = Queue(maxsize=100)

class Window(QtGui.QMainWindow):
    def __init__(self):
        super(Window, self).__init__()
        self.thread = QtCore.QThread()
        self.file_dialog = FileDialog()
        self.setGeometry(100, 100, 1100, 950)
        self.setWindowTitle("LC3 Simulator")
        self.setWindowIcon(QtGui.QIcon('LC3_logo.png'))
        self.setupFileMenu()
        self.console = Console(self)
        self.console_thread = None
        # self.speed_slider = SpeedSlider(self)
        self.worker = RunHandler(self)
        self.modified_data = []
        self.labeled_addresses = {}

        self.mem_table = None
        # TODO: make this faster
        self.mem_table = MemoryTable(65536, 6)

        self.reg_table = RegisterTable(4, 8)
        self.search_bar = SearchBar(self.mem_table)
        self.buttons = ButtonRow(self)

        self.grid = QtGui.QGridLayout()
        self.right_grid = QtGui.QGridLayout()
        self.left_grid = QtGui.QGridLayout()

        self.home()

        self.reinitialize_machine(True)

    def __del__(self):
        # Restore sys.stdout
        sys.stdout = sys.__stdout__

    def home(self):
        # Setup the general layout of the UI
        centralWidget = QtGui.QWidget()
        rightWidget = QtGui.QWidget()
        leftWidget = QtGui.QWidget()

        self.right_grid.addWidget(self.reg_table, 0, 0)
        self.right_grid.addWidget(self.buttons, 1, 0)
        self.right_grid.addWidget(self.console, 2, 0)
        self.left_grid.addWidget(self.search_bar, 0, 0)
        self.left_grid.addWidget(self.mem_table, 1, 0)

        self.right_grid.setRowStretch(0, 2)
        self.right_grid.setRowStretch(1, 1)
        self.right_grid.setRowStretch(2, 12)

        rightWidget.setLayout(self.right_grid)
        leftWidget.setLayout(self.left_grid)

        self.grid.addWidget(leftWidget, 0, 0)
        self.grid.addWidget(rightWidget, 0, 1)

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

    # Slot for receiving register updates
    @QtCore.pyqtSlot()
    def update_gui_tables(self):
        self.reg_table.setData()
        KBDR_gui = KBDR & bit_mask
        KBSR_gui = KBSR & bit_mask
        self.mem_table.setDataRange(KBDR_gui, KBDR_gui + 1)
        self.mem_table.setDataRange(KBSR_gui, KBSR_gui + 1)

    # Slot for receiving memory updates
    @QtCore.pyqtSlot(int)
    def update_memory_table(self, changed):
        if self.mem_table.item(changed, 0) is not None:
            self.mem_table.setDataRange(changed, changed + 1)

    # Open the file dialog to select program to load
    def load_program(self):
        self.file_dialog.file_open(self)

    # Clear the console
    def clear_console(self):
        self.console.clear()

    # Reinitialize machine
    def reinitialize_machine(self, first_time=False):
        if not first_time:  # Initial time should not suspend process
            self.suspend_process()
            memory.paused = False
        for i, register in enumerate(registers):
            registers[i] = 0
        self.set_pc(0x3000)
        registers.IR = 0
        registers.CC = 0b010
        registers.PSR = 0x8000 + registers.CC
        self.reg_table.setData()

        for row in memory.breakpoints:
            self.mem_table.item(row, 0).setBackground(default_color)

        memory.load_os()
        for address in memory.modified_data:
            if 0x514 <= address <= 0xFA00:  # If address is not in OS segment of memory, clear it to 0
                self.mem_table.clearData(address)
            else:  # Else set it to the correct OS data
                self.mem_table.setDataRange(address, address + 1)
        memory.reset_modified()
        memory.key_queue = Queue(maxsize=100)
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
        self.worker.update_memory.connect(self.update_memory_table)
        self.worker.updated.connect(self.append_text)

        if step == 'run':
            self.thread.started.connect(self.worker.run_app)
        elif step == 'step':
            self.thread.started.connect(self.worker.step_app)
        elif step == 'over':
            memory.stepping_over = True
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
    def keyPressEvent(self, event):
        self.handle_input(event)
        QTextEdit.keyPressEvent(self, event)

    def handle_input(self, event):
        if isinstance(event, QtGui.QKeyEvent) and len(event.text()) > 0:
            self.send_key(event.text())
            if (memory[KBSR] >> 14) & 1 == 1:
                self.initiate_service_routine(self.main, 0x80)

    @staticmethod
    def send_key(event_txt):
        key = ord(str(event_txt))
        memory.key_queue.put(key, 0.01)

    @staticmethod
    def initiate_service_routine(main, vector):
        old_PSR = registers.PSR
        old_PC = registers.PC
        main.mem_table.item(old_PC, 0).setBackground(default_color)

        registers.PSR = registers.PSR & 0x7FFF  # Enter Supervisor Mode
        registers.PSR = registers.PSR | 0x0400  # Set priority level to PL4
        SSP = registers.registers[6]  # Set SSP to R6
        registers.registers[6] -= 1  # Increment stack pointer
        memory[SSP] = old_PSR  # Place PSR on top of Supervisor Stack
        registers.registers[6] -= 1  # Increment stack pointer
        SSP = registers.registers[6]  # Set SSP again
        memory[SSP] = old_PC  # Place PC on top of Supervisor Stack
        registers.PC = memory[vector + 0x100] - 1  # Jump to interrupt vector table location (always 0x0180)
        changed = SSP & bit_mask
        main.mem_table.setDataRange(changed - 2, changed)
        main.reg_table.setData()


# Class for RunHandler, which handles all connections from GUI to logic
# TODO: Rename the variables so that their names make sense
class RunHandler(QtCore.QObject):
    #
    # Below are all signals associated with this worker
    #
    finished = QtCore.pyqtSignal()  # Used when done
    updated = QtCore.pyqtSignal(str)  # Used when console is updated
    update_regs = QtCore.pyqtSignal()  # Used when registers are updated
    started = QtCore.pyqtSignal()  # Used when started
    update_memory = QtCore.pyqtSignal(int)  # Used to update memory gui

    def __init__(self, main, ):
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

        if self.pc_out_of_view(self.main.mem_table, registers.PC & bit_mask):
            self.main.mem_table.verticalScrollBar().setValue(registers.PC & bit_mask)  # If we step, make sure to follow

        self.emit_done()

    @staticmethod
    def pc_out_of_view(mem_table, row):
        rect = mem_table.viewport().contentsRect()
        top = mem_table.indexAt(rect.topLeft())
        if top.isValid():
            bottom = mem_table.indexAt(rect.bottomLeft())
        if not bottom.isValid():
            bottom = mem_table.model().index(mem_table.count() - 1)
        for visible_row in range(top.row(), bottom.row()):
            if visible_row == row:
                return False
        return True

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

    @QtCore.pyqtSlot(int)
    def send_update_gui_memory(self, changed):
        self.update_memory.emit(changed)


# Class for the GUI element displaying the Register Table
class RegisterTable(QTableWidget):
    def __init__(self, *args):
        QTableWidget.__init__(self, *args)
        self.setData()
        self.setRowHeight(0, 29)
        self.setRowHeight(1, 29)
        self.setRowHeight(2, 30)
        self.setRowHeight(3, 30)
        self.setColumnWidth(0, 30)
        self.setColumnWidth(1, 100)
        self.setColumnWidth(2, 50)
        self.setColumnWidth(3, 30)
        self.setColumnWidth(4, 100)
        self.setColumnWidth(5, 50)
        self.setColumnWidth(6, 30)
        self.setColumnWidth(7, 94)
        headerVert = self.verticalHeader()
        headerVert.setVisible(False)
        headerVert.setResizeMode(QtGui.QHeaderView.Stretch)
        headerHoriz = self.horizontalHeader()
        headerHoriz.setVisible(False)
        headerHoriz.setResizeMode(QtGui.QHeaderView.Stretch)
        self.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.setMouseTracking(True)
        self.edited_location = None
        self.cellDoubleClicked.connect(self.set_edited_location)
        self.itemChanged.connect(self.update_internal_registers)

    # Set the visual data to be the same as the underlying registers
    def setData(self):
        # This basically just makes sure the registers go from 0 to 7 down the columns
        for row in range(self.rowCount()):
            reg_num = row
            for col in range(self.columnCount() - 2):  # Subtract 2 so we don't iterate over the special registers
                if col == 3:
                    reg_num = row + 4
                if col % 3 == 0:
                    self.setItem(row, col, QTableWidgetItem(QString('R' + str(reg_num))))
                    self.item(row, col).setBackground(default_color)
                    self.item(row, col).setFlags(QtCore.Qt.ItemIsEnabled)
                if col % 3 == 1:
                    self.setItem(row, col, QTableWidgetItem(QString(to_hex_string(registers[reg_num]))))
                if col % 3 == 2:
                    self.setItem(row, col, QTableWidgetItem(QString(str(registers[reg_num]))))

        # Manually set the rest of the register info
        self.setItem(0, 6, QTableWidgetItem(QString('PC')))
        self.item(0, 6).setBackground(default_color)
        self.setItem(0, 7, QTableWidgetItem(QString(to_hex_string(registers.PC))))
        self.item(0, 6).setFlags(QtCore.Qt.ItemIsEnabled)
        self.item(0, 7).setFlags(QtCore.Qt.ItemIsEnabled)

        self.setItem(1, 6, QTableWidgetItem(QString('IR')))
        self.item(1, 6).setBackground(default_color)
        self.setItem(1, 7, QTableWidgetItem(QString(to_hex_string(registers.IR))))
        self.item(1, 6).setFlags(QtCore.Qt.ItemIsEnabled)
        self.item(1, 7).setFlags(QtCore.Qt.ItemIsEnabled)

        self.setItem(2, 6, QTableWidgetItem(QString('PSR')))
        self.item(2, 6).setBackground(default_color)
        self.setItem(2, 7, QTableWidgetItem(QString(to_hex_string(registers.PSR))))
        self.item(2, 6).setFlags(QtCore.Qt.ItemIsEnabled)
        self.item(2, 7).setFlags(QtCore.Qt.ItemIsEnabled)

        self.setItem(3, 6, QTableWidgetItem(QString('CC')))
        self.item(3, 6).setBackground(default_color)
        CC = '{:03b}'.format(registers.CC)
        CC += ' (n)' if CC[0] == '1' else ' (z)' if CC[1] == '1' else ' (p)'  # Gives context to CC
        self.setItem(3, 7, QTableWidgetItem(QString(CC)))
        self.item(3, 6).setFlags(QtCore.Qt.ItemIsEnabled)
        self.item(3, 7).setFlags(QtCore.Qt.ItemIsEnabled)

    def set_edited_location(self):
        if self.selectedIndexes():
            self.edited_location = self.selectedIndexes()[0]

    def update_internal_registers(self):
        if self.edited_location is not None:
            row = self.edited_location.row()
            column = self.edited_location.column()
            register = row + column
            self.edited_location = None
            if column % 3 == 2:
                register -= 2  # We must subtract 2 b/c the column + row combo will be off by 2 here
                dec_string = str(self.item(row, column).text())
                reg_val = int(dec_string, 10)
                reg_hex = to_hex_string(reg_val)

                self.setItem(row, column - 1, QTableWidgetItem(QString(reg_hex)))
                registers.registers[register] = reg_val  # Convert bit string at address to instruction
            if column % 3 == 1:
                register -= 1  # We must subtract 2 b/c the column + row combo will be off by 2 here
                hex_string = str(self.item(row, column).text()[1:])
                reg_val = int(hex_string, 16)
                reg_hex = str(reg_val)

                self.setItem(row, column + 1, QTableWidgetItem(QString(reg_hex)))
                registers.registers[register] = reg_val  # Convert bit string at address to instruction


# Class for the memory table GUI element
class MemoryTable(QTableWidget):
    def __init__(self, *args):
        QTableWidget.__init__(self, *args)
        self.setData()
        self.setColumnWidth(0, 40)
        self.setColumnWidth(1, 50)
        self.setColumnWidth(2, 163)
        self.setColumnWidth(3, 60)
        self.setColumnWidth(4, 60)
        self.setColumnWidth(5, 140)
        self.verticalHeader().setVisible(False)
        header = self.horizontalHeader()
        header.setVisible(False)
        header.setResizeMode(2, QtGui.QHeaderView.Stretch)
        self.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.setMouseTracking(True)
        self.edited_location = None
        self.cellDoubleClicked.connect(self.set_edited_location)
        self.itemChanged.connect(self.update_internal_memory)
        self.doubleClicked.connect(self.handle_double_click)
        self.labels = None

    # Same as register setData, although there might be a way to make this faster
    def setData(self):
        for row in range(self.rowCount()):
            self.setItem(row, 0, QtGui.QTableWidgetItem())
            self.item(row, 0).setFlags(QtCore.Qt.ItemIsSelectable)
            if 0x514 <= row <= 0xFA00:
                self.clearData(row)
            else:
                inst = memory.memory[row]
                inst_bin = to_bin_string(inst)
                inst_hex = to_hex_string(inst)

                self.setItem(row, 1, QTableWidgetItem(QString(to_hex_string(row))))
                self.item(row, 1).setFlags(QtCore.Qt.ItemIsEnabled)
                self.setItem(row, 2, QTableWidgetItem(QString(inst_bin)))
                self.setItem(row, 3, QTableWidgetItem(QString(inst_hex)))
                self.set_info_column(row, inst)
                self.item(row, 5).setFlags(QtCore.Qt.ItemIsEnabled)

            self.item(row, 0).setBackground(default_color)
            if row == registers.PC:
                self.item(row, 0).setBackground(pc_color)
            self.item(row, 0).setFlags(QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)

    # Used when we know the range of the data to update, so that we don't have to update the entire table
    def setDataRange(self, start, stop, labels={}):
        self.labels = labels
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
            self.set_info_column(row, inst, labels)

    def clearData(self, address):
        self.item(address, 0).setFlags(QtCore.Qt.ItemIsSelectable)
        self.setItem(address, 1, QTableWidgetItem(QString(to_hex_string(address))))
        self.item(address, 1).setFlags(QtCore.Qt.ItemIsEnabled)
        self.setItem(address, 2, QTableWidgetItem(QString("0" * 16)))
        self.setItem(address, 3, QTableWidgetItem(QString("x0000")))
        self.setItem(address, 5, QTableWidgetItem(QString("NOP")))
        self.item(address, 5).setFlags(QtCore.Qt.ItemIsEnabled)

    def set_edited_location(self):
        if self.selectedIndexes():
            self.edited_location = self.selectedIndexes()[0]

    def update_internal_memory(self):
        if self.edited_location is not None:
            address = self.edited_location.row()
            column = self.edited_location.column()
            self.edited_location = None
            if address and column == 2:
                bit_string = str(self.item(address, 2).text())
                inst = int(bit_string, 2)
                inst_hex = to_hex_string(inst)

                self.setItem(address, 3, QTableWidgetItem(QString(inst_hex)))
                self.set_info_column(address, inst)

                memory[address] = inst  # Convert bit string at address to instruction
            if address and column == 3:
                hex_string = str(self.item(address, 3).text()[1:])
                inst = int(hex_string, 16)
                inst_bin = to_bin_string(inst)

                self.setItem(address, 2, QTableWidgetItem(QString(inst_bin)))
                set_info_column(address, inst)
                memory[address] = inst  # Convert bit string at address to instruction

    def handle_double_click(self, cell):
        if cell.column() == 0:
            self.set_breakpoint(cell)
        elif cell.column() == 5:
            pass

    def set_breakpoint(self, cell):
        if cell.row() & bit_mask not in memory.breakpoints:
            self.item(cell.row(), cell.column()).setBackground(breakpoint_color)
            memory.breakpoints.append(cell.row())
        else:
            memory.breakpoints.remove(cell.row() & bit_mask)
            self.item(cell.row(), cell.column()).setBackground(default_color)
        self.clearSelection()

    def set_info_column(self, address, inst, labels=[]):
        inst_list = parser.parse_any(inst)
        if np.issubdtype(type(inst_list[-1]), int):
            final_address = (inst_list[-1] + address & bit_mask) + 1
            if final_address & bit_mask in labels:
                final_address = labels[final_address & bit_mask]
                inst_list[-1] = final_address
            else:
                inst_list[-1] = to_hex_string(final_address)
        self.setItem(address, 5,
                     QTableWidgetItem(QString(str(inst_list.pop(0)) + ' ' + ', '.join(str(e) for e in inst_list))))
        self.item(address, 5).setFlags(QtCore.Qt.ItemIsEnabled)

# Class for the file dialog
class FileDialog(QtGui.QFileDialog):
    def __init__(self, *args):
        QtGui.QFileDialog.__init__(self, *args)
        self.main = None
        self.labeled_addresses = {}

    def file_open(self, main):
        self.main = main
        self.setNameFilters(["OBJ Files (*.obj)"])
        self.selectNameFilter("OBJ Files (*.obj)")
        file_names = self.getOpenFileNames(self, "Open files")

        found_default = False

        if len(file_names) == 0:
            return
        main.mem_table.item(registers.PC, 0).setBackground(default_color)
        memory.key_queue = Queue(maxsize=100)  # Clear key buffer

        # TODO: fix
        for name in file_names:
            pass
            # self.check_symbol_table(name)

        for name in file_names:
            interval = memory.load_instructions(name)
            if interval[0] == default_origin:
                found_default = True
            # Interval that we updated, used so that load times are faster
            main.mem_table.setDataRange(interval[0], interval[1], self.labeled_addresses)
            main.mem_table.verticalScrollBar().setValue(interval[0])
            main.modified_data.append(interval)

        # In place so that the default_origin (probably 0x3000) is used instead of most recent
        # Only used if at least 1 file is found to start at default_origin
        if found_default:
            main.mem_table.item(registers.PC, 0).setBackground(default_color)
            registers.set_origin(default_origin)
            main.mem_table.item(registers.PC, 0).setBackground(pc_color)
            main.mem_table.verticalScrollBar().setValue(default_origin)

    # TODO: fix this monstrosity (i.e. don't use 7 levels of statements)
    def check_symbol_table(self, name):
        base_name = name[:-4]
        try:
            with open(base_name + ".sym") as f:
                for i, line in enumerate(f):
                    if i > 1:
                        label = ''
                        for j, char in enumerate(line):
                            if j > 2:
                                if char == " ":
                                    break
                                label += char
                        address = line[-5:-1]
                        self.main.mem_table.setItem(int(address, 16), 4, QTableWidgetItem(QString(label)))
                        self.labeled_addresses[int(address, 16)] = label

        except IOError:
            return  # It's fine, just no labels for them


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
        self.run_button.clicked.connect(lambda: window.run('run'))

        self.step_button = QtGui.QPushButton('Step', self)
        self.step_button.setMaximumSize(70, 120)
        self.step_button.clicked.connect(lambda: window.run('step'))

        self.step_over_button = QtGui.QPushButton('Step Over', self)
        self.step_over_button.setMaximumSize(70, 120)
        self.step_over_button.clicked.connect(lambda: window.run('over'))

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
