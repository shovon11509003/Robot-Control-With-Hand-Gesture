import cv2
import math
import time
import mediapipe as mp
import socket
from collections import deque, Counter

WSL_IP = "172.29.161.158"
PORT = 5005
MAX_PIXEL_SPEED = 40.0

DEAD_ZONE = 20
SMOOTHING = 8

last_cmd = "STOP"
last_sent = None

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def send_cmd(cmd: str):
    sock.sendto(cmd.encode(), (WSL_IP, PORT))

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.6,
    min_tracking_confidence=0.6
)
mp_draw = mp.solutions.drawing_utils

def is_finger_up(lm, tip, pip):
    return lm[tip].y < lm[pip].y

def is_open_palm(lm):
    fingers = [
        is_finger_up(lm, 8, 6),
        is_finger_up(lm, 12, 10),
        is_finger_up(lm, 16, 14),
        is_finger_up(lm, 20, 18),
    ]
    thumb = lm[4].x < lm[3].x  # simple heuristic
    return all(fingers) and thumb

def direction_from_motion(dx, dy):
    if abs(dx) < DEAD_ZONE and abs(dy) < DEAD_ZONE:
        return "NONE"
    if abs(dx) > abs(dy):
        return "LEFT" if dx < 0 else "RIGHT"
    else:
        return "FORWARD" if dy < 0 else "BACKWARD"

cap = cv2.VideoCapture(0)
tip_history = deque(maxlen=20)
dir_history = deque(maxlen=SMOOTHING)

print("Starting hand control... Open palm = STOP (ESC to exit)")

current_speed = 0.0
while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    h, w = frame.shape[:2]
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands.process(rgb)

    cmd = last_cmd  # default: keep last command

    if result.multi_hand_landmarks:
        lm = result.multi_hand_landmarks[0].landmark
        mp_draw.draw_landmarks(frame, result.multi_hand_landmarks[0], mp_hands.HAND_CONNECTIONS)

        if is_open_palm(lm):
            cmd = "STOP"
            last_cmd = "STOP"
            current_speed = 0.0
            tip_history.clear()
            dir_history.clear()
        else:
            tip = lm[8]
            x = int(tip.x * w)
            y = int(tip.y * h)
            tip_history.append((x, y))

            if len(tip_history) >= 2:
                dx = x - tip_history[-2][0]
                dy = y - tip_history[-2][1]

                raw = direction_from_motion(dx, dy)
                dir_history.append(raw)

                counts = Counter(dir_history)
                non_none = {k: v for k, v in counts.items() if k != "NONE"}

                if non_none:
                    cmd = max(non_none, key=non_none.get)
                    last_cmd = cmd

                    # Only compute speed if real movement
                    speed = math.sqrt(dx * dx + dy * dy)
                    norm_speed = min(speed / MAX_PIXEL_SPEED, 1.0)

                    MIN_SPEED = 0.15
                    if norm_speed < MIN_SPEED:
                        norm_speed = MIN_SPEED

                    current_speed = norm_speed

            cv2.circle(frame, (x, y), 8, (255, 0, 0), -1)
    else:
        # no hand detected -> safety stop (optional)
        cmd = "STOP"
        last_cmd = "STOP"
        current_speed = 0.0

    # if cmd != last_sent:
    #     send_cmd(cmd)
    #     last_sent = cmd
    timestamp = time.time()
    send_cmd(f"{cmd},{current_speed:.2f},{timestamp}")
    last_sent = cmd

    #cv2.putText(frame, f"CMD: {cmd}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.putText(frame, f"CMD: {cmd}  SPEED: {current_speed:.2f}",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                0.8, (0, 255, 0), 2)
    cv2.imshow("Hand Control (Windows)", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        send_cmd("STOP")
        break

cap.release()
cv2.destroyAllWindows()