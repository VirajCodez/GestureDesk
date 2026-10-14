# GestureDesk

GestureDesk is a manually launched macOS desktop application that lets you control system volume and Apple Music using real-time hand gestures detected through your webcam.

The application uses Python, OpenCV, and MediaPipe for hand tracking and gesture recognition. Camera frames and hand landmarks are processed locally on your Mac. Recognized gestures trigger fixed AppleScript operations, and gesture content is never passed to a shell command.

## Features

- Real-time hand tracking and gesture recognition.
- Hands-free system volume control.
- Apple Music playback and track navigation.
- Emergency Stop to immediately disable gesture actions.
- Independent camera start and stop controls.
- Adjustable detection sensitivity and volume step.
- Standalone macOS application packaging.
- Manual launch with no automatic startup mechanism.

## Gesture Controls

| Hand Gesture | Action |
|---|---|
| Open palm | Increase system volume while held |
| Partial hand | Decrease system volume while held |
| Peace sign | Toggle Apple Music play/pause once per gesture |
| Thumbs up | Play the next Apple Music track |
| Thumbs down | Play the previous Apple Music track |
| Fist | No system action |

### Additional Controls

- **Emergency Stop:** Immediately disables all gesture actions.
- **Re-enable Controls:** Restores gesture actions after an emergency stop.
- **Start Camera / Stop Camera:** Controls the camera independently of the desktop application.
- **Sensitivity:** Adjusts MediaPipe detection confidence.
- **Volume Step:** Changes the amount of each volume adjustment.

Volume actions repeat no more frequently than once per second, while held track-skip gestures repeat no more frequently than once every 1.5 seconds. The peace-sign gesture triggers only once until another stable gesture or no-hand detection is observed.

## Technology Stack

- **Python** — application logic
- **OpenCV** — camera capture and computer vision
- **MediaPipe** — hand landmark detection and gesture recognition
- **AppleScript** — macOS system volume and Apple Music control
- **PyInstaller** — standalone application packaging

## Requirements

- macOS
- Python environment with the project's required dependencies
- Webcam access
- Apple Music for music playback controls

The packaged application is built for Apple Silicon using the active Apple Silicon Python environment.

## Build GestureDesk.app

Open Terminal in the project directory and run:

```sh
./.venv/bin/python -m pip install -r requirements.txt
./build_app.sh
```

The generated application is located at:

```text
dist/GestureDesk.app
```

The build script creates the application icon, bundles the `hand_landmarker.task` model, and builds an arm64 application bundle. It explicitly collects MediaPipe 0.10.35's `mediapipe.tasks.c` package and `libmediapipe.dylib`, which MediaPipe loads through `importlib.resources`.

The build script checks that the required package and native library are present in the finished bundle and fails if either is missing.

Run the build script again after modifying the source code to rebuild the application. Build output is kept under `build/` and `dist/`.

### Verify the Packaged MediaPipe Model

To verify that the packaged application can resolve the MediaPipe C library and initialize the included hand model without opening the camera, run:

```sh
./dist/GestureDesk.app/Contents/MacOS/GestureDesk --verify-mediapipe
```

An exit status of `0` indicates that package/resource lookup and HandLandmarker initialization succeeded. This verification does not request camera or Apple Music permissions.

## Launch the Application

1. Open the `dist` folder in Finder.
2. Double-click `GestureDesk.app`.
3. Alternatively, drag `GestureDesk.app` into `/Applications` and launch it from Finder.

GestureDesk does not install a login item, LaunchAgent, service, scheduled task, or automatic-start mechanism. It runs only when opened manually. Quitting the application stops the camera worker and releases the camera.

Because the locally built application is not Developer ID signed or notarized, macOS may display a security warning on first launch. If macOS offers an **Open** confirmation for this app, use that confirmation rather than disabling Gatekeeper or other macOS security protections.

For distribution outside your own Mac, sign and notarize the application using your own Apple Developer ID.

## macOS Permissions

### Camera

Allow GestureDesk to access the camera in:

**System Settings → Privacy & Security → Camera**

The application bundle includes `NSCameraUsageDescription`.

### Apple Music and Automation

Allow GestureDesk to control Music when macOS prompts you. Review the permissions in:

**System Settings → Privacy & Security → Automation**

The application bundle includes `NSAppleEventsUsageDescription`.

System volume is controlled through macOS AppleScript volume settings. GestureDesk does not require microphone access, a network service, or login permissions.

If the application was copied to `/Applications` before permissions were granted, quit and reopen it after changing the privacy settings. Rebuilding the application may cause macOS to request permissions again.

## Troubleshooting

**Camera unavailable**
- Check camera permissions.
- Close other applications using the camera.
- Restart GestureDesk.

**Apple Music controls not working**
- Open Music once.
- Approve the Automation permission prompt.
- Check the application's last-action/error panel for AppleScript failures.

**Hand landmark model missing**
- Rebuild using `./build_app.sh`.
- Confirm the build completes and includes the required model.

**Build dependency errors**
- Install dependencies using `./.venv/bin/python -m pip install -r requirements.txt`.
- Build on macOS using the appropriate Python environment. PyInstaller bundles are platform-specific.

**Incorrect gesture detection**
- Adjust the Sensitivity setting.
- Keep your hand fully visible in the camera frame.
- Hold gestures briefly to allow stabilization.

## Development Checks

Run the unit tests:

```sh
./.venv/bin/python -m unittest -v
```

Check the Python files for syntax errors:

```sh
./.venv/bin/python -m py_compile gesture_desk.py camera_worker.py gesture_app.py
```

## Project Purpose

GestureDesk explores practical applications of computer vision and AI-assisted software development by connecting real-time hand gesture recognition with desktop automation.

The project was developed with AI coding assistance for implementation, debugging, and troubleshooting.
