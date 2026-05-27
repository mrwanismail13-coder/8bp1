import pygame
import pygame.gfxdraw
import win32gui
import win32con
import win32api
import cv2
import numpy as np
import math
import sys
import time
import keyboard

# =========================================
# DXCAM / MSS FALLBACK
# =========================================

try:

    import dxcam
    DXCAM_AVAILABLE = True

except:

    DXCAM_AVAILABLE = False

    import mss

# =========================================
# OpenCV Optimization
# =========================================

cv2.setUseOptimized(True)
cv2.setNumThreads(0)

# =========================================
# Settings
# =========================================

FPS = 240

BALL_RADIUS = 16

SMOOTH_WHITE = 0.35
SMOOTH_GHOST = 0.22
TRACK_SMOOTH = 0.35

SCREEN_WIDTH = win32api.GetSystemMetrics(0)
SCREEN_HEIGHT = win32api.GetSystemMetrics(1)

TRANSPARENT = (1, 1, 1)

WHITE = (255, 255, 255)
YELLOW = (255, 255, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 162, 232)
PINK = (255, 0, 128)
ORANGE = (255, 165, 0)
CYAN = (0, 220, 255)

INNER_OFFSET = BALL_RADIUS + 10

# =========================================
# Variables
# =========================================

table_region = None

locked_ball = None
selected_pocket = None

smooth_white = None
smooth_ghost = None

tracked_balls = {}
next_ball_id = 0

last_lock_time = 0

# =========================================
# Helper Functions
# =========================================

def distance(p1, p2):

    return math.hypot(
        p1[0] - p2[0],
        p1[1] - p2[1]
    )

def smooth(current, previous, alpha):

    if previous is None:
        return current

    return (
        previous[0] + (current[0] - previous[0]) * alpha,
        previous[1] + (current[1] - previous[1]) * alpha
    )

def aa_circle(surface, color, pos, radius):

    pygame.gfxdraw.aacircle(
        surface,
        int(pos[0]),
        int(pos[1]),
        radius,
        color
    )

def detect_table(frame):

    hsv = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2HSV
    )

    lower = np.array([30, 40, 40])
    upper = np.array([100, 255, 255])

    mask = cv2.inRange(
        hsv,
        lower,
        upper
    )

    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    if contours:

        largest = max(
            contours,
            key=cv2.contourArea
        )

        if cv2.contourArea(largest) > 40000:

            x, y, w, h = cv2.boundingRect(largest)

            return {
                "left": x,
                "top": y,
                "width": w,
                "height": h
            }

    return None

def is_white_ball(roi):

    if roi is None or roi.size == 0:
        return False

    hsv = cv2.cvtColor(
        roi,
        cv2.COLOR_BGR2HSV
    )

    lower = np.array([0, 0, 185])
    upper = np.array([180, 45, 255])

    mask = cv2.inRange(
        hsv,
        lower,
        upper
    )

    white_ratio = np.sum(mask == 255) / mask.size

    mean_bgr = cv2.mean(roi)[:3]

    b = mean_bgr[0]
    g = mean_bgr[1]
    r = mean_bgr[2]

    brightness = (r + g + b) / 3

    balance = (
        abs(r - g) < 18 and
        abs(r - b) < 18 and
        abs(g - b) < 18
    )

    return (
        white_ratio > 0.58
        and balance
        and brightness > 170
    )

def ghost_ball(target, pocket, radius):

    dx = target[0] - pocket[0]
    dy = target[1] - pocket[1]

    dist = math.hypot(dx, dy)

    if dist == 0:
        return target

    ratio = (dist + radius * 2) / dist

    return (
        pocket[0] + dx * ratio,
        pocket[1] + dy * ratio
    )

# =========================================
# Initialize Pygame
# =========================================

pygame.init()
pygame.font.init()

pygame.mouse.set_visible(False)

pygame.event.set_allowed([
    pygame.QUIT
])

screen = pygame.display.set_mode(
    (SCREEN_WIDTH, SCREEN_HEIGHT),
    pygame.NOFRAME |
    pygame.HWSURFACE |
    pygame.DOUBLEBUF
)

hwnd = pygame.display.get_wm_info()["window"]

font = pygame.font.SysFont(
    "Arial",
    18,
    bold=True
)

pocket_font = pygame.font.SysFont(
    "Arial",
    22,
    bold=True
)

cached_text = font.render(
    "Static AI Aim Assist",
    True,
    GREEN
)

# =========================================
# Overlay Setup
# =========================================

styles = win32gui.GetWindowLong(
    hwnd,
    win32con.GWL_EXSTYLE
)

win32gui.SetWindowLong(
    hwnd,
    win32con.GWL_EXSTYLE,
    styles
    | win32con.WS_EX_LAYERED
    | win32con.WS_EX_TRANSPARENT
    | win32con.WS_EX_TOPMOST
    | win32con.WS_EX_NOACTIVATE
)

