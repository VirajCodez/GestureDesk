import sys

from PySide6.QtCore import QTimer, Qt, Slot
from PySide6.QtGui import QCloseEvent, QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QProgressBar,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from camera_worker import CameraWorker
from gesture_desk import MODEL_PATH, VOLUME_REPEAT_INTERVAL


STYLES = """
QMainWindow, QWidget { background: #111618; color: #e6eeeb; font-family: 'Avenir Next'; }
QFrame#panel { background: #192124; border: 1px solid #293538; border-radius: 12px; }
QFrame#preview { background: #0a0e10; border: 1px solid #354346; border-radius: 12px; }
QLabel#eyebrow { color: #82a09a; font-size: 10px; font-weight: 700; letter-spacing: 1px; }
QLabel#title { color: #eff8f3; font-size: 25px; font-weight: 700; }
QLabel#muted { color: #8ca09a; font-size: 12px; }
QLabel#value { color: #edfaf4; font-size: 19px; font-weight: 650; }
QLabel#status { color: #91e5c3; font-size: 12px; font-weight: 700; }
QLabel#error { background: #3a2224; color: #ffaaa0; border: 1px solid #754143; border-radius: 8px; padding: 9px; }
QPushButton { background: #263438; color: #edf6f2; border: 1px solid #3a4b4e; border-radius: 8px; padding: 11px 15px; font-size: 13px; font-weight: 650; }
QPushButton:hover { background: #314247; }
QPushButton:disabled { color: #647370; background: #20292b; }
QPushButton#primary { color: #102019; background: #88e2b5; border: 0; }
QPushButton#primary:hover { background: #a0f0c7; }
QPushButton#stop { background: #482829; color: #ffb2a7; border: 1px solid #8a4b49; }
QPushButton#stop:hover { background: #613435; }
QSlider::groove:horizontal { height: 5px; background: #354346; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #80dcb0; border-radius: 2px; }
QSlider::handle:horizontal { background: #eaf8ef; border: 2px solid #78d5a8; width: 14px; margin: -6px 0; border-radius: 8px; }
"""


def panel():
    widget = QFrame()
    widget.setObjectName("panel")
    return widget


class GestureDeskWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GestureDesk")
        self.setMinimumSize(1060, 700)
        self.resize(1280, 820)
        self.worker = None
        self._latest_frame = None
        self.controls_enabled = True
        self.camera_active = False

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(16)

        header = QHBoxLayout()
        brand = QVBoxLayout()
        title = QLabel("GestureDesk")
        title.setObjectName("title")
        subtitle = QLabel("LOCAL HAND CONTROL  /  MAC MEDIA + VOLUME")
        subtitle.setObjectName("eyebrow")
        brand.addWidget(title)
        brand.addWidget(subtitle)
        header.addLayout(brand)
        header.addStretch(1)
        self.camera_badge = QLabel("●  CAMERA OFF")
        self.camera_badge.setObjectName("status")
        header.addWidget(self.camera_badge, alignment=Qt.AlignVCenter)
        layout.addLayout(header)

        self.error_banner = QLabel()
        self.error_banner.setObjectName("error")
        self.error_banner.setWordWrap(True)
        self.error_banner.hide()
        layout.addWidget(self.error_banner)

        body = QHBoxLayout()
        body.setSpacing(16)
        preview_panel = QFrame()
        preview_panel.setObjectName("preview")
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        self.preview = QLabel("Camera preview is off")
        self.preview.setObjectName("muted")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(600, 360)
        self.preview.setScaledContents(False)
        preview_layout.addWidget(self.preview)
        body.addWidget(preview_panel, 7)

        dashboard = QVBoxLayout()
        dashboard.setSpacing(12)
        gesture_card = panel()
        gesture_layout = QVBoxLayout(gesture_card)
        gesture_layout.setContentsMargins(16, 15, 16, 15)
        gesture_label = QLabel("DETECTED GESTURE")
        gesture_label.setObjectName("eyebrow")
        self.gesture_value = QLabel("No hand detected")
        self.gesture_value.setObjectName("value")
        gesture_layout.addWidget(gesture_label)
        gesture_layout.addWidget(self.gesture_value)
        dashboard.addWidget(gesture_card)

        volume_card = panel()
        volume_layout = QVBoxLayout(volume_card)
        volume_layout.setContentsMargins(16, 14, 16, 14)
        volume_head = QHBoxLayout()
        volume_caption = QLabel("SYSTEM VOLUME")
        volume_caption.setObjectName("eyebrow")
        self.volume_value = QLabel("--%")
        self.volume_value.setObjectName("value")
        volume_head.addWidget(volume_caption)
        volume_head.addStretch(1)
        volume_head.addWidget(self.volume_value)
        volume_layout.addLayout(volume_head)
        self.volume_meter = QProgressBar()
        self.volume_meter.setFixedHeight(7)
        self.volume_meter.setRange(0, 100)
        self.volume_meter.setTextVisible(False)
        self.volume_meter.setStyleSheet("QProgressBar { background: #354346; border: 0; border-radius: 3px; } QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #88e2b5, stop:1 #dfd47d); border-radius: 3px; }")
        volume_layout.addWidget(self.volume_meter)
        dashboard.addWidget(volume_card)

        action_card = panel()
        action_layout = QVBoxLayout(action_card)
        action_layout.setContentsMargins(16, 14, 16, 14)
        action_title = QLabel("LAST ACTION")
        action_title.setObjectName("eyebrow")
        self.action_value = QLabel("Waiting for camera")
        self.action_value.setWordWrap(True)
        self.action_value.setMinimumHeight(40)
        action_layout.addWidget(action_title)
        action_layout.addWidget(self.action_value)
        dashboard.addWidget(action_card)

        controls_card = panel()
        controls_layout = QVBoxLayout(controls_card)
        controls_layout.setContentsMargins(16, 14, 16, 14)
        controls_title = QLabel("GESTURES")
        controls_title.setObjectName("eyebrow")
        controls_layout.addWidget(controls_title)
        for name, action in (
            ("Open palm", "Volume up while held"),
            ("Partial hand", "Volume down while held"),
            ("Fist", "Unassigned"),
            ("Peace sign", "Music play / pause"),
            ("Thumbs up", "Next track"),
            ("Thumbs down", "Previous track"),
        ):
            row = QHBoxLayout()
            name_label = QLabel(name)
            name_label.setStyleSheet("font-weight: 650")
            action_label = QLabel(action)
            action_label.setObjectName("muted")
            row.addWidget(name_label)
            row.addStretch(1)
            row.addWidget(action_label)
            controls_layout.addLayout(row)
        dashboard.addWidget(controls_card)
        dashboard.addStretch(1)
        body.addLayout(dashboard, 4)
        layout.addLayout(body, 1)

        footer = QHBoxLayout()
        start_button = QPushButton("Start Camera")
        start_button.setObjectName("primary")
        self.start_button = start_button
        self.start_button.clicked.connect(self.start_camera)
        self.stop_button = QPushButton("Stop Camera")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_camera)
        self.emergency_button = QPushButton("Emergency Stop")
        self.emergency_button.setObjectName("stop")
        self.emergency_button.clicked.connect(self.toggle_controls)
        footer.addWidget(self.start_button)
        footer.addWidget(self.stop_button)
        footer.addWidget(self.emergency_button)
        footer.addStretch(1)

        settings = QHBoxLayout()
        sensitivity_box = QVBoxLayout()
        sensitivity_top = QHBoxLayout()
        sensitivity_label = QLabel("SENSITIVITY")
        sensitivity_label.setObjectName("eyebrow")
        self.sensitivity_value = QLabel("55%")
        self.sensitivity_value.setObjectName("muted")
        sensitivity_top.addWidget(sensitivity_label)
        sensitivity_top.addStretch(1)
        sensitivity_top.addWidget(self.sensitivity_value)
        sensitivity_box.addLayout(sensitivity_top)
        self.sensitivity_slider = QSlider(Qt.Horizontal)
        self.sensitivity_slider.setRange(35, 85)
        self.sensitivity_slider.setValue(55)
        self.sensitivity_slider.valueChanged.connect(self._sensitivity_changed)
        self.sensitivity_slider.sliderReleased.connect(self._settings_changed)
        sensitivity_box.addWidget(self.sensitivity_slider)

        speed_box = QVBoxLayout()
        speed_top = QHBoxLayout()
        speed_label = QLabel("VOLUME STEP / REPEAT")
        speed_label.setObjectName("eyebrow")
        self.speed_value = QLabel(f"6 points / {VOLUME_REPEAT_INTERVAL:.1f} s")
        self.speed_value.setObjectName("muted")
        speed_top.addWidget(speed_label)
        speed_top.addStretch(1)
        speed_top.addWidget(self.speed_value)
        speed_box.addLayout(speed_top)
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(1, 12)
        self.speed_slider.setValue(6)
        self.speed_slider.valueChanged.connect(self._speed_changed)
        self.speed_slider.sliderReleased.connect(self._settings_changed)
        speed_box.addWidget(self.speed_slider)
        settings.addLayout(sensitivity_box, 1)
        settings.addSpacing(22)
        settings.addLayout(speed_box, 1)

        footer_wrap = QVBoxLayout()
        footer_wrap.addLayout(footer)
        footer_wrap.addLayout(settings)
        layout.addLayout(footer_wrap)

        self.setCentralWidget(root)
        self.setStyleSheet(STYLES)
        self._refresh_controls()
        self._update_volume(0)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self.toggle_controls)
        QShortcut(QKeySequence("Escape"), self, activated=self.emergency_stop)

    @Slot()
    def start_camera(self):
        if self.worker is not None and self.worker.isRunning():
            return
        if not MODEL_PATH.is_file():
            self._show_error(f"Hand tracking model not found: {MODEL_PATH}")
            return
        self.error_banner.hide()
        self.preview.setText("Opening built-in camera…")
        self.camera_badge.setText("●  STARTING CAMERA")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.worker = CameraWorker(
            self.sensitivity_slider.value() / 100,
            self.speed_slider.value(),
            VOLUME_REPEAT_INTERVAL,
            self,
        )
        self.worker.frame_ready.connect(self._show_frame)
        self.worker.camera_state.connect(self._camera_state_changed)
        self.worker.telemetry.connect(self._telemetry_changed)
        self.worker.volume_changed.connect(self._update_volume)
        self.worker.error_occurred.connect(self._show_error)
        self.worker.finished.connect(self._worker_finished)
        self.worker.set_controls_enabled(self.controls_enabled)
        self.worker.start()

    @Slot()
    def stop_camera(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()
            self.camera_badge.setText("●  STOPPING")
            self.stop_button.setEnabled(False)

    @Slot()
    def emergency_stop(self):
        self.controls_enabled = False
        if self.worker is not None and self.worker.isRunning():
            self.worker.set_controls_enabled(False)
        self._refresh_controls()
        self.action_value.setText("Emergency stop active. Gesture commands are disabled.")

    @Slot()
    def toggle_controls(self):
        self.controls_enabled = not self.controls_enabled
        if self.worker is not None and self.worker.isRunning():
            self.worker.set_controls_enabled(self.controls_enabled)
        self._refresh_controls()

    @Slot(QImage)
    def _show_frame(self, image):
        self._latest_frame = image
        self.preview.setText("")
        self._render_latest_frame()

    def _render_latest_frame(self):
        if self._latest_frame is None or self._latest_frame.isNull():
            return
        pixmap = QPixmap.fromImage(self._latest_frame)
        self.preview.setPixmap(pixmap.scaled(
            self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        ))

    @Slot(str)
    def _camera_state_changed(self, state):
        self.camera_badge.setText(f"●  {state.upper()}")

    @Slot(str, str)
    def _telemetry_changed(self, gesture, action):
        self.gesture_value.setText(gesture)
        self.action_value.setText(action)

    @Slot(int)
    def _update_volume(self, volume):
        self.volume_value.setText(f"{volume}%")
        self.volume_meter.setValue(volume)

    @Slot(str)
    def _show_error(self, message):
        self.error_banner.setText(message)
        self.error_banner.show()

    @Slot()
    def _worker_finished(self):
        self.camera_active = False
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.camera_badge.setText("●  CAMERA OFF")
        self._latest_frame = None
        self.preview.clear()
        self.preview.setText("Camera preview is off")

    @Slot(int)
    def _sensitivity_changed(self, value):
        self.sensitivity_value.setText(f"{value}%")

    @Slot(int)
    def _speed_changed(self, value):
        self.speed_value.setText(f"{value} points / {VOLUME_REPEAT_INTERVAL:.1f} s")

    @Slot()
    def _settings_changed(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.update_settings(
                self.sensitivity_slider.value() / 100,
                self.speed_slider.value(),
                VOLUME_REPEAT_INTERVAL,
            )

    def _refresh_controls(self):
        self.emergency_button.setText(
            "Emergency Stop" if self.controls_enabled else "Re-enable Controls"
        )
        if self.controls_enabled:
            self.emergency_button.setObjectName("stop")
        else:
            self.emergency_button.setObjectName("primary")
        self.emergency_button.style().unpolish(self.emergency_button)
        self.emergency_button.style().polish(self.emergency_button)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._render_latest_frame()

    def closeEvent(self, event: QCloseEvent):
        if self.worker is not None and self.worker.isRunning():
            self.worker.stop()
            if not self.worker.wait(5000):
                self._show_error("Camera worker is still stopping. Wait for camera release before quitting.")
                event.ignore()
                return
        event.accept()


def main():
    if "--verify-mediapipe" in sys.argv[1:]:
        import importlib.resources

        import mediapipe as mp
        import mediapipe.tasks.c

        native_library = importlib.resources.files("mediapipe.tasks.c") / "libmediapipe.dylib"
        if not native_library.is_file() or not MODEL_PATH.is_file():
            return 2
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(MODEL_PATH)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=1,
        )
        landmarker = mp.tasks.vision.HandLandmarker.create_from_options(options)
        landmarker.close()
        return 0

    app = QApplication(sys.argv)
    app.setApplicationName("GestureDesk")
    app.setOrganizationName("GestureDesk")
    window = GestureDeskWindow()
    window.show()
    if "--smoke-test" in sys.argv[1:]:
        QTimer.singleShot(1200, window.close)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())