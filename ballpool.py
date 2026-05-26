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

# إعداد أبعاد الشاشة بالكامل
SCREEN_WIDTH = win32api.GetSystemMetrics(0)
SCREEN_HEIGHT = win32api.GetSystemMetrics(1)

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
    lower_white = np.array([0, 0, 180]) # توسيع النطاق لضمان لقطة دقيقة
    upper_white = np.array([180, 40, 255])
    mask = cv2.inRange(hsv, lower_white, upper_white)
    white_ratio = np.sum(mask == 255) / mask.size
    return white_ratio > 0.45

def get_ghost_ball_position(target_ball, pocket, ball_radius):
    dx = target_ball[0] - pocket[0]
    dy = target_ball[1] - pocket[1]
    distance = math.sqrt(dx**2 + dy**2)
    if distance == 0:
        return target_ball
    ratio = (distance + (ball_radius * 2)) / distance
    ghost_x = pocket[0] + dx * ratio
    ghost_y = pocket[1] + dy * ratio
    return (int(ghost_x), int(ghost_y))

def detect_table_bounds(frame):
    """التعرف التلقائي على حدود طاولة البلياردو (الخضراء أو الزرقاء)"""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    # نطاق الألوان لطاولات البلياردو (الأزرق والأخضر)
    lower_table = np.array([35, 40, 40])
    upper_table = np.array([130, 255, 255])
    
    mask = cv2.inRange(hsv, lower_table, upper_table)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if contours:
        # أخذ أكبر مساحة تم العثور عليها وهي الطاولة بالتأكيد
        largest_contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest_contour) > 50000: # حد أدنى للتأكد أنها الطاولة
            x, y, w, h = cv2.boundingRect(largest_contour)
            return {"top": y, "left": x, "width": w, "height": h}
            
    # إعدادات افتراضية كاملة في حال لم يتم رصد الطاولة في أول جزء من الثانية
    return {"top": 0, "left": 0, "width": SCREEN_WIDTH, "height": SCREEN_HEIGHT}

def main():
    global locked_ball_center
    
    pygame.init()
    pygame.font.init()
    font = pygame.font.SysFont("Arial", 18, bold=True)
    
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.NOFRAME)
    hwnd = pygame.display.get_wm_info()['window']
    
    styles = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    new_styles = styles | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOPMOST
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, new_styles)
    
    win32gui.SetLayeredWindowAttributes(hwnd, win32api.RGB(*TRANSPARENT_COLOR), 0, win32con.LWA_COLORKEY)
    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)

    clock = pygame.time.Clock()
    full_monitor = {"top": 0, "left": 0, "width": SCREEN_WIDTH, "height": SCREEN_HEIGHT}

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

            # 1. التقاط كامل الشاشة لتحليل مكان الطاولة أولاً
            full_img = np.array(sct.grab(full_monitor))
            full_frame = cv2.cvtColor(full_img, cv2.COLOR_BGRA2BGR)
            
            # تحديد إحداثيات الطاولة فقط
            table = detect_table_bounds(full_frame)
            
            # قص صورة الطاولة للعمل عليها بشكل مخصص وسريع جداً
            table_frame = full_frame[table["top"]:table["top"]+table["height"], table["left"]:table["left"]+table["width"]]
            
            if table_frame.size == 0:
                continue

            gray = cv2.cvtColor(table_frame, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (7, 7), 1.5) # تعديل الفلتر لتحسين تباين الكرات
            
            # 2. تحسين معايير رصد الدوائر لتشمل جميع الكرات وتتجاهل الضوضاء بالخارج
            circles = cv2.HoughCircles(
                blurred, cv2.HOUGH_GRADIENT, dp=1.2, minDist=20,
                param1=45, param2=22, minRadius=10, maxRadius=30
            )

            # حساب مواقع الجيوب الستة ديناميكياً بناءً على أبعاد الطاولة المكتشفة تلقائياً
            pockets = [
                (table["left"] + 30, table["top"] + 30),                                # علوي يسار
                (table["left"] + table["width"] // 2, table["top"] + 25),               # علوي وسط
                (table["left"] + table["width"] - 30, table["top"] + 30),               # علوي يمين
                (table["left"] + 30, table["top"] + table["height"] - 30),              # سفلي يسار
                (table["left"] + table["width"] // 2, table["top"] + table["height"] - 25), # سفلي وسط
                (table["left"] + table["width"] - 30, table["top"] + table["height"] - 30)  # سفلي يمين
            ]

            # رسم الجيوب المكتشفة ديناميكياً
            for pocket in pockets:
                pygame.draw.circle(screen, RED, pocket, 14, 2)

            white_ball_center = None
            hovered_ball = None
            detected_radius = 16 # نصف قطر افتراضي محسّن للعبة

            if circles is not None:
                circles = np.uint16(np.around(circles))
                for i in circles[0, :]:
                    # تحويل الإحداثيات من إحداثيات الجدول المقصوص إلى إحداثيات الشاشة الكاملة المطلقة
                    cx = int(i[0]) + table["left"]
                    cy = int(i[1]) + table["top"]
                    r = int(i[2])
                    ball_center = (cx, cy)

                    y1, y2 = max(0, int(i[1])-r), min(table["height"], int(i[1])+r)
                    x1, x2 = max(0, int(i[0])-r), min(table["width"], int(i[0])+r)
                    ball_roi = table_frame[y1:y2, x1:x2]

                    if is_white_ball(ball_roi):
                        white_ball_center = ball_center
                        detected_radius = r
                        pygame.draw.circle(screen, WHITE, ball_center, r, 2)
                    else:
                        pygame.draw.circle(screen, YELLOW, ball_center, r, 1)

                    if calculate_distance((mx, my), ball_center) <= r:
                        hovered_ball = ball_center
                        pygame.draw.circle(screen, BLUE, ball_center, r + 4, 2)

            if keyboard.is_pressed('z') and hovered_ball is not None:
                locked_ball_center = hovered_ball

            # 3. رسم خطوط التحليل والمحاكاة الاحترافية (مطابقة لـ Screenshot_18)
            if locked_ball_center:
                best_pocket = None
                min_distance = float('inf')
                for pocket in pockets:
                    dist = calculate_distance(locked_ball_center, pocket)
                    if dist < min_distance:
                        min_distance = dist
                        best_pocket = pocket

                if best_pocket:
                    ghost_pos = get_ghost_ball_position(locked_ball_center, best_pocket, detected_radius)
                    
                    # خط المسار المستهدف (أصفر) نحو البوكت
                    pygame.draw.line(screen, YELLOW, locked_ball_center, best_pocket, 3)
                    pygame.draw.circle(screen, YELLOW, locked_ball_center, detected_radius, 2)

                    # خط التوجيه الأبيض من الكرة البيضاء الحقيقية إلى الـ Ghost Ball
                    if white_ball_center:
                        pygame.draw.line(screen, WHITE, white_ball_center, ghost_pos, 2)
                        pygame.draw.circle(screen, WHITE, ghost_pos, detected_radius, 1)
                        pygame.draw.line(screen, WHITE, ghost_pos, locked_ball_center, 1)
                    
                    info_text = f"Esports AI | Target Ball: {locked_ball_center} -> Pocket: {best_pocket}"
                    text_surface = font.render(info_text, True, YELLOW)
                    screen.blit(text_surface, (table["left"] + 10, table["top"] - 30 if table["top"] > 40 else 20))

            pygame.display.update()
            clock.tick(60)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
