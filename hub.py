import sys
import os
import json
import time
import shutil
import platform
import subprocess
import urllib.request
import webbrowser
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QLabel, QPushButton, QFrame, QScrollArea, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap

APP_VERSION = "1.31"
VERSION_URL = "https://raw.githubusercontent.com/william-short-git/AppLauncher/main/version.txt"

APPS = [
    {"name": "Visual Studio Code", "icon": "💻", "icon_path": "icons/vscode.png", "category": "Development", "app_name": "Visual Studio Code", "cask": "visual-studio-code", "source": "brew", "desc": "Code editing, debugging, and extension ecosystem"},
    {"name": "KiCad", "icon": "🔌", "icon_path": "icons/kicad.png", "category": "EDA / PCB Design", "app_name": "KiCad", "cask": "kicad", "source": "github", "repo": "KiCad/kicad-mac-builder", "desc": "Schematic capture (Updates pulled from GitHub releases)"},
    {"name": "LTspice", "icon": "⚡", "icon_path": "icons/ltspice.png", "category": "Simulation", "app_name": "LTspice", "cask": "ltspice", "source": "brew", "desc": "High-performance SPICE simulation and circuit analysis"},
    {"name": "Autodesk Fusion", "icon": "🏗️", "icon_path": "icons/fusion.png", "category": "CAD / CAM", "app_name": "Autodesk Fusion 360", "cask": "autodesk-fusion", "source": "student", "desc": "Managed securely via Autodesk Education portal"},
    {"name": "FreeCAD", "icon": "🛠️", "icon_path": "icons/freecad.png", "category": "Open-Source CAD", "app_name": "FreeCAD", "cask": "freecad", "source": "github", "repo": "FreeCAD/FreeCAD", "desc": "Parametric 3D modeler (Updates pulled from GitHub)"},
]

class GithubDownloadThread(QThread):
    progress = pyqtSignal(int)
    finished_action = pyqtSignal(bool)

    def __init__(self, repo, app_name):
        super().__init__()
        self.repo = repo
        self.app_name = app_name

    def run(self):
        try:
            url = f"https://api.github.com/repos/{self.repo}/releases/latest"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            data = json.loads(urllib.request.urlopen(req).read())
            
            dmg_url = None
            arch = "arm64" if platform.machine() == "arm64" else "x86_64"
            for asset in data.get("assets", []):
                name = asset["name"].lower()
                if name.endswith(".dmg") and (arch in name or "mac" in name or "darwin" in name):
                    dmg_url = asset["browser_download_url"]
                    break
            
            if not dmg_url:
                for asset in data.get("assets", []):
                    if asset["name"].lower().endswith(".dmg"):
                        dmg_url = asset["browser_download_url"]
                        break
            
            if not dmg_url:
                self.finished_action.emit(False)
                return

            temp_dmg = f"/tmp/{self.app_name}.dmg"
            def reporthook(count, block_size, total_size):
                if total_size > 0:
                    p = int(count * block_size * 100 / total_size)
                    self.progress.emit(min(p, 100))
            
            urllib.request.urlretrieve(dmg_url, temp_dmg, reporthook)
            self.progress.emit(100)

            mount_point = f"/Volumes/{self.app_name}_mount"
            subprocess.run(["hdiutil", "attach", temp_dmg, "-mountpoint", mount_point, "-nobrowse", "-quiet"], check=True)

            app_path = f"/Applications/{self.app_name}.app"
            if os.path.exists(app_path):
                shutil.rmtree(app_path) 
            
            for item in os.listdir(mount_point):
                if item.endswith(".app"):
                    subprocess.run(["cp", "-R", os.path.join(mount_point, item), "/Applications/"], check=True)
                    break
            
            subprocess.run(["hdiutil", "detach", mount_point, "-quiet"], check=True)
            self.finished_action.emit(True)
        except Exception:
            self.finished_action.emit(False)

