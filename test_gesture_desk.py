import unittest
from types import SimpleNamespace
from unittest.mock import patch

from gesture_desk import (
    TRACK_REPEAT_INTERVAL,
    VOLUME_REPEAT_INTERVAL,
    GestureController,
    classify_hand,
    perform_action,
)


def make_hand(extended_fingers, thumb_pose=None):
    landmarks = [SimpleNamespace(x=0.5, y=0.9, z=0.0) for _ in range(21)]
    finger_points = ((5, 6, 7, 8), (9, 10, 11, 12), (13, 14, 15, 16), (17, 18, 19, 20))

    for finger_index, (base, pip, dip, tip) in enumerate(finger_points):
        x = 0.38 + finger_index * 0.08
        landmarks[base] = SimpleNamespace(x=x, y=0.65, z=0.0)
        if finger_index in extended_fingers:
            landmarks[pip] = SimpleNamespace(x=x, y=0.48, z=0.0)
            landmarks[dip] = SimpleNamespace(x=x, y=0.31, z=0.0)
            landmarks[tip] = SimpleNamespace(x=x, y=0.14, z=0.0)
        else:
            landmarks[pip] = SimpleNamespace(x=x, y=0.48, z=0.0)
            landmarks[dip] = SimpleNamespace(x=x, y=0.54, z=0.0)
            landmarks[tip] = SimpleNamespace(x=x, y=0.60, z=0.0)

    if thumb_pose is not None:
        landmarks[1] = SimpleNamespace(x=0.46, y=0.84, z=0.0)
        landmarks[2] = SimpleNamespace(x=0.42, y=0.78, z=0.0)
        if thumb_pose == "up":
            landmarks[3] = SimpleNamespace(x=0.40, y=0.65, z=0.0)
            landmarks[4] = SimpleNamespace(x=0.35, y=0.52, z=0.0)
        elif thumb_pose == "down":
            landmarks[3] = SimpleNamespace(x=0.40, y=0.85, z=0.0)
            landmarks[4] = SimpleNamespace(x=0.35, y=0.97, z=0.0)
        else:
            landmarks[3] = SimpleNamespace(x=0.33, y=0.78, z=0.0)
            landmarks[4] = SimpleNamespace(x=0.24, y=0.78, z=0.0)

    return landmarks


class ClassifyHandTests(unittest.TestCase):
    def test_open_palm(self):
        self.assertEqual(classify_hand(make_hand({0, 1, 2, 3})), "Open palm")

    def test_fist(self):
        self.assertEqual(classify_hand(make_hand(set())), "Fist")

    def test_peace_sign(self):
        self.assertEqual(classify_hand(make_hand({0, 1})), "Peace sign")

    def test_other_partial_pose_is_not_a_fist(self):
        self.assertEqual(classify_hand(make_hand({0})), "Partial hand")

    def test_thumbs_up(self):
        self.assertEqual(classify_hand(make_hand(set(), "up")), "Thumbs up")

    def test_thumbs_down(self):
        self.assertEqual(classify_hand(make_hand(set(), "down")), "Thumbs down")

    def test_sideways_thumb_is_not_mislabeled(self):
        self.assertEqual(classify_hand(make_hand(set(), "sideways")), "Partial hand")


