"""
EngineeringHub (AppLauncher) - Main Desktop Application
Adobe Creative Cloud-style launcher for macOS engineering software.
"""

import sys
import os
import subprocess
from typing import List

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QFrame, QScrollArea, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap

from apps_config import APPS
from app_model import App
import auth
import network
from workers import (
    AppActionWorker, StatusCheckWorker, LauncherCheckWorker, LauncherBuilderWorker,
    APP_VERSION
)


class AppCard(QFrame):
    """Card widget representing a single managed application and its controls."""

    def __init__(self, app: App):
        super().__init__()
        self.app = app
        self.is_working = False
        self.worker: AppActionWorker = None

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
        icon_layout.setContentsMargins(0, 0, 0, 0)

        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        candidate_icon_paths = [
            os.path.expanduser(f"~/EngineeringHub/{self.app.icon_path}"),
            os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__))), self.app.icon_path),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), self.app.icon_path),
        ]
        resolved_icon_path = next((p for p in candidate_icon_paths if os.path.exists(p)), None)

        if resolved_icon_path:
            pixmap = QPixmap(resolved_icon_path).scaled(
                32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            icon_label.setPixmap(pixmap)
        else:
            icon_label.setText(self.app.icon)
            icon_label.setStyleSheet("font-size: 20px; background: transparent;")

        icon_layout.addWidget(icon_label)
        top_layout.addWidget(icon_frame)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(3)
        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        self.name_label = QLabel(self.app.name)
        self.name_label.setObjectName("AppName")
        title_row.addWidget(self.name_label)

        self.badge = QLabel(self.app.category)
        self.badge.setObjectName("Badge")
        title_row.addWidget(self.badge)
        title_row.addStretch()
        text_layout.addLayout(title_row)

        self.desc_label = QLabel(self.app.desc)
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
        self.progress_bar.setStyleSheet(
            "QProgressBar { background-color: #27272A; border: none; border-radius: 2px; } "
            "QProgressBar::chunk { background-color: #10B981; border-radius: 2px; }"
        )
        main_layout.addWidget(self.progress_bar)

    def launch_app(self):
        self.app.launch()

    def set_status(self, status: str):
        """
        Updates button states according to application status.
        Crucial: Never display the launch button if the application is not installed on disk.
        """
        if self.is_working:
            return

        self.progress_bar.setVisible(False)
        self.action_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)

        if status == "missing":
            self.action_btn.setVisible(True)
            self.action_btn.setText("Student Portal" if self.app.is_student else "Install")
            self.action_btn.setStyleSheet(
                "QPushButton { background-color: #059669; color: white; } "
                "QPushButton:hover { background-color: #047857; }"
            )
            self.launch_btn.setVisible(False)
            self.delete_btn.setVisible(False)

        elif status == "outdated":
            if self.app.is_installed():
                self.action_btn.setVisible(True)
                self.action_btn.setText("Update")
                self.action_btn.setStyleSheet(
                    "QPushButton { background-color: #B45309; color: #FEF3C7; } "
                    "QPushButton:hover { background-color: #92400E; }"
                )
                self.launch_btn.setVisible(True)
                self.delete_btn.setVisible(True)
            else:
                self.set_status("missing")

        elif status == "installed":
            if self.app.is_installed():
                self.action_btn.setVisible(False)
                self.launch_btn.setVisible(True)
                self.delete_btn.setVisible(True)
            else:
                self.set_status("missing")

        else:
            # Fallback for unknown / error status
            if self.app.is_installed():
                self.action_btn.setVisible(False)
                self.launch_btn.setVisible(True)
                self.delete_btn.setVisible(True)
            else:
                self.set_status("missing")

    def update_progress(self, val: int):
        if val >= 100:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(val)

    def run_action(self):
        if self.app.is_student:
            self.worker = AppActionWorker(self.app, "install")
            self.worker.start()
            return

        self.is_working = True
        # Immediately hide launch and delete buttons while operation is in progress
        self.launch_btn.setVisible(False)
        self.delete_btn.setVisible(False)

        is_install = self.action_btn.text() in ("Install", "Student Portal", "Retry Install", "Needs Auth", "Needs Password")
        action = "install" if is_install else "upgrade"
        self.action_btn.setText(f"{action.title()}ing...")
        self.action_btn.setEnabled(False)
        self.action_btn.setStyleSheet("QPushButton { background-color: #3F3F46; color: white; }")

        self.progress_bar.setVisible(True)
        if self.app.source == "github":
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
        else:
            self.progress_bar.setRange(0, 0)

        self.worker = AppActionWorker(self.app, action)
        if self.app.source == "github":
            self.worker.progress.connect(self.update_progress)
        self.worker.finished_action.connect(self.on_action_finished)
        self.worker.start()

    def run_delete(self):
        self.is_working = True
        # Immediately hide launch and delete buttons
        self.launch_btn.setVisible(False)
        self.delete_btn.setVisible(False)

        self.action_btn.setVisible(True)
        self.action_btn.setText("Uninstalling...")
        self.action_btn.setStyleSheet("QPushButton { background-color: #3F3F46; color: white; }")
        self.action_btn.setEnabled(False)

        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)

        self.worker = AppActionWorker(self.app, "uninstall")
        self.worker.finished_action.connect(self.on_uninstall_finished)
        self.worker.start()

    def on_action_finished(self, success: bool, message: str):
        self.is_working = False
        self.progress_bar.setVisible(False)

        if success:
            if self.app.is_installed():
                self.set_status("installed")
            else:
                self.set_status("missing")
        else:
            # Action failed: under NO circumstances should the Open button appear!
            self.launch_btn.setVisible(False)
            self.delete_btn.setVisible(False)

            if "password" in message.lower() or "auth" in message.lower():
                self.action_btn.setVisible(True)
                self.action_btn.setEnabled(True)
                self.action_btn.setText("Needs Password" if not auth.has_sudo_password() else "Auth Failed")
                self.action_btn.setStyleSheet("QPushButton { background-color: #DC2626; color: white; }")
                self.action_btn.setToolTip(message)
            else:
                if self.app.is_installed():
                    self.set_status("outdated")
                else:
                    self.action_btn.setVisible(True)
                    self.action_btn.setEnabled(True)
                    self.action_btn.setText("Retry Install")
                    self.action_btn.setStyleSheet("QPushButton { background-color: #DC2626; color: white; }")
                    self.action_btn.setToolTip(message)

    def on_uninstall_finished(self, success: bool, message: str):
        self.is_working = False
        self.progress_bar.setVisible(False)

        if success and not self.app.is_installed():
            self.set_status("missing")
        else:
            if self.app.is_installed():
                self.set_status("installed")
            else:
                self.set_status("missing")