class BrewActionThread(QThread):
    finished_action = pyqtSignal(bool)

    def __init__(self, action, cask):
        super().__init__()
        self.action = action 
        self.cask = cask

    def run(self):
        brew_bin = shutil.which("brew") or "/opt/homebrew/bin/brew" or "/usr/local/bin/brew"
        try:
            subprocess.run([brew_bin, self.action, "--cask", self.cask], check=True, capture_output=True)
            self.finished_action.emit(True)
        except subprocess.CalledProcessError:
            self.finished_action.emit(False)

class LauncherBuilderThread(QThread):
    progress = pyqtSignal(int)
    finished_build = pyqtSignal(bool)

    def run(self):
        try:
            self.progress.emit(20)
            subprocess.run(["git", "pull", "origin", "main"], cwd=os.path.expanduser("~/EngineeringHub"), check=True, capture_output=True)
            self.progress.emit(50)
            subprocess.run(["./venv/bin/pyinstaller", "--windowed", "--name", "EngineeringHub", "--noconfirm", "hub.py"], cwd=os.path.expanduser("~/EngineeringHub"), check=True, capture_output=True)
            self.progress.emit(100)
            self.finished_build.emit(True)
        except Exception:
            self.finished_build.emit(False)

class LauncherCheckThread(QThread):
    update_available = pyqtSignal(str)

    def run(self):
        try:
            req = urllib.request.Request(f"{VERSION_URL}?t={time.time()}", headers={'Cache-Control': 'no-cache', 'User-Agent': 'Mozilla/5.0'})
            remote_version = urllib.request.urlopen(req, timeout=3).read().decode('utf-8').strip()
            if float(remote_version) > float(APP_VERSION):
                self.update_available.emit(remote_version)
        except Exception:
            pass 

class BrewCheckThread(QThread):
    finished_check = pyqtSignal(dict)

    def run(self):
        brew_bin = shutil.which("brew") or "/opt/homebrew/bin/brew" or "/usr/local/bin/brew"
        try:
            installed = subprocess.run([brew_bin, "list", "--cask", "-1"], capture_output=True, text=True).stdout.splitlines()
            outdated_data = json.loads(subprocess.run([brew_bin, "outdated", "--cask", "--json=v2"], capture_output=True, text=True).stdout)
            outdated = {item["name"]: item["current_version"] for item in outdated_data.get("casks", [])}

            statuses = {}
            for app in APPS:
                if app["source"] == "brew":
                    cask = app["cask"]
                    if cask not in installed:
                        statuses[app["name"]] = "missing"
                    elif cask in outdated:
                        statuses[app["name"]] = "outdated"
                    else:
                        statuses[app["name"]] = "installed"
                elif app["source"] in ["github", "student"]:
                    if not os.path.exists(f"/Applications/{app['app_name']}.app"):
                        statuses[app["name"]] = "missing"
                    else:
                        statuses[app["name"]] = "installed" 
            self.finished_check.emit(statuses)
        except Exception:
            self.finished_check.emit({})

