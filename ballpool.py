import cv2
import numpy as np
import mss
import math
import keyboard # مكتبة لالتقاط الأزرار في الخلفية
import win32gui
import win32con

# متغيرات عالمية للتحكم بالكرة المستهدفة المقفلة
locked_ball_center = None

def calculate_distance(p1, p2):
    """حساب المسافة الإقليدية بين نقطتين"""
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def is_white_ball(roi):
    """التحقق إذا كانت الدائرة المرصودة هي الكرة البيضاء بناءً على نسبة سطوع اللون"""
    # تصحيح الخطأ المطبعي الفائت وضمان فحص حجم المصفوفة بشكل صحيح
    if roi is None or roi.size == 0:
        return False
    
    # تحويل منطقة الكرة إلى نظام HSV لفحص اللون الأبيض بدقة
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    
    # تصفية اللون الأبيض (سطوع عالي وتشبع لوني منخفض)
    lower_white = np.array([0, 0, 200])
    upper_white = np.array([180, 50, 255])
    mask = cv2.inRange(hsv, lower_white, upper_white)
    
    white_ratio = np.sum(mask == 255) / mask.size
    return white_ratio > 0.5 # إذا كان أكثر من 50% من الكرة أبيض

def start_analysis():
    global locked_ball_center
    
    # إعدادات التقاط الشاشة كاملة (1920x1080) كـ Overlay عائم
    monitor = {"top": 0, "left": 0, "width": 1920, "height": 1080}
    
    # إحداثيات الجيوب الستة الافتراضية للطاولة (قم بتعديلها لاحقاً لتناسب مكان طاولة لعبتك بالظبط)
    pockets = [
        (50, 50),     (960, 45),    (1870, 50),  # الجيوب العلوية
        (50, 1030),   (960, 1035),  (1870, 1030) # الجيوب السفلية
    ]

    window_name = "AI Billiards Analysis Tool (Floating)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    
    # جعل النافذة شفافة جزئياً وبدون حواف وعائمة فوق كل البرامج (Always on Top)
    hwnd = win32gui.FindWindow(None, window_name)
    if hwnd:
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 800, 600, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)

    # مصفوفة لتتبع إحداثيات حركة الماوس الحية داخل النافذة
    mouse_x, mouse_y = 0, 0
    def mouse_callback(event, x, y, flags, param):
        nonlocal mouse_x, mouse_y
        if event == cv2.EVENT_MOUSEMOVE:
            mouse_x, mouse_y = x, y

    cv2.setMouseCallback(window_name, mouse_callback)

    with mss.mss() as sct:
        print("[INFO] الأداة تعمل الآن بنجاح... اضغط 'q' للخروج و 'z' لتحديد الكرة بالماوس.")
        
        while True:
            # التقاط الشاشة فائق السرعة
            img = np.array(sct.grab(monitor))
            frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (9, 9), 2)
            
            # رسم الجيوب الثابتة كدوائر حمراء رفيعة
            for pocket in pockets:
                cv2.circle(frame, pocket, 20, (0, 0, 255), 2)
            
            # رصد الدوائر (الكرات) هندسياً
            circles = cv2.HoughCircles(
                blurred, cv2.HOUGH_GRADIENT, dp=1, minDist=30,
                param1=50, param2=25, minRadius=15, maxRadius=40
            )
            
            white_ball_center = None
            hovered_ball = None
            
            if circles is not None:
                circles = np.uint16(np.around(circles))
                
                for i in circles[0, :]:
                    # تحويل الإحداثيات إلى أرقام صحيح عادية (Int) لمنع تداخل نصوص بايثون على الشاشة
                    cx, cy, r = int(i[0]), int(i[1]), int(i[2])
                    ball_center = (cx, cy)
                    
                    # استخراج منطقة الكرة لفحص لونها
                    y1, y2 = max(0, cy-r), min(monitor["height"], cy+r)
                    x1, x2 = max(0, cx-r), min(monitor["width"], cx+r)
                    ball_roi = frame[y1:y2, x1:x2]
                    
                    # 1. التعرف التلقائي الذكي على الكرة البيضاء
                    if is_white_ball(ball_roi):
                        white_ball_center = ball_center
                        cv2.circle(frame, ball_center, r, (255, 255, 255), 3) # دائرة بيضاء سميكة
                        cv2.putText(frame, "CUE", (cx - 15, cy - r - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                    else:
                        cv2.circle(frame, ball_center, r, (0, 255, 255), 1) # دائرة صفراء خفيفة لبقية الكرات
                    
                    # تحقق إذا كان مؤشر الماوس يقف حالياً فوق نطاق هذه الكرة
                    if calculate_distance((mouse_x, mouse_y), ball_center) <= r:
                        hovered_ball = ball_center
                        # إضاءة توجيهية باللون الأزرق للكرة التي يقف عليها الماوس فوراً
                        cv2.circle(frame, ball_center, r + 4, (255, 0, 0), 2)

            # 2. ميزة زر الـ Z: قفل التتبع على الكرة الحالية عند ضغط الزر
            if keyboard.is_pressed('z') and hovered_ball is not None:
                locked_ball_center = hovered_ball
                print(f"[LOCK] تم قفل وتثبيت الكرة المستهدفة عند: {locked_ball_center}")

            # 3. حساب المسار والمسافة وعرض البيانات النظيفة بالكامل
            if locked_ball_center:
                # رسم علامة خضراء سميكة تثبت قفل الكرة المطلوبة للتحليل العلمي
                cv2.circle(frame, locked_ball_center, 25, (0, 255, 0), 3)
                cv2.putText(frame, "TARGET", (locked_ball_center[0] - 25, locked_ball_center[1] - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                # البحث التلقائي عن أقرب وأسهل بوكيت للكرة المستهدفة المقفلة
                best_pocket = None
                min_distance = float('inf')
                for pocket in pockets:
                    dist = calculate_distance(locked_ball_center, pocket)
                    if dist < min_distance:
                        min_distance = dist
                        best_pocket = pocket
                
                # رسم خطوط التحليل الرياضي للمسار
                if best_pocket:
                    # خط أزرق سميك من الكرة المستهدفة إلى الجيب (المسار النهائي)
                    cv2.line(frame, locked_ball_center, best_pocket, (255, 0, 0), 3)
                    
                    # إذا نجحت الأداة في رصد مكان الكرة البيضاء، ارسم خط ربط تكتيكي بينهما
                    if white_ball_center:
                        cv2.line(frame, white_ball_center, locked_ball_center, (255, 255, 255), 2)
                    
                    # صياغة البيانات وعرضها بشكل نصي نظيف ومقروء
                    info_text = f"Target Ball: {locked_ball_center} -> Pocket: {best_pocket} | Distance: {int(min_distance)}px"
                    cv2.putText(frame, info_text, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            # عرض الواجهة العائمة فوق كل التطبيقات والألعاب شاشتك
            cv2.imshow(window_name, frame)
            
            # الخروج الفوري عند ضغط زر 'q'
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
        cv2.destroyAllWindows()

if __name__ == "__main__":
    start_analysis()
