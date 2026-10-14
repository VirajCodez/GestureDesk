import threading
import time

import cv2
import mediapipe as mp
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from gesture_desk import (
    MODEL_PATH,
    TRACK_REPEAT_INTERVAL,
    VOLUME_REPEAT_INTERVAL,
    GestureController,
    classify_hand,
    draw_hand,
    perform_action,
)


class CameraWorker(QThread):
    frame_ready = Signal(QImage)
    camera_state = Signal(str)
    telemetry = Signal(str, str)
    volume_changed = Signal(int)
    error_occurred = Signal(str)

    def __init__(self, sensitivity, volume_step, repeat_interval, parent=None):
        super().__init__(parent)
        self._lock = threading.Lock()
        self._stopping = False
        self._controls_enabled = True
        self._sensitivity = sensitivity
        self._volume_step = volume_step
        self._repeat_interval = repeat_interval

    def set_controls_enabled(self, enabled):
        with self._lock:
            self._controls_enabled = enabled

    def update_settings(self, sensitivity, volume_step, repeat_interval):
        with self._lock:
            self._sensitivity = sensitivity
            self._volume_step = volume_step
            self._repeat_interval = repeat_interval

    def stop(self):
        with self._lock:
            self._stopping = True

    def _configuration(self):
        with self._lock:
            return (
                self._stopping,
                self._controls_enabled,
                self._sensitivity,
                self._volume_step,
                self._repeat_interval,
            )

    def run(self):
        task_path = MODEL_PATH
        if not task_path.is_file():
            self.error_occurred.emit(f"Hand tracking model is missing: {task_path}")
            self.camera_state.emit("Unavailable")
            return

        self.camera_state.emit("Starting camera")
        camera = None
        landmarker = None
        controller = GestureController()
        last_gesture = "No hand detected"
        last_action = "Camera ready"
        last_telemetry_time = 0.0
        last_volume_query_time = 0.0
        active_sensitivity = None

        try:
            camera = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)
            if not camera.isOpened():
                raise RuntimeError(
                    "Camera could not be opened. Allow camera access in System Settings > Privacy & Security > Camera."
                )

            camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.camera_state.emit("Camera active")

            while True:
                stopping, controls_enabled, sensitivity, volume_step, repeat_interval = self._configuration()
                if stopping:
                    break

                if sensitivity != active_sensitivity:
                    if landmarker is not None:
                        landmarker.close()
                    options = mp.tasks.vision.HandLandmarkerOptions(
                        base_options=mp.tasks.BaseOptions(model_asset_path=str(task_path)),
                        running_mode=mp.tasks.vision.RunningMode.VIDEO,
                        num_hands=1,
                        min_hand_detection_confidence=sensitivity,
                        min_hand_presence_confidence=sensitivity,
                        min_tracking_confidence=sensitivity,
                    )
                    landmarker = mp.tasks.vision.HandLandmarker.create_from_options(options)
                    active_sensitivity = sensitivity
                    controller.reset()

                success, frame = camera.read()
                if not success:
                    raise RuntimeError("Camera stopped returning frames. Check camera permissions and connection.")

                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                timestamp_ms = time.monotonic_ns() // 1_000_000
                result = landmarker.detect_for_video(image, timestamp_ms)
                gesture = "No hand detected"
                if result.hand_landmarks:
                    landmarks = result.hand_landmarks[0]
                    draw_hand(frame, landmarks)
                    gesture = classify_hand(landmarks)

                if controls_enabled:
                    for action in controller.update(
                        gesture,
                        time.monotonic(),
                        volume_repeat_interval=repeat_interval or VOLUME_REPEAT_INTERVAL,
                        track_repeat_interval=TRACK_REPEAT_INTERVAL,
                    ):
                        if not self._configuration()[1]:
                            controller.reset()
                            break
                        last_action = perform_action(action, volume_step)
                        if " error:" in last_action.lower():
                            self.error_occurred.emit(last_action)
                else:
                    controller.reset()
                    last_action = "Gesture controls stopped"

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                height, width, channels = rgb.shape
                image = QImage(rgb.data, width, height, channels * width, QImage.Format_RGB888).copy()
                self.frame_ready.emit(image)

                now = time.monotonic()
                if now - last_telemetry_time >= 0.12 or gesture != last_gesture:
                    self.telemetry.emit(gesture, last_action)
                    last_telemetry_time = now
                    last_gesture = gesture

                if now - last_volume_query_time >= 1.0:
                    volume_ok, volume_text = self._query_volume()
                    if volume_ok:
                        try:
                            self.volume_changed.emit(max(0, min(100, int(float(volume_text)))))
                        except ValueError:
                            pass
                    last_volume_query_time = now
        except Exception as error:
            self.error_occurred.emit(str(error))
            self.camera_state.emit("Error")
        finally:
            if camera is not None:
                camera.release()
            if landmarker is not None:
                landmarker.close()
            self.camera_state.emit("Camera stopped")

    @staticmethod
    def _query_volume():
        from gesture_desk import run_applescript

        return run_applescript("return output volume of (get volume settings) as text")