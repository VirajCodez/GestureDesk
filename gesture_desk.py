
import math
import subprocess
import sys
import time
from pathlib import Path

import cv2
import mediapipe as mp


RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
MODEL_PATH = RESOURCE_ROOT / "hand_landmarker.task"
WINDOW_NAME = "GestureDesk - Mac Controls"
VOLUME_GESTURES = {"Open palm", "Partial hand"}
MEDIA_GESTURES = {"Peace sign", "Thumbs up", "Thumbs down"}
VOLUME_REPEAT_INTERVAL = 1.0
TRACK_REPEAT_INTERVAL = 1.5
STABLE_GESTURE_FRAMES = 3
HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
)


def finger_extended(landmarks, tip, pip):
    wrist = landmarks[0]
    tip_distance = math.hypot(landmarks[tip].x - wrist.x, landmarks[tip].y - wrist.y)
    pip_distance = math.hypot(landmarks[pip].x - wrist.x, landmarks[pip].y - wrist.y)
    return tip_distance > pip_distance * 1.12


def thumb_direction(landmarks):
    thumb_mcp = landmarks[2]
    thumb_ip = landmarks[3]
    thumb_tip = landmarks[4]
    tip_segment = math.hypot(thumb_tip.x - thumb_ip.x, thumb_tip.y - thumb_ip.y)
    base_segment = math.hypot(thumb_ip.x - thumb_mcp.x, thumb_ip.y - thumb_mcp.y)
    mcp_to_tip = math.hypot(thumb_tip.x - thumb_mcp.x, thumb_tip.y - thumb_mcp.y)
    if mcp_to_tip <= (base_segment + tip_segment) * 0.75:
        return None

    wrist = landmarks[0]
    palm_length = math.hypot(landmarks[9].x - wrist.x, landmarks[9].y - wrist.y)
    vertical_delta = thumb_mcp.y - thumb_tip.y
    threshold = max(0.035, palm_length * 0.2)
    if vertical_delta > threshold:
        return "Thumbs up"
    if vertical_delta < -threshold:
        return "Thumbs down"
    return "Thumb extended sideways"


def classify_hand(landmarks):
    index_up = finger_extended(landmarks, 8, 6)
    middle_up = finger_extended(landmarks, 12, 10)
    ring_up = finger_extended(landmarks, 16, 14)
    pinky_up = finger_extended(landmarks, 20, 18)
    extended_count = sum((index_up, middle_up, ring_up, pinky_up))

    if extended_count >= 3:
        return "Open palm"
    if index_up and middle_up and not ring_up and not pinky_up:
        return "Peace sign"
    if extended_count == 0:
        direction = thumb_direction(landmarks)
        if direction in ("Thumbs up", "Thumbs down"):
            return direction
        if direction is None:
            return "Fist"
    return "Partial hand"


class GestureController:
    def __init__(self):
        self.candidate_gesture = None
        self.candidate_frames = 0
        self.active_gesture = None
        self.last_volume_action_time = None
        self.last_track_action_time = None

    def reset(self):
        self.candidate_gesture = None
        self.candidate_frames = 0
        self.active_gesture = None

    def update(
        self,
        gesture,
        now,
        volume_repeat_interval=VOLUME_REPEAT_INTERVAL,
        track_repeat_interval=TRACK_REPEAT_INTERVAL,
    ):
        if gesture == self.candidate_gesture:
            self.candidate_frames += 1
        else:
            self.candidate_gesture = gesture
            self.candidate_frames = 1

        if self.active_gesture in VOLUME_GESTURES and gesture != self.active_gesture:
            self.active_gesture = None

        actions = []
        if self.candidate_frames >= STABLE_GESTURE_FRAMES and gesture != self.active_gesture:
            self.active_gesture = gesture
            if gesture in VOLUME_GESTURES:
                if (
                    self.last_volume_action_time is None
                    or now - self.last_volume_action_time >= volume_repeat_interval
                ):
                    self.last_volume_action_time = now
                    actions.append(gesture)
            elif gesture in ("Thumbs up", "Thumbs down"):
                if (
                    self.last_track_action_time is None
                    or now - self.last_track_action_time >= track_repeat_interval
                ):
                    self.last_track_action_time = now
                    actions.append(gesture)
            elif gesture == "Peace sign":
                actions.append(gesture)

        if (
            self.active_gesture in VOLUME_GESTURES
            and gesture == self.active_gesture
            and (
                self.last_volume_action_time is None
                or now - self.last_volume_action_time >= volume_repeat_interval
            )
        ):
            self.last_volume_action_time = now
            actions.append(self.active_gesture)

        if (
            self.active_gesture in ("Thumbs up", "Thumbs down")
            and gesture == self.active_gesture
            and (
                self.last_track_action_time is None
                or now - self.last_track_action_time >= track_repeat_interval
            )
        ):
            self.last_track_action_time = now
            actions.append(self.active_gesture)

        return actions


def run_applescript(script):
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, str(error)

    if result.returncode != 0:
        return False, result.stderr.strip() or "AppleScript command failed"
    return True, result.stdout.strip()


