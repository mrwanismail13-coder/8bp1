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

# تعريف الألوان (نستخدم اللون الأسود كلون شفاف للخلفية)
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

def main():
    global locked_ball_center
    
    # 1. إعداد نافذة PyGame الشفافة بالكامل
    pygame.init()
    pygame.font.init()
    font = pygame.font.SysFont("Arial", 20, bold=True)
    
    # إنشاء النافذة بأبعاد الشاشة الكاملة وبدون حواف
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.NOFRAME)
    
    # الحصول على مقبض النافذة (HWND) لضبط خصائص ويندوز المتقدمة
    hwnd = pygame.display.get_wm_info()['window']
    
    # جعل النافذة عائمة فوق كل شيء (Always on Top) وشفافة وتمرر النقرات (Click-Through)
    styles = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    new_styles = styles | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOPMOST
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, new_styles)
    
    # تحديد اللون الأسود ليكون هو اللون الشفاف (أي شيء باللون الأسود لن يظهر وسيعرض اللعبة خلفه)
    win32gui.SetLayeredWindowAttributes(hwnd, win32api.RGB(*TRANSPARENT_COLOR), 0, win32con.L_COLORKEY)
    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)

    # إحداثيات الجيوب الستة الافتراضية لطاولتك (قم بتعديلها لتطابق أماكن الجيوب على شاشتك بدقة)
    pockets = [
        (100, 100),   (SCREEN_WIDTH // 2, 90),   (SCREEN_WIDTH - 100, 100),
        (100, SCREEN_HEIGHT - 100), (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 90), (SCREEN_WIDTH - 100, SCREEN_HEIGHT - 100)
    ]

    clock = pygame.time.Clock()
    monitor = {"top": 0, "left": 0, "width": SCREEN_WIDTH, "height": SCREEN_HEIGHT}

    with mss.mss() as sct:
        print("[INFO] الـ Overlay الشفاف يعمل الآن مباشرة فوق اللعبة! اضغط Z لتحديد الكرة و Ctrl+Q للخروج.")
        
        running = True
        while running:
            # التعامل مع أحداث PyGame لمنع تجمّد الأداة
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
            
            if keyboard.is_pressed('ctrl+q'):
                running = False
                break

            # تنظيف الشاشة بملئها باللون الشفاف (الأسود) في كل إطار
            screen.fill(TRANSPARENT_COLOR)

            # الحصول على الإحداثيات الحية للماوس مباشرة من ويندوز
            mx, my = win32api.GetCursorPos()

            # 2. التقاط الشاشة ومعالجتها برؤية حاسوبية فائقة السرعة في الخلفية
            img = np.array(sct.grab(monitor))
            frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (9, 9), 2)
            
            circles = cv2.HoughCircles(
                blurred, cv2.HOUGH_GRADIENT, dp=1, minDist=30,
                param1=50, param2=25, minRadius=15, maxRadius=40
            )

            # رسم الجيوب الستة للإرشاد كدوائر حمراء رقيقة مباشرة على الشاشة
            for pocket in pockets:
                pygame.draw.circle(screen, RED, pocket, 18, 2)

            white_ball_center = None
            hovered_ball = None

            if circles is not None:
                circles = np.uint16(np.around(circles))
                for i in circles[0, :]:
                    cx, cy, r = int(i[0]), int(i[1]), int(i[2])
                    ball_center = (cx, cy)

                    y1, y2 = max(0, cy-r), min(SCREEN_HEIGHT, cy+r)
                    x1, x2 = max(0, cx-r), min(SCREEN_WIDTH, cx+r)
                    ball_roi = frame[y1:y2, x1:x2]

                    # التعرف التلقائي على الكرة البيضاء ورسم دائرة بيضاء حولها مباشرة على شاشتك
                    if is_white_ball(ball_roi):
                        white_ball_center = ball_center
                        pygame.draw.circle(screen, WHITE, ball_center, r, 3)
                    else:
                        # رسم دائرة صفراء خفيفة جداً حول بقية الكرات لرصد الأداة
                        pygame.draw.circle(screen, YELLOW, ball_center, r,  1)

                    # فحص ما إذا كان ماوس اللاعب يقف فوق هذه الكرة حالياً
                    if calculate_distance((mx, my), ball_center) <= r:
                        hovered_ball = ball_center
                        pygame.draw.circle(screen, BLUE, ball_center, r + 4, 2)

            # 3. ميزة زر الـ Z للتحكم وتثبيت الكرة المستهدفة
            if keyboard.is_pressed('z') and hovered_ball is not None:
                locked_ball_center = hovered_ball

            # 4. الحساب الرياضي ورسم خط المسار النهائي فوق اللعبة بدون أي نوافذ
            if locked_ball_center:
                # رسم دائرة خضراء حول الكرة المستهدفة المقفلة
                pygame.draw.circle(screen, GREEN, locked_ball_center, 22, 3)
                
                # البحث عن أسهل وأقرب جيب للكرة المقفلة
                best_pocket = None
                min_distance = float('inf')
                for pocket in pockets:
                    dist = calculate_distance(locked_ball_center, pocket)
                    if dist < min_distance:
                        min_distance = dist
                        best_pocket = pocket

                if best_pocket:
                    # رسم مسار الكرة إلى الجيب (خط أزرق سميك واحترافي مباشر على شاشتك)
                    pygame.draw.line(screen, BLUE, locked_ball_center, best_pocket, 3)
                    
                    # رسم خط الربط التكتيكي من الكرة البيضاء إلى الكرة المستهدفة
                    if white_ball_center:
                        pygame.draw.line(screen, WHITE, white_ball_center, locked_ball_center, 2)

                    # كتابة البيانات التحليلية في زاوية الشاشة العلوية بشكل عائم ونظيف جداً
                    info_text = f"AI Analysis -> Target Ball: {locked_ball_center} | Pocket: {best_pocket} | Distance: {int(min_distance)}px"
                    text_surface = font.render(info_text, True, YELLOW)
                    screen.blit(text_surface, (20, 20))

            # تحديث شاشة العرض العائمة
            pygame.display.update()
            clock.tick(60) # تحديد معدل تحديث الأداة بـ 60 إطار في الثانية لضمان استقرار الأداء وسرعته

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
