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

# الحصول على أبعاد الشاشة الحالية
SCREEN_WIDTH = win32api.GetSystemMetrics(0)
SCREEN_HEIGHT = win32api.GetSystemMetrics(1)

# الألوان المستخدمة في الرسم العائم
TRANSPARENT_COLOR = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 162, 232)
YELLOW = (255, 242, 0)
ORANGE = (255, 127, 39)

locked_ball_center = None
selected_pocket_index = None # لتخزين الجيب المختار يدوياً عبر الكيبورد

def calculate_distance(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def is_white_ball(roi):
    if roi is None or roi.size == 0:
        return False
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    lower_white = np.array([0, 0, 190])
    upper_white = np.array([180, 45, 255])
    mask = cv2.inRange(hsv, lower_white, upper_white)
    white_ratio = np.sum(mask == 255) / mask.size
    return white_ratio > 0.50

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

def is_line_blocked(p1, p2, obstacle_balls, current_radius):
    """التحقق برمجياً مما إذا كان هناك كرة عائق تقطع المسار المستقيم بين نقطتين"""
    for ball in obstacle_balls:
        # حساب المسافة العمودية من مركز كرة العائق إلى الخط المستقيم الممتد بين p1 و p2
        x0, y0 = ball
        x1, y1 = p1
        x2, y2 = p2
        
        # تجنب القسمة على صفر إذا كانت النقاط متطابقة
        line_len = calculate_distance(p1, p2)
        if line_len == 0:
            continue
            
        # حساب المسافة العمودية
        distance_to_line = abs((x2 - x1) * (y1 - y0) - (x1 - x0) * (y2 - y1)) / line_len
        
        # التأكد من أن كرة العائق تقع 'بين' النقطتين وليس خلفهما على نفس الامتداد
        dot_product = (x0 - x1) * (x2 - x1) + (y0 - y1) * (y2 - y1)
        if dot_product >= 0 and dot_product <= line_len**2:
            # إذا كانت المسافة العمودية أقل من قطر الكرة الكامل، فهذا يعني حدوث تصادم حتمي (عائق)
            if distance_to_line < (current_radius * 2):
                return True
    return False

def detect_table_bounds(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower_table = np.array([35, 40, 40])
    upper_table = np.array([130, 255, 255])
    
    mask = cv2.inRange(hsv, lower_table, upper_table)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if contours:
        largest_contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest_contour) > 40000:
            x, y, w, h = cv2.boundingRect(largest_contour)
            return {"top": y, "left": x, "width": w, "height": h}
            
    return {"top": 0, "left": 0, "width": SCREEN_WIDTH, "height": SCREEN_HEIGHT}

def main():
    global locked_ball_center, selected_pocket_index
    
    pygame.init()
    pygame.font.init()
    font = pygame.font.SysFont("Arial", 18, bold=True)
    pocket_font = pygame.font.SysFont("Arial", 22, bold=True) # خط كبير وواضح لأرقام الجيوب
    
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

            # الاستماع لأزرار الأرقام من 1 إلى 6 لتحديد الجيب يدوياً
            for n in range(1, 7):
                if keyboard.is_pressed(str(n)):
                    selected_pocket_index = n - 1 # تحويلها لفهرس مصفوفة (0 إلى 5)
            
            # إعادة التوجيه للوضع التلقائي عند ضغط مفتاح صفر '0'
            if keyboard.is_pressed('0'):
                selected_pocket_index = None

            screen.fill(TRANSPARENT_COLOR)
            mx, my = win32api.GetCursorPos()

            full_img = np.array(sct.grab(full_monitor))
            full_frame = cv2.cvtColor(full_img, cv2.COLOR_BGRA2BGR)
            
            table = detect_table_bounds(full_frame)
            table_frame = full_frame[table["top"]:table["top"]+table["height"], table["left"]:table["left"]+table["width"]]
            
            if table_frame.size == 0:
                continue

            gray = cv2.cvtColor(table_frame, cv2.COLOR_BGR2GRAY)
            filtered = cv2.bilateralFilter(gray, 9, 75, 75)
            
            circles = cv2.HoughCircles(
                filtered, cv2.HOUGH_GRADIENT, dp=1, minDist=25,
                param1=50, param2=32, minRadius=12, maxRadius=24
            )

            # توزيع الجيوب الستة ديناميكياً على الطاولة
            pockets = [
                (table["left"] + 25, table["top"] + 25),                       # 1: علوي يسار
                (table["left"] + table["width"] // 2, table["top"] + 15),      # 2: علوي وسط
                (table["left"] + table["width"] - 25, table["top"] + 25),      # 3: علوي يمين
                (table["left"] + 25, table["top"] + table["height"] - 25),     # 4: سفلي يسار
                (table["left"] + table["width"] // 2, table["top"] + table["height"] - 15), # 5: سفلي وسط
                (table["left"] + table["width"] - 25, table["top"] + table["height"] - 25)  # 6: سفلي يمين
            ]

            # رسم الجيوب الستة وترقيمها مباشرة على الشاشة
            for idx, pocket in enumerate(pockets):
                pygame.draw.circle(screen, RED, pocket, 15, 2)
                # عرض أرقام الجيوب (1-6) بلون برتقالي مميز بجانب كل جيب لسهولة التوجيه
                p_text = pocket_font.render(str(idx + 1), True, ORANGE)
                screen.blit(p_text, (pocket[0] - 8, pocket[1] - 35 if idx < 3 else pocket[1] + 15))

            white_ball_center = None
            hovered_ball = None
            all_other_balls = [] # مصفوفة لتخزين مواقع الكرات الأخرى لفحص العوائق
            detected_radius = 16

            if circles is not None:
                circles = np.uint16(np.around(circles))
                for i in circles[0, :]:
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
                        # إضافة الكرات الملونة العادية إلى قائمة فحص العوائق (باستثناء الكرة المستهدفة الحالية لاحقاً)
                        all_other_balls.append(ball_center)

                    if calculate_distance((mx, my), ball_center) <= r:
                        hovered_ball = ball_center
                        pygame.draw.circle(screen, BLUE, ball_center, r + 4, 2)

            if keyboard.is_pressed('z') and hovered_ball is not None:
                locked_ball_center = hovered_ball

            if locked_ball_center:
                # تصفية الكرات العوائق لكي لا نعتبر الكرة المستهدفة نفسها عائقاً أمام مسارها
                obstacle_balls = [b for b in all_other_balls if b != locked_ball_center]
                
                # تحديد الجيب المستهدف (إما يدوياً بالرقم المكبوس، أو تلقائياً الأقرب)
                best_pocket = None
                if selected_pocket_index is not None and selected_pocket_index < len(pockets):
                    best_pocket = pockets[selected_pocket_index]
                else:
                    # الحساب التلقائي الافتراضي لأقرب جيب
                    min_distance = float('inf')
                    for pocket in pockets:
                        dist = calculate_distance(locked_ball_center, pocket)
                        if dist < min_distance:
                            min_distance = dist
                            best_pocket = pocket

                if best_pocket:
                    ghost_pos = get_ghost_ball_position(locked_ball_center, best_pocket, detected_radius)
                    
                    # خط المسار المستهدف من الكرة المحددة إلى الجيب (أصفر)
                    pygame.draw.line(screen, YELLOW, locked_ball_center, best_pocket, 3)
                    pygame.draw.circle(screen, YELLOW, locked_ball_center, detected_radius, 2)

                    # خط التوجيه والـ Ghost Ball من الكرة البيضاء
                    if white_ball_center:
                        # فحص العوائق: هل توجد أي كرة تقف حائلاً بين البيضاء وموقع الـ Ghost Ball؟
                        blocked = is_line_blocked(white_ball_center, ghost_pos, obstacle_balls, detected_radius)
                        
                        if blocked:
                            # إذا وجد عائق، يتم صبغ الخط باللون الأحمر الناري للتحذير الهندسي
                            pygame.draw.line(screen, RED, white_ball_center, ghost_pos, 3)
                            pygame.draw.circle(screen, RED, ghost_pos, detected_radius, 2)
                            status_text = "PATH BLOCKED! (عائق مكتشف)"
                            text_color = RED
                        else:
                            # إذا كان المسار خالياً ونظيفاً، يُرسم باللون الأبيض المعتاد
                            pygame.draw.line(screen, WHITE, white_ball_center, ghost_pos, 2)
                            pygame.draw.circle(screen, WHITE, ghost_pos, detected_radius, 1)
                            status_text = "CLEAR PATH (مسار مفتوح)"
                            text_color = GREEN
                            
                        pygame.draw.line(screen, WHITE, ghost_pos, locked_ball_center, 1)
                    
                    # عرض البيانات النصية وحالة المسار في الأعلى
                    mode_text = f"Manual Pocket: {selected_pocket_index + 1}" if selected_pocket_index is not None else "Auto-Pocket"
                    info_text = f"Billiards AI | Mode: {mode_text} | Status: {status_text}"
                    text_surface = font.render(info_text, True, text_color)
                    screen.blit(text_surface, (table["left"] + 10, table["top"] - 30 if table["top"] > 40 else 20))

            pygame.display.update()
            clock.tick(60)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