def perform_action(gesture, volume_step=6):
    if gesture == "Open palm":
        script = (
            "set currentVolume to output volume of (get volume settings)\n"
            f"set newVolume to currentVolume + {int(volume_step)}\n"
            "if newVolume > 100 then set newVolume to 100\n"
            "set volume output volume newVolume\n"
            "return newVolume as text"
        )
        succeeded, response = run_applescript(script)
        return f"System volume: {response}%" if succeeded else f"System volume error: {response}"

    if gesture == "Partial hand":
        script = (
            "set currentVolume to output volume of (get volume settings)\n"
            f"set newVolume to currentVolume - {int(volume_step)}\n"
            "if newVolume < 0 then set newVolume to 0\n"
            "set volume output volume newVolume\n"
            "return newVolume as text"
        )
        succeeded, response = run_applescript(script)
        return f"System volume: {response}%" if succeeded else f"System volume error: {response}"

    if gesture == "Peace sign":
        return run_music_action("playpause", "Apple Music play/pause toggled")

    if gesture == "Thumbs up":
        return run_music_action("next track", "Apple Music: next track")

    if gesture == "Thumbs down":
        return run_music_action("previous track", "Apple Music: previous track")

    return "No action for this gesture"


def run_music_action(command, success_message):
    script = (
        'tell application "Music"\n'
        "launch\n"
        f"{command}\n"
        f'return "{success_message}"\n'
        "end tell"
    )
    succeeded, response = run_applescript(script)
    return response if succeeded else f"Apple Music error: {response}"


def draw_hand(frame, landmarks):
    height, width = frame.shape[:2]
    points = [
        (int(landmark.x * width), int(landmark.y * height))
        for landmark in landmarks
    ]
    for start, end in HAND_CONNECTIONS:
        cv2.line(frame, points[start], points[end], (70, 205, 170), 2, cv2.LINE_AA)
    for point in points:
        cv2.circle(frame, point, 4, (245, 245, 235), -1, cv2.LINE_AA)


def draw_status(frame, gesture, status, controls_enabled):
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (frame.shape[1], 188), (19, 26, 29), -1)
    cv2.addWeighted(overlay, 0.84, frame, 0.16, 0, frame)
    cv2.putText(
        frame, "GESTUREDESK  /  MAC CONTROLS", (20, 30),
        cv2.FONT_HERSHEY_SIMPLEX, 0.64, (235, 238, 226), 2, cv2.LINE_AA,
    )
    control_color = (95, 232, 177) if controls_enabled else (90, 130, 240)
    control_text = "CONTROLS ENABLED  /  E: EMERGENCY STOP" if controls_enabled else "CONTROLS DISABLED  /  E: RE-ENABLE"
    cv2.putText(
        frame, control_text, (20, 59),
        cv2.FONT_HERSHEY_SIMPLEX, 0.53, control_color, 2, cv2.LINE_AA,
    )
    cv2.putText(
        frame, f"GESTURE  {gesture}", (20, 92),
        cv2.FONT_HERSHEY_SIMPLEX, 0.78, (95, 232, 177), 2, cv2.LINE_AA,
    )
    cv2.putText(
        frame, f"ACTION  {status[:72]}", (20, 122),
        cv2.FONT_HERSHEY_SIMPLEX, 0.52, (245, 245, 235), 1, cv2.LINE_AA,
    )
    cv2.putText(
        frame, "PALM +6  PARTIAL -6  PEACE play/pause  THUMBS UP next  THUMBS DOWN previous",
        (20, 153), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (190, 202, 195), 1, cv2.LINE_AA,
    )
    cv2.putText(
        frame, "E  emergency stop / re-enable     Q  quit",
        (20, 177), cv2.FONT_HERSHEY_SIMPLEX, 0.43, (190, 202, 195), 1, cv2.LINE_AA,
    )


def main():
    if not MODEL_PATH.is_file():
        print(f"Missing hand model: {MODEL_PATH}")
        print("Download the official model from the MediaPipe Hand Landmarker model page.")
        return 1

    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.55,
        min_hand_presence_confidence=0.55,
        min_tracking_confidence=0.55,
    )
    landmarker = mp.tasks.vision.HandLandmarker.create_from_options(options)
    camera = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)

    if not camera.isOpened():
        landmarker.close()
        camera.release()
        print("Camera unavailable. Allow camera access for your terminal or IDE in macOS Privacy & Security settings.")
        return 1

    gesture_controller = GestureController()
    controls_enabled = True
    status = "Show your hand"
    print("GestureDesk started. Press E to stop/re-enable controls or Q to quit.")

    try:
        while True:
            success, frame = camera.read()
            if not success:
                print("Could not read from the camera.")
                break

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
                for action in gesture_controller.update(gesture, time.monotonic()):
                    status = perform_action(action)
                    print(f"{action}: {status}")
            else:
                gesture_controller.reset()

            draw_status(frame, gesture, status, controls_enabled)
            cv2.imshow(WINDOW_NAME, frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q")):
                break
            if key in (ord("e"), ord("E")):
                controls_enabled = not controls_enabled
                gesture_controller.reset()
                status = "Gesture controls enabled" if controls_enabled else "Gesture controls stopped"
    finally:
        camera.release()
        landmarker.close()
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