win32gui.SetLayeredWindowAttributes(
    hwnd,
    win32api.RGB(*TRANSPARENT),
    0,
    win32con.LWA_COLORKEY
)

# =========================================
# Camera Setup
# =========================================

if DXCAM_AVAILABLE:

    camera = dxcam.create(
        output_color="BGR"
    )

    camera.start(
        target_fps=FPS,
        video_mode=True
    )

else:

    sct = mss.mss()

    monitor = {
        "top": 0,
        "left": 0,
        "width": SCREEN_WIDTH,
        "height": SCREEN_HEIGHT
    }

# =========================================
# Clock
# =========================================

clock = pygame.time.Clock()

# =========================================
# Main Loop
# =========================================

running = True

while running:

    clock.tick_busy_loop(FPS)

    for event in pygame.event.get():

        if event.type == pygame.QUIT:
            running = False

    if keyboard.is_pressed("ctrl+q"):
        running = False

    win32gui.SetWindowPos(
        hwnd,
        win32con.HWND_TOPMOST,
        0,
        0,
        0,
        0,
        win32con.SWP_NOMOVE
        | win32con.SWP_NOSIZE
        | win32con.SWP_NOACTIVATE
    )

    # =========================================
    # Capture Frame
    # =========================================

    if DXCAM_AVAILABLE:

        frame = camera.get_latest_frame()

    else:

        img = np.array(
            sct.grab(monitor)
        )

        frame = cv2.cvtColor(
            img,
            cv2.COLOR_BGRA2BGR
        )

    if frame is None:
        continue

    # =========================================
    # Detect Table
    # =========================================

    if table_region is None:

        detected = detect_table(frame)

        if detected:
            table_region = detected

    if table_region is None:
        continue

    x = table_region["left"]
    y = table_region["top"]
    w = table_region["width"]
    h = table_region["height"]

    table = frame[y:y+h, x:x+w]

    if table.size == 0:
        continue

    # =========================================
    # Bands
    # =========================================

    top_band = y + INNER_OFFSET
    bottom_band = y + h - INNER_OFFSET

    left_band = x + INNER_OFFSET
    right_band = x + w - INNER_OFFSET

    # =========================================
    # Resize
    # =========================================

    small = cv2.resize(
        table,
        None,
        fx=0.75,
        fy=0.75,
        interpolation=cv2.INTER_LINEAR
    )

    scale = 1 / 0.75

    # =========================================
    # Preprocessing
    # =========================================

    gray = cv2.cvtColor(
        small,
        cv2.COLOR_BGR2GRAY
    )

    gray = cv2.equalizeHist(gray)

    gray = cv2.GaussianBlur(
        gray,
        (5, 5),
        0
    )

    edges = cv2.Canny(
        gray,
        60,
        120
    )

    # =========================================
    # Detect Balls
    # =========================================

    circles = cv2.HoughCircles(
        edges,
        cv2.HOUGH_GRADIENT,
        dp=1.3,
        minDist=28,
        param1=90,
        param2=24,
        minRadius=7,
        maxRadius=15
    )

    raw_white = None
    raw_targets = []

    try:
        mx, my = win32api.GetCursorPos()
    except:
        mx, my = (0, 0)

    hovered_ball = None

    pockets = [

        (x + 25, y + 25),
        (x + w // 2, y + 15),
        (x + w - 25, y + 25),

        (x + 25, y + h - 25),
        (x + w // 2, y + h - 15),
        (x + w - 25, y + h - 25)
    ]

    # =========================================
    # Clear Screen
    # =========================================

    screen.fill(TRANSPARENT)

    # =========================================
    # Draw Bands
    # =========================================

    pygame.draw.rect(
        screen,
        CYAN,
        (
            left_band,
            top_band,
            right_band - left_band,
            bottom_band - top_band
        ),
        2
    )

    # =========================================
    # Draw Pockets
    # =========================================

    for idx, p in enumerate(pockets):

        aa_circle(
            screen,
            RED,
            p,
            14
        )

        txt = pocket_font.render(
            str(idx + 1),
            True,
            ORANGE
        )

        screen.blit(
            txt,
            (
                p[0] - 8,
                p[1] - 35 if idx < 3 else p[1] + 15
            )
        )

    # =========================================
    # Process Circles
    # =========================================

    if circles is not None:

        circles = np.round(
            circles[0, :]
        ).astype("int")

        for (cx, cy, r) in circles:

            cx = int(cx * scale + x)
            cy = int(cy * scale + y)
            r = int(r * scale)

            ignore = False

            for p in pockets:

                if distance((cx, cy), p) < 35:
                    ignore = True
                    break

            if ignore:
                continue

            pad = 3

            x1 = max(0, cx - x - r - pad)
            y1 = max(0, cy - y - r - pad)

            x2 = min(w, cx - x + r + pad)
            y2 = min(h, cy - y + r + pad)

            roi = table[y1:y2, x1:x2]

            if is_white_ball(roi):

                raw_white = (cx, cy)

            else:

                raw_targets.append((cx, cy))

            if distance((mx, my), (cx, cy)) < r + 8:

                hovered_ball = (cx, cy)

    # =========================================
    # White Ball
    # =========================================

    if raw_white:

        smooth_white = smooth(
            raw_white,
            smooth_white,
            SMOOTH_WHITE
        )

        aa_circle(
            screen,
            WHITE,
            smooth_white,
            BALL_RADIUS
        )

    # =========================================
    # Ball Tracking
    # =========================================

    updated_balls = {}

    if len(raw_targets) > 0:

        for bx, by in raw_targets:

            best_id = None
            best_dist = 999999

            for ball_id, old_pos in tracked_balls.items():

                d = distance(
                    (bx, by),
                    old_pos
                )

                if d < best_dist and d < 35:

                    best_dist = d
                    best_id = ball_id

            if best_id is not None:

                old = tracked_balls[best_id]

                nx = old[0] + (
                    bx - old[0]
                ) * TRACK_SMOOTH

                ny = old[1] + (
                    by - old[1]
                ) * TRACK_SMOOTH

                updated_balls[best_id] = (
                    nx,
                    ny
                )

            else:

                updated_balls[next_ball_id] = (
                    bx,
                    by
                )

                next_ball_id += 1

    tracked_balls = updated_balls

    # =========================================
    # Draw Balls
    # =========================================

    for ball_id, sb in tracked_balls.items():

        color = YELLOW

        if locked_ball:

            if distance(sb, locked_ball) < 10:
                color = BLUE

        aa_circle(
            screen,
            color,
            sb,
            BALL_RADIUS
        )

    # =========================================
    # Lock Ball
    # =========================================

    if keyboard.is_pressed("z"):

        current_time = time.time()

        if current_time - last_lock_time > 0.25:

            if hovered_ball and len(tracked_balls) > 0:

                locked_ball = min(
                    tracked_balls.values(),
                    key=lambda b: distance(
                        b,
                        hovered_ball
                    )
                )

                last_lock_time = current_time

    # =========================================
    # Unlock Ball
    # =========================================

    if keyboard.is_pressed("x"):

        locked_ball = None

    # =========================================
    # Pocket Selection
    # =========================================

    if keyboard.is_pressed("1"):
        selected_pocket = 0

    elif keyboard.is_pressed("2"):
        selected_pocket = 1

    elif keyboard.is_pressed("3"):
        selected_pocket = 2

    elif keyboard.is_pressed("4"):
        selected_pocket = 3

    elif keyboard.is_pressed("5"):
        selected_pocket = 4

    elif keyboard.is_pressed("6"):
        selected_pocket = 5

    elif keyboard.is_pressed("0"):
        selected_pocket = None

    # =========================================
    # Aim System
    # =========================================

    if smooth_white and locked_ball:

        if selected_pocket is not None:

            target_pocket = pockets[selected_pocket]

        else:

            target_pocket = min(
                pockets,
                key=lambda p: distance(
                    locked_ball,
                    p
                )
            )

        gp = ghost_ball(
            locked_ball,
            target_pocket,
            BALL_RADIUS
        )

        smooth_ghost = smooth(
            gp,
            smooth_ghost,
            SMOOTH_GHOST
        )

        white_pos = (
            int(smooth_white[0]),
            int(smooth_white[1])
        )

        ghost_pos = (
            int(smooth_ghost[0]),
            int(smooth_ghost[1])
        )

        lock_pos = (
            int(locked_ball[0]),
            int(locked_ball[1])
        )

        # =========================================
        # Main Aim Line
        # =========================================

        pygame.draw.line(
            screen,
            WHITE,
            white_pos,
            ghost_pos,
            2
        )

        # =========================================
        # Pocket Line
        # =========================================

        pygame.draw.line(
            screen,
            YELLOW,
            lock_pos,
            (
                int(target_pocket[0]),
                int(target_pocket[1])
            ),
            2
        )

        # =========================================
        # Ghost Ball
        # =========================================

        aa_circle(
            screen,
            WHITE,
            ghost_pos,
            BALL_RADIUS
        )

        # =========================================
        # Reflection Line
        # =========================================

        dx = lock_pos[0] - ghost_pos[0]
        dy = lock_pos[1] - ghost_pos[1]

        dist = math.hypot(dx, dy)

        if dist > 0:

            rx = lock_pos[0] + (
                dx / dist
            ) * 300

            ry = lock_pos[1] + (
                dy / dist
            ) * 300

            pygame.draw.line(
                screen,
                PINK,
                lock_pos,
                (
                    int(rx),
                    int(ry)
                ),
                2
            )

    # =========================================
    # Text
    # =========================================

    screen.blit(
        cached_text,
        (x + 10, y - 30)
    )

    # =========================================
    # Update Display
    # =========================================

    pygame.display.update()

# =========================================
# Exit
# =========================================

if DXCAM_AVAILABLE:
    camera.stop()

pygame.quit()

sys.exit()