class GestureControllerTests(unittest.TestCase):
    def test_media_gesture_is_one_shot_while_held(self):
        controller = GestureController()
        self.assertEqual(controller.update("Peace sign", 0.00), [])
        self.assertEqual(controller.update("Peace sign", 0.03), [])
        self.assertEqual(controller.update("Peace sign", 0.06), ["Peace sign"])
        self.assertEqual(controller.update("Peace sign", 0.50), [])

    def test_volume_repeats_and_switches_direction(self):
        controller = GestureController()
        for now in (0.00, 0.03):
            self.assertEqual(controller.update("Open palm", now), [])
        self.assertEqual(controller.update("Open palm", 0.06), ["Open palm"])
        self.assertEqual(controller.update("Open palm", 1.05), [])
        self.assertEqual(controller.update("Open palm", 1.06), ["Open palm"])

        self.assertEqual(controller.update("Partial hand", 1.07), [])
        self.assertEqual(controller.update("Partial hand", 1.10), [])
        self.assertEqual(controller.update("Partial hand", 1.13), [])
        self.assertEqual(controller.update("Partial hand", 2.05), [])
        self.assertEqual(controller.update("Partial hand", 2.06), ["Partial hand"])
        self.assertEqual(controller.update("Partial hand", 3.05), [])
        self.assertEqual(controller.update("Partial hand", 3.06), ["Partial hand"])

        self.assertEqual(controller.update("No hand detected", 3.07), [])
        self.assertEqual(controller.update("No hand detected", 3.10), [])
        self.assertEqual(controller.update("No hand detected", 3.13), [])
        self.assertEqual(controller.update("No hand detected", 4.20), [])

    def test_track_skip_repeats_every_interval_and_shares_cooldown(self):
        controller = GestureController()
        self.assertEqual(controller.update("Thumbs up", 10.00), [])
        self.assertEqual(controller.update("Thumbs up", 10.03), [])
        self.assertEqual(controller.update("Thumbs up", 10.06), ["Thumbs up"])
        self.assertEqual(controller.update("Thumbs up", 11.55), [])
        self.assertEqual(controller.update("Thumbs up", 11.56), ["Thumbs up"])

        self.assertEqual(controller.update("Thumbs down", 11.57), [])
        self.assertEqual(controller.update("Thumbs down", 11.60), [])
        self.assertEqual(controller.update("Thumbs down", 11.63), [])
        self.assertEqual(controller.update("Thumbs down", 13.05), [])
        self.assertEqual(controller.update("Thumbs down", 13.06), ["Thumbs down"])
        self.assertEqual(controller.update("Thumbs down", 14.55), [])
        self.assertEqual(controller.update("Thumbs down", 14.56), ["Thumbs down"])

    def test_peace_toggles_once_until_another_pose_is_stable(self):
        controller = GestureController()
        self.assertEqual(controller.update("Peace sign", 20.00), [])
        self.assertEqual(controller.update("Peace sign", 20.03), [])
        self.assertEqual(controller.update("Peace sign", 20.06), ["Peace sign"])
        self.assertEqual(controller.update("Peace sign", 25.00), [])

        self.assertEqual(controller.update("No hand detected", 25.01), [])
        self.assertEqual(controller.update("No hand detected", 25.04), [])
        self.assertEqual(controller.update("No hand detected", 25.07), [])
        self.assertEqual(controller.update("Peace sign", 25.08), [])
        self.assertEqual(controller.update("Peace sign", 25.11), [])
        self.assertEqual(controller.update("Peace sign", 25.14), ["Peace sign"])

    def test_reset_does_not_clear_category_cooldowns(self):
        controller = GestureController()
        self.assertEqual(controller.update("Open palm", 30.00), [])
        self.assertEqual(controller.update("Open palm", 30.03), [])
        self.assertEqual(controller.update("Open palm", 30.06), ["Open palm"])
        controller.reset()
        self.assertEqual(controller.update("Partial hand", 30.07), [])
        self.assertEqual(controller.update("Partial hand", 30.10), [])
        self.assertEqual(controller.update("Partial hand", 30.13), [])
        self.assertEqual(controller.update("Partial hand", 31.05), [])
        self.assertEqual(controller.update("Partial hand", 31.06), ["Partial hand"])

    def test_configured_cooldown_constants(self):
        self.assertEqual(VOLUME_REPEAT_INTERVAL, 1.0)
        self.assertEqual(TRACK_REPEAT_INTERVAL, 1.5)

    def test_fist_is_unassigned_and_peace_sign_is_not_volume(self):
        controller = GestureController()
        self.assertEqual(controller.update("Fist", 0.0), [])
        self.assertEqual(controller.update("Fist", 0.03), [])
        self.assertEqual(controller.update("Fist", 0.06), [])
        self.assertEqual(controller.update("Peace sign", 0.07), [])
        self.assertEqual(controller.update("Peace sign", 0.10), [])
        self.assertEqual(controller.update("Peace sign", 0.13), ["Peace sign"])
        self.assertEqual(controller.update("Peace sign", 0.50), [])


class MediaActionTests(unittest.TestCase):
    @patch("gesture_desk.run_applescript", return_value=(True, "42"))
    def test_partial_hand_lowers_volume(self, run_script):
        self.assertEqual(perform_action("Partial hand", volume_step=8), "System volume: 42%")
        self.assertIn("currentVolume - 8", run_script.call_args.args[0])

    def test_fist_has_no_action(self):
        self.assertEqual(perform_action("Fist"), "No action for this gesture")

    @patch("gesture_desk.run_applescript")
    def test_media_gestures_use_fixed_music_commands(self, run_script):
        run_script.side_effect = [
            (True, "play/pause"),
            (True, "next"),
            (True, "previous"),
        ]
        expected_commands = ("playpause", "next track", "previous track")

        for gesture, expected_command in zip(
            ("Peace sign", "Thumbs up", "Thumbs down"), expected_commands
        ):
            perform_action(gesture)
            script = run_script.call_args.args[0]
            self.assertIn('tell application "Music"', script)
            self.assertIn("launch", script)
            self.assertIn(expected_command, script)
            self.assertNotIn("do shell script", script)

    @patch("gesture_desk.run_applescript", return_value=(False, "Not authorized"))
    def test_music_failures_are_returned_as_visible_status(self, run_script):
        self.assertEqual(
            perform_action("Thumbs up"), "Apple Music error: Not authorized"
        )


if __name__ == "__main__":
    unittest.main()