class AppCard(QFrame):
    def __init__(self, app_info):
        super().__init__()
        self.app_info = app_info
        self.is_working = False
        self.setObjectName("AppCard")
        self.setFixedHeight(95)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 14, 18, 14)
        main_layout.setSpacing(8)
        
        top_layout = QHBoxLayout()
        top_layout.setSpacing(14)

        icon_frame = QFrame()
        icon_frame.setFixedSize(40, 40)
        icon_frame.setStyleSheet("background-color: #27272A; border-radius: 8px;")
        icon_layout = QVBoxLayout(icon_frame)
        icon_layout.setContentsMargins(0,0,0,0)
        
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon_path = os.path.expanduser(f"~/EngineeringHub/{app_info.get('icon_path', '')}")
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path).scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            icon_label.setPixmap(pixmap)
        else:
            icon_label.setText(app_info["icon"])
            icon_label.setStyleSheet("font-size: 20px; background: transparent;")
            
        icon_layout.addWidget(icon_label)
        top_layout.addWidget(icon_frame)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(3)
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
        top_layout.addLayout(text_layout, stretch=1)

        self.action_btn = QPushButton("")
        self.action_btn.setObjectName("UpdateBtn")
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_btn.setVisible(False)
        self.action_btn.clicked.connect(self.run_action)
        top_layout.addWidget(self.action_btn)

        self.launch_btn = QPushButton("Open")
        self.launch_btn.setObjectName("LaunchBtn")
        self.launch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.launch_btn.setVisible(False)
        self.launch_btn.clicked.connect(self.launch_app)
        top_layout.addWidget(self.launch_btn)

        self.delete_btn = QPushButton("🗑")
        self.delete_btn.setObjectName("DeleteBtn")
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.setVisible(False)
        self.delete_btn.clicked.connect(self.run_delete)
        top_layout.addWidget(self.delete_btn)

        main_layout.addLayout(top_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("QProgressBar { background-color: #27272A; border: none; border-radius: 2px; } QProgressBar::chunk { background-color: #10B981; border-radius: 2px; }")
        main_layout.addWidget(self.progress_bar)

        self.auth_timer = QTimer()
        self.auth_timer.timeout.connect(self.check_auth_success)

    def launch_app(self):
        subprocess.Popen(["open", "-a", self.app_info["app_name"]])

    def set_status(self, status):
        if self.is_working: return
        self.action_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if status == "missing":
            self.action_btn.setVisible(True)
            self.action_btn.setText("Student Portal" if self.app_info["source"] == "student" else "Install")
            self.action_btn.setStyleSheet("QPushButton { background-color: #059669; color: white; } QPushButton:hover { background-color: #047857; }")
            self.launch_btn.setVisible(False)
            self.delete_btn.setVisible(False)
        elif status == "outdated":
            self.action_btn.setVisible(True)
            self.action_btn.setText("Update")
            self.action_btn.setStyleSheet("QPushButton { background-color: #B45309; color: #FEF3C7; } QPushButton:hover { background-color: #92400E; }")
            self.launch_btn.setVisible(True)
            self.delete_btn.setVisible(True)
        else:
            self.action_btn.setVisible(False)
            self.launch_btn.setVisible(True)
            self.delete_btn.setVisible(True)

    def update_progress(self, val):
        if val == 100:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(val)

    def run_action(self):
        if self.app_info["source"] == "student":
            webbrowser.open("https://www.autodesk.com/education/edu-software/overview")
            return

        self.is_working = True
        self.action_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        action = "install" if self.action_btn.text() == "Install" else "upgrade"
        self.action_btn.setText(f"{action.title()}ing...")
        
        self.progress_bar.setVisible(True)
        
        if self.app_info["source"] == "github":
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.thread = GithubDownloadThread(self.app_info["repo"], self.app_info["app_name"])
            self.thread.progress.connect(self.update_progress)
        else:
            self.progress_bar.setRange(0, 0)
            self.thread = BrewActionThread(action, self.app_info["cask"])
            
        self.thread.finished_action.connect(self.on_action_finished)
        self.thread.start()

    def run_delete(self):
        self.is_working = True
        self.action_btn.setVisible(True)
        self.action_btn.setText("Uninstalling...")
        self.action_btn.setStyleSheet("QPushButton { background-color: #3F3F46; color: white; }")
        self.action_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self.launch_btn.setVisible(False)
        
        if self.app_info["source"] == "brew":
            cmd = f"brew uninstall --cask {self.app_info['cask']} && exit"
            subprocess.Popen(["osascript", "-e", f'tell application "Terminal" to do script "{cmd}"'])
            QTimer.singleShot(5000, lambda: [setattr(self, 'is_working', False), self.set_status("missing")])
        else:
            app_path = f"/Applications/{self.app_info['app_name']}.app"
            subprocess.run(["rm", "-rf", app_path])
            self.is_working = False
            self.set_status("missing")

    def on_action_finished(self, success):
        if success:
            self.is_working = False
            self.set_status("installed")
        else:
            if self.app_info["source"] == "brew":
                self.action_btn.setText("Needs Auth")
                self.action_btn.setStyleSheet("QPushButton { background-color: #DC2626; color: white; }")
                self.action_btn.setEnabled(True)
                cmd = f"brew install --cask {self.app_info['cask']} && exit"
                subprocess.Popen(["osascript", "-e", f'tell application "Terminal" to do script "{cmd}"'])
                self.auth_timer.start(3000)
            else:
                self.is_working = False
                self.set_status("missing")

    def check_auth_success(self):
        brew_bin = shutil.which("brew") or "/opt/homebrew/bin/brew" or "/usr/local/bin/brew"
        if self.app_info["cask"] in subprocess.run([brew_bin, "list", "--cask", "-1"], capture_output=True, text=True).stdout.splitlines():
            self.auth_timer.stop()
            self.is_working = False
            self.set_status("installed")

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

        launcher_box = QVBoxLayout()
        self.launcher_update_btn = QPushButton("Update Launcher!")
        self.launcher_update_btn.setObjectName("LauncherUpdateBtn")
        self.launcher_update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.launcher_update_btn.setVisible(False)
        self.launcher_update_btn.clicked.connect(self.trigger_self_update)
        launcher_box.addWidget(self.launcher_update_btn)

        self.launcher_progress = QProgressBar()
        self.launcher_progress.setFixedHeight(4)
        self.launcher_progress.setTextVisible(False)
        self.launcher_progress.setVisible(False)
        self.launcher_progress.setStyleSheet("QProgressBar { background-color: #27272A; border: none; border-radius: 2px; } QProgressBar::chunk { background-color: #10B981; border-radius: 2px; }")
        launcher_box.addWidget(self.launcher_progress)
        
        header.addLayout(launcher_box)

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
        self.status_label = QLabel("Tools managed via Homebrew & GitHub")
        self.status_label.setObjectName("StatusLabel")
        bottom_bar.addWidget(self.status_label)
        bottom_bar.addStretch()
        main_layout.addLayout(bottom_bar)
        self.apply_theme()

        self.launcher_thread = LauncherCheckThread()
        self.launcher_thread.update_available.connect(self.show_launcher_update)
        self.launcher_thread.start()
        self.start_check()

    def show_launcher_update(self, new_version):
        self.launcher_update_btn.setText(f"Update Hub to v{new_version}")
        self.launcher_update_btn.setVisible(True)

    def trigger_self_update(self):
        self.launcher_update_btn.setText("Compiling Update...")
        self.launcher_update_btn.setEnabled(False)
        self.launcher_progress.setVisible(True)
        self.launcher_progress.setValue(0)
        
        self.build_thread = LauncherBuilderThread()
        self.build_thread.progress.connect(self.launcher_progress.setValue)
        self.build_thread.finished_build.connect(self.finalize_self_update)
        self.build_thread.start()

    def finalize_self_update(self, success):
        if success:
            script_path = "/tmp/update_hub.sh"
            with open(script_path, "w") as f:
                f.write("#!/bin/bash\nrm -rf /Applications/EngineeringHub.app\ncp -r ~/EngineeringHub/dist/EngineeringHub.app /Applications/\nopen -a EngineeringHub\n")
            os.chmod(script_path, 0o755)
            subprocess.Popen([script_path], start_new_session=True)
            sys.exit()
        else:
            self.launcher_update_btn.setText("Update Failed")
            self.launcher_progress.setVisible(False)

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
            QPushButton { font-size: 12px; font-weight: 600; border-radius: 6px; padding: 6px 16px; border: none; }
            #LaunchBtn { background-color: #2563EB; color: #FFFFFF; }
            #LaunchBtn:hover { background-color: #1D4ED8; }
            #DeleteBtn { background-color: #3F3F46; color: #FFFFFF; padding: 6px 10px; }
            #DeleteBtn:hover { background-color: #DC2626; }
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
            status = statuses.get(card.app_info["name"], "unknown")
            card.set_status(status)
            if not card.is_working:
                if status == "outdated": updates += 1
                elif status == "missing": missing += 1

        if updates > 0: self.status_label.setText(f"Found {updates} pending update(s).")
        elif missing > 0: self.status_label.setText(f"Up to date. {missing} app(s) are not installed.")
        else: self.status_label.setText("All engineering tools are installed and up to date.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HubWindow()
    window.show()
    sys.exit(app.exec())
