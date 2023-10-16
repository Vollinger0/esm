import sys
import subprocess
from PyQt5.QtWidgets import QApplication, QMainWindow, QSystemTrayIcon, QMenu, QAction, QTextEdit, QMessageBox, QVBoxLayout, QWidget, QPushButton, QStyle

class MyWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.initUI()

    def initUI(self):
        self.setGeometry(100, 100, 600, 400)
        self.setWindowTitle('My GUI App')

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        self.text_output = QTextEdit(self)
        self.text_output.setReadOnly(True)
        layout.addWidget(self.text_output)

        btn_run = QPushButton('Run Command', self)
        btn_log = QPushButton('View Log File', self)

        layout.addWidget(btn_run)
        layout.addWidget(btn_log)

        btn_run.clicked.connect(self.on_run_clicked)
        btn_log.clicked.connect(self.on_view_log_clicked)

    def on_run_clicked(self):
        # Replace this with the command you want to run
        cmd = "python -m mymodule.mycommand"

        try:
            result = subprocess.check_output(cmd, shell=True, text=True)
            self.text_output.setPlainText(result)
        except subprocess.CalledProcessError as e:
            self.text_output.setPlainText(f"Error: {e}")

    def on_view_log_clicked(self):
        # Replace 'logfile.txt' with the actual log file path
        log_file_path = 'logfile.txt'

        try:
            with open(log_file_path, 'r') as log_file:
                log_contents = log_file.read()
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle('Log File')
                msg_box.setText(log_contents)
                msg_box.exec_()
        except FileNotFoundError:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle('Error')
            msg_box.setText('Log file not found.')
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.exec_()

def main():
    app = QApplication(sys.argv)
    window = MyWindow()
    window.show()

    # Create a system tray icon
    tray_icon = QSystemTrayIcon(app)
    tray_icon.setIcon(app.style().standardIcon(QStyle.SP_ComputerIcon))
    tray_menu = QMenu()
    show_action = QAction('Show', app)
    exit_action = QAction('Exit', app)
    tray_menu.addAction(show_action)
    tray_menu.addSeparator()
    tray_menu.addAction(exit_action)
    tray_icon.setContextMenu(tray_menu)
    tray_icon.show()

    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