class HubWindow(QMainWindow):
    """Main application window for EngineeringHub."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Engineering Hub v{APP_VERSION}")
        self.setFixedSize(680, 560)

        self.apps: List[App] = [App(data) for data in APPS]
        self.check_thread: StatusCheckWorker = None
        self.launcher_thread: LauncherCheckWorker = None
        self.build_thread: LauncherBuilderWorker = None

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(20)

        # Header
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
        self.launcher_progress.setStyleSheet(
            "QProgressBar { background-color: #27272A; border: none; border-radius: 2px; } "
            "QProgressBar::chunk { background-color: #10B981; border-radius: 2px; }"
        )
        launcher_box.addWidget(self.launcher_progress)
        header.addLayout(launcher_box)

        self.check_btn = QPushButton("Check Updates")
        self.check_btn.setObjectName("PrimaryActionBtn")
        self.check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_btn.clicked.connect(lambda: self.start_check(is_periodic=False))
        header.addWidget(self.check_btn)

        main_layout.addLayout(header)

        # Scroll Area for Application Cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName("CardScrollArea")

        scroll_content = QWidget()
        self.card_layout = QVBoxLayout(scroll_content)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setSpacing(10)

        self.cards: List[AppCard] = []
        for app in self.apps:
            card = AppCard(app)
            self.cards.append(card)
            self.card_layout.addWidget(card)

        self.card_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        # Bottom status bar
        bottom_bar = QHBoxLayout()
        self.status_label = QLabel("Tools managed via Homebrew & GitHub")
        self.status_label.setObjectName("StatusLabel")
        bottom_bar.addWidget(self.status_label)
        bottom_bar.addStretch()
        main_layout.addLayout(bottom_bar)

        self.apply_theme()

        # Check for launcher updates
        self.start_launcher_check()

        # Initial check for application statuses
        self.start_check(is_periodic=False)

        # 2-Minute Background Update Check Timer
        # Checks for updates every 2 minutes if connected to the internet
        self.auto_check_timer = QTimer(self)
        self.auto_check_timer.setInterval(2 * 60 * 1000)  # 2 minutes = 120,000 ms
        self.auto_check_timer.timeout.connect(self.on_periodic_timer)
        self.auto_check_timer.start()

    def on_periodic_timer(self):
        """Triggered every 2 minutes; performs update scan if connected to the internet."""
        if network.is_connected(timeout=2.0):
            self.start_launcher_check()
            self.start_check(is_periodic=True)
        else:
            self.status_label.setText("Offline — periodic update check paused until reconnected.")

    def start_launcher_check(self, is_manual: bool = False):
        if self.launcher_thread and self.launcher_thread.isRunning():
            return
        self.launcher_thread = LauncherCheckWorker()
        self.launcher_thread.update_available.connect(self.show_launcher_update)
        self.launcher_thread.check_completed.connect(self.on_launcher_check_completed)
        self.launcher_thread.start()

    def show_launcher_update(self, new_version: str, reason: str = ""):
        btn_text = f"Update Hub to v{new_version}!" if new_version and new_version != "latest" else "Update Hub from GitHub!"
        self.launcher_update_btn.setText(btn_text)
        self.launcher_update_btn.setVisible(True)
        if reason:
            self.status_label.setText(f"{reason}. Click 'Update Hub' to install.")

    def on_launcher_check_completed(self, has_update: bool, message: str):
        if not has_update and not self.launcher_update_btn.isVisible():
            if "Scanning" not in self.check_btn.text():
                self.status_label.setText(f"{message}. All tools up to date.")

    def trigger_self_update(self):
        self.launcher_update_btn.setText("Compiling Update...")
        self.launcher_update_btn.setEnabled(False)
        self.launcher_progress.setVisible(True)
        self.launcher_progress.setValue(0)

        self.build_thread = LauncherBuilderWorker()
        self.build_thread.progress.connect(self.launcher_progress.setValue)
        self.build_thread.finished_build.connect(self.finalize_self_update)
        self.build_thread.start()

    def finalize_self_update(self, success: bool):
        if success:
            script_path = "/tmp/update_hub.sh"
            with open(script_path, "w") as f:
                f.write(
                    "#!/bin/bash\n"
                    "pkill -f 'EngineeringHub' 2>/dev/null\n"
                    "sleep 1\n"
                    "rm -rf /Applications/EngineeringHub.app\n"
                    "cp -R ~/EngineeringHub/dist/EngineeringHub.app /Applications/\n"
                    "open /Applications/EngineeringHub.app\n"
                )
            os.chmod(script_path, 0o755)
            subprocess.Popen([script_path], start_new_session=True)
            sys.exit()
        else:
            self.launcher_update_btn.setText("Update Failed")
            self.launcher_progress.setVisible(False)

    def start_check(self, is_periodic: bool = False):
        if not is_periodic:
            self.start_launcher_check(is_manual=True)

        if self.check_thread and self.check_thread.isRunning():
            return

        if not is_periodic:
            self.check_btn.setEnabled(False)
            self.check_btn.setText("Scanning...")
            self.status_label.setText("Checking GitHub for launcher & app updates...")

        self.check_thread = StatusCheckWorker(self.apps)
        self.check_thread.finished_check.connect(lambda statuses: self.on_check_finished(statuses, is_periodic))
        self.check_thread.start()

    def on_check_finished(self, statuses: dict, is_periodic: bool = False):
        self.check_btn.setEnabled(True)
        self.check_btn.setText("Check Updates")

        updates, missing = 0, 0
        for card in self.cards:
            status = statuses.get(card.app.name, "missing")
            card.set_status(status)
            if not card.is_working:
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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HubWindow()
    window.show()
    sys.exit(app.exec())
