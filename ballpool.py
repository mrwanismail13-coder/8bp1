import pygame
import win32gui
import win32con
import win32api
import mss
import cv2
import numpy as np
import math
import keyboard
import sys

# إعداد أبعاد الشاشة بالكامل لتغطية اللعبة
SCREEN_WIDTH = win32api.GetSystemMetrics(0)
SCREEN_HEIGHT = win32api.GetSystemMetrics(1)

# تعريف الألوان الأساسية للرسم
TRANSPARENT_COLOR = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 162, 232)
YELLOW = (255, 242, 0)

locked_ball_center = None

def calculate_distance(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def is_white_ball(roi):
    if roi is None or roi.size == 0:
        return False
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    lower_white = np.array([0, 0, 200])
    upper_white = np.array([180, 50, 255])
    mask = cv2.inRange(hsv, lower_white, upper_white)
    white_ratio = np.sum(mask == 255) / mask.size
    return white_ratio > 0.5

def get_ghost_ball_position(target_ball, pocket, ball_radius):
    """حساب نقطة التصادم التخيلية (Ghost Ball) بناءً على زاوية الهدف والجيب"""
    dx = target_ball[0] - pocket[0]
    dy = target_ball[1] - pocket[1]
    distance = math.sqrt(dx**2 + dy**2)
    if distance == 0:
        return target_ball
    
    # نقطة التصادم تقع على نفس خط الامتداد وتبعد مسافة ضعف نصف القطر (قطر كامل) عن مركز الكرة المستهدفة
    ratio = (distance + (ball_radius * 2)) / distance
    ghost_x = pocket[0] + dx * ratio
    ghost_y = pocket[1] + dy * ratio
    return (int(ghost_x), int(ghost_y))

def main():
    global locked_ball_center
    
    pygame.init()
    pygame.font.init()
    font = pygame.font.SysFont("Arial", 18, bold=True)
    
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.NOFRAME)
    hwnd = pygame.display.get_wm_info()['window']
    
    # ضبط خصائص النافذة لتصبح Overlay شفاف مئة بالمئة ويمرر الضغطات (Click-Through)
    styles = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    new_styles = styles | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOPMOST
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, new_styles)
    
    # تصحيح الخطأ: تم استبدال L_COLORKEY بـ LWA_COLORKEY المعتمد رسميًا في Win32
    win32gui.SetLayeredWindowAttributes(hwnd, win32api.RGB(*TRANSPARENT_COLOR), 0, win32con.LWA_COLORKEY)
    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)

    # إحداثيات الجيوب الستة الافتراضية لطاولتك (تعدل حسب اللعبة على الشاشة)
    pockets = [
        (100, 100),   (SCREEN_WIDTH // 2, 90),   (SCREEN_WIDTH - 100, 100),
        (100, SCREEN_HEIGHT - 100), (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 90), (SCREEN_WIDTH - 100, SCREEN_HEIGHT - 100)
    ]

    clock = pygame.time.Clock()
    monitor = {"top": 0, "left": 0, "width": SCREEN_WIDTH, "height": SCREEN_HEIGHT}

    with mss.mss() as sct:
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
            
            if keyboard.is_pressed('ctrl+q'):
                running = False
                break

            screen.fill(TRANSPARENT_COLOR)
            mx, my = win32api.GetCursorPos()

            # التقاط الشاشة المباشر
            img = np.array(sct.grab(monitor))
            frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (9, 9), 2)
            
            circles = cv2.HoughCircles(
                blurred, cv2.HOUGH_GRADIENT, dp=1, minDist=30,
                param1=50, param2=25, minRadius=15, maxRadius=40
            )

            # رسم الجيوب للإرشاد
            for pocket in pockets:
                pygame.draw.circle(screen, RED, pocket, 15, 2)

            white_ball_center = None
            hovered_ball = None
            detected_radius = 20 # نصف قطر افتراضي في حال لم يتم الرصد فوراً

            if circles is not None:
                circles = np.uint16(np.around(circles))
                for i in circles[0, :]:
                    cx, cy, r = int(i[0]), int(i[1]), int(i[2])
                    ball_center = (cx, cy)

                    y1, y2 = max(0, cy-r), min(SCREEN_HEIGHT, cy+r)
                    x1, x2 = max(0, cx-r), min(SCREEN_WIDTH, cx+r)
                    ball_roi = frame[y1:y2, x1:x2]

                    if is_white_ball(ball_roi):
                        white_ball_center = ball_center
                        detected_radius = r
                        pygame.draw.circle(screen, WHITE, ball_center, r, 2)
                    else:
                        pygame.draw.circle(screen, YELLOW, ball_center, r, 1)

                    if calculate_distance((mx, my), ball_center) <= r:
                        hovered_ball = ball_center
                        pygame.draw.circle(screen, BLUE, ball_center, r + 4, 2)

            # ميزة التقاط الهدف بالماوس
            if keyboard.is_pressed('z') and hovered_ball is not None:
                locked_ball_center = hovered_ball

            # محاكاة خطوط التحليل المتقدمة (مطابقة للصورة المرفقة)
            if locked_ball_center:
                # 1. إيجاد أقرب جيب للكرة المستهدفة المقفلة
                best_pocket = None
                min_distance = float('inf')
                for pocket in pockets:
                    dist = calculate_distance(locked_ball_center, pocket)
                    if dist < min_distance:
                        min_distance = dist
                        best_pocket = pocket

                if best_pocket:
                    # 2. حساب موقع الـ Ghost Ball (كرة التصادم التخيلية)
                    ghost_pos = get_ghost_ball_position(locked_ball_center, best_pocket, detected_radius)
                    
                    # 3. رسم خط المسار النهائي من الكرة المستهدفة إلى الجيب باللون الأصفر
                    pygame.draw.line(screen, YELLOW, locked_ball_center, best_pocket, 3)
                    pygame.draw.circle(screen, YELLOW, locked_ball_center, detected_radius, 2)
                    pygame.draw.circle(screen, YELLOW, best_pocket, 10, 2) # تبيين البوكت المستهدف

                    # 4. رسم خط التوجيه الأبيض من الكرة البيضاء الحقيقية إلى موقع الـ Ghost Ball
                    if white_ball_center:
                        pygame.draw.line(screen, WHITE, white_ball_center, ghost_pos, 2)
                        # رسم دائرة بيضاء منقطة أو خفيفة تمثل الـ Ghost Ball قبل التصادم
                        pygame.draw.circle(screen, WHITE, ghost_pos, detected_radius, 1)
                        # خط ارتداد وهمي بسيط لإيضاح زاوية الانحراف
                        pygame.draw.line(screen, WHITE, ghost_pos, locked_ball_center, 1)
                    
                    # عرض البيانات النصية البحثية بالأعلى
                    info_text = f"Esports Tool | Target: {locked_ball_center} -> Pocket: {best_pocket} | Distance: {int(min_distance)}px"
                    text_surface = font.render(info_text, True, YELLOW)
                    screen.blit(text_surface, (25, 25))

            pygame.display.update()
            clock.tick(60)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
