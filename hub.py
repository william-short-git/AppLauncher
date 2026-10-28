import sys
import json
import shutil
import subprocess
import urllib.request
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QLabel, QPushButton, QFrame, QScrollArea
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

APP_VERSION = "1.0"
VERSION_URL = "https://raw.githubusercontent.com/william-short-git/AppLauncher/main/version.txt"

APPS = [
    {"name": "Visual Studio Code", "category": "Development", "app_name": "Visual Studio Code", "cask": "visual-studio-code", "desc": "Code editing, debugging, and extension ecosystem"},
    {"name": "KiCad", "category": "EDA / PCB Design", "app_name": "KiCad", "cask": "kicad", "desc": "Schematic capture and printed circuit board layout"},
    {"name": "LTspice", "category": "Simulation", "app_name": "LTspice", "cask": "ltspice", "desc": "High-performance SPICE simulation and circuit analysis"},
    {"name": "Autodesk Fusion", "category": "CAD / CAM", "app_name": "Autodesk Fusion", "cask": "autodesk-fusion", "desc": "Cloud-based 3D modeling, CAM, and engineering design"},
    {"name": "FreeCAD", "category": "Open-Source CAD", "app_name": "FreeCAD", "cask": "freecad", "desc": "Parametric 3D modeler for mechanical engineering"},
]

class LauncherCheckThread(QThread):
    update_available = pyqtSignal(str)

    def run(self):
        try:
            req = urllib.request.Request(VERSION_URL, headers={'Cache-Control': 'no-cache'})
            remote_version = urllib.request.urlopen(req, timeout=3).read().decode('utf-8').strip()
            if float(remote_version) > float(APP_VERSION):
                self.update_available.emit(remote_version)
        except Exception as e:
            pass # Fail silently if offline

class BrewCheckThread(QThread):
    finished_check = pyqtSignal(dict)

    def run(self):
        brew_bin = shutil.which("brew") or "/opt/homebrew/bin/brew" or "/usr/local/bin/brew"
        try:
            installed_res = subprocess.run([brew_bin, "list", "--cask", "-1"], capture_output=True, text=True, check=True)
            installed = installed_res.stdout.splitlines()

            outdated_res = subprocess.run([brew_bin, "outdated", "--cask", "--json=v2"], capture_output=True, text=True, check=True)
            outdated_data = json.loads(outdated_res.stdout)
            outdated = {item["name"]: item["current_version"] for item in outdated_data.get("casks", [])}

            statuses = {}
            for app in APPS:
                cask = app["cask"]
                if cask not in installed:
                    statuses[cask] = "missing"
                elif cask in outdated:
                    statuses[cask] = "outdated"
                else:
                    statuses[cask] = "installed"
                    
            self.finished_check.emit(statuses)
        except Exception:
            self.finished_check.emit({})

class AppCard(QFrame):
    def __init__(self, app_info):
        super().__init__()
        self.app_info = app_info
        self.setObjectName("AppCard")
        self.setFixedHeight(82)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(3)
        text_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        self.name_label = QLabel(app_info["name"])
        self.name_label.setObjectName("AppName")
        title_row.addWidget(self.name_label)

        self.badge = QLabel(app_info["category"])
        self.badge.setObjectName("Badge")
        title_row.addWidget(self.badge)
        title_row.addStretch()
        text_layout.addLayout(title_row)

        self.desc_label = QLabel(app_info["desc"])
        self.desc_label.setObjectName("AppDesc")
        text_layout.addWidget(self.desc_label)

        layout.addLayout(text_layout, stretch=1)

        self.action_btn = QPushButton("")
        self.action_btn.setObjectName("UpdateBtn")
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_btn.setVisible(False)
        self.action_btn.clicked.connect(self.run_action)
        layout.addWidget(self.action_btn)

        self.launch_btn = QPushButton("Open")
        self.launch_btn.setObjectName("LaunchBtn")
        self.launch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.launch_btn.clicked.connect(self.launch_app)
        layout.addWidget(self.launch_btn)

    def launch_app(self):
        subprocess.Popen(["open", "-a", self.app_info["app_name"]])

    def set_status(self, status):
        if status == "missing":
            self.action_btn.setVisible(True)
            self.action_btn.setText("Install")
            self.action_btn.setStyleSheet("QPushButton { background-color: #059669; color: white; font-size: 12px; font-weight: 600; border-radius: 6px; padding: 6px 12px; border: none; } QPushButton:hover { background-color: #047857; }")
            self.launch_btn.setVisible(False)
        elif status == "outdated":
            self.action_btn.setVisible(True)
            self.action_btn.setText("Update")
            self.action_btn.setStyleSheet("QPushButton { background-color: #B45309; color: #FEF3C7; font-size: 12px; font-weight: 600; border-radius: 6px; padding: 6px 12px; border: none; } QPushButton:hover { background-color: #92400E; }")
            self.launch_btn.setVisible(True)
        else:
            self.action_btn.setVisible(False)
            self.launch_btn.setVisible(True)

    def run_action(self):
        cask = self.app_info["cask"]
        self.action_btn.setEnabled(False)
        
        if self.action_btn.text() == "Install":
            self.action_btn.setText("Installing...")
            cmd = f"brew install --cask {cask}"
        else:
            self.action_btn.setText("Updating...")
            cmd = f"brew upgrade --cask {cask}"
            
        subprocess.Popen(["osascript", "-e", f'tell application "Terminal" to do script "{cmd}"'])

class HubWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Engineering Hub v{APP_VERSION}")
        self.setFixedSize(680, 560)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(20)

        header = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(2)

        title = QLabel("Workspace")
        title.setObjectName("HeaderTitle")
        subtitle = QLabel("Engineering suite launcher & package manager")
        subtitle.setObjectName("HeaderSubtitle")

        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        header.addLayout(header_text)
        header.addStretch()

        # Secret Launcher Update Button
        self.launcher_update_btn = QPushButton("Update Launcher!")
        self.launcher_update_btn.setObjectName("LauncherUpdateBtn")
        self.launcher_update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.launcher_update_btn.setVisible(False)
        self.launcher_update_btn.clicked.connect(self.trigger_self_update)
        header.addWidget(self.launcher_update_btn)

        self.check_btn = QPushButton("Check Updates")
        self.check_btn.setObjectName("PrimaryActionBtn")
        self.check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_btn.clicked.connect(self.start_check)
        header.addWidget(self.check_btn)

        main_layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName("CardScrollArea")

        scroll_content = QWidget()
        self.card_layout = QVBoxLayout(scroll_content)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setSpacing(10)

        self.cards = []
        for app in APPS:
            card = AppCard(app)
            self.cards.append(card)
            self.card_layout.addWidget(card)

        self.card_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        bottom_bar = QHBoxLayout()
        self.status_label = QLabel("All tools managed via Homebrew")
        self.status_label.setObjectName("StatusLabel")
        bottom_bar.addWidget(self.status_label)
        bottom_bar.addStretch()

        main_layout.addLayout(bottom_bar)
        self.apply_theme()

        # Automatically check if a launcher update exists on startup
        self.launcher_thread = LauncherCheckThread()
        self.launcher_thread.update_available.connect(self.show_launcher_update)
        self.launcher_thread.start()

    def show_launcher_update(self, new_version):
        self.launcher_update_btn.setText(f"Update Hub to v{new_version}")
        self.launcher_update_btn.setVisible(True)

    def trigger_self_update(self):
        # 1. Pull latest code from GitHub
        # 2. Rebuild the app with PyInstaller
        # 3. Replace the old app in /Applications
        # 4. Relaunch it!
        update_script = (
            "cd ~/EngineeringHub && "
            "git pull origin main && "
            "./venv/bin/pyinstaller --windowed --name EngineeringHub --noconfirm hub.py && "
            "rm -rf /Applications/EngineeringHub.app && "
            "cp -r dist/EngineeringHub.app /Applications/ && "
            "open -a EngineeringHub && "
            "exit"
        )
        subprocess.Popen(["osascript", "-e", f'tell application "Terminal" to do script "{update_script}"'])
        sys.exit() # Close the current app immediately so it can be overwritten safely

    def apply_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #121214; }
            #HeaderTitle { color: #FFFFFF; font-size: 22px; font-weight: 700; letter-spacing: -0.4px; }
            #HeaderSubtitle { color: #71717A; font-size: 13px; font-weight: 400; }
            #PrimaryActionBtn { background-color: #27272A; color: #FAFAFA; font-size: 13px; font-weight: 500; border: 1px solid #3F3F46; border-radius: 8px; padding: 8px 16px; }
            #PrimaryActionBtn:hover { background-color: #3F3F46; border-color: #52525B; }
            #LauncherUpdateBtn { background-color: #10B981; color: white; font-weight: bold; border-radius: 8px; padding: 8px 16px; border: none;}
            #LauncherUpdateBtn:hover { background-color: #059669; }
            #AppCard { background-color: #18181B; border: 1px solid #27272A; border-radius: 12px; }
            #AppCard:hover { border-color: #3F3F46; background-color: #1C1C20; }
            #AppName { color: #F4F4F5; font-size: 15px; font-weight: 600; }
            #Badge { background-color: #27272A; color: #A1A1AA; font-size: 10px; font-weight: 600; border-radius: 4px; padding: 2px 6px; text-transform: uppercase; letter-spacing: 0.3px; }
            #AppDesc { color: #71717A; font-size: 12px; }
            #LaunchBtn { background-color: #2563EB; color: #FFFFFF; font-size: 12px; font-weight: 600; border-radius: 6px; padding: 6px 16px; border: none; }
            #LaunchBtn:hover { background-color: #1D4ED8; }
            #StatusLabel { color: #52525B; font-size: 11px; }
            #CardScrollArea { background: transparent; }
            QScrollBar:vertical { border: none; background: transparent; width: 6px; margin: 0px; }
            QScrollBar::handle:vertical { background: #27272A; border-radius: 3px; min-height: 20px; }
        """)

    def start_check(self):
        self.check_btn.setEnabled(False)
        self.check_btn.setText("Scanning...")
        self.status_label.setText("Querying Homebrew package repository...")
        self.thread = BrewCheckThread()
        self.thread.finished_check.connect(self.on_check_finished)
        self.thread.start()

    def on_check_finished(self, statuses):
        self.check_btn.setEnabled(True)
        self.check_btn.setText("Check Updates")
        
        updates, missing = 0, 0
        for card in self.cards:
            cask = card.app_info["cask"]
            status = statuses.get(cask, "unknown")
            card.set_status(status)
            if status == "outdated":
                updates += 1
            elif status == "missing":
                missing += 1

        if updates > 0:
            self.status_label.setText(f"Found {updates} pending update(s).")
        elif missing > 0:
            self.status_label.setText(f"Up to date. {missing} app(s) are not installed.")
        else:
            self.status_label.setText("All engineering tools are installed and up to date.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HubWindow()
    window.show()
    sys.exit(app.exec())
