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
    if roi is size == 0:
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
    
    # إعدادات التقاط الشاشة (يمكنك تعديلها لتطابق أبعاد شاشتك أو نافذة اللعبة بالكامل)
    monitor = {"top": 0, "left": 0, "width": 1920, "height": 1080}
    
    # إحداثيات الجيوب الستة الافتراضية للطاولة (قم بتعديلها لتناسب مكان الطاولة على شاشتك)
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

    # مصفوفة التقاط الماوس التلقائية عبر OpenCV
    mouse_x, mouse_y = 0, 0
    def mouse_callback(event, x, y, flags, param):
        nonlocal mouse_x, mouse_y
        if event == cv2.EVENT_MOUSEMOVE:
            mouse_x, mouse_y = x, y

    cv2.setMouseCallback(window_name, mouse_callback)

    with mss.mss() as sct:
        print("[INFO] الأداة تعمل الآن كـ Overlay عائم... اضغط 'q' للخروج و 'z' لتحديد الكرة بالماوس.")
        
        while True:
            img = np.array(sct.grab(monitor))
            frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (9, 9), 2)
            
            # رسم الجيوب الثابتة كدوائر حمراء رفيعة
            for pocket in pockets:
                cv2.circle(frame, pocket, 20, (0, 0, 255), 2)
            
            # رصد الدوائر (الكرات)
            circles = cv2.HoughCircles(
                blurred, cv2.HOUGH_GRADIENT, dp=1, minDist=30,
                param1=50, param2=25, minRadius=15, maxRadius=40
            )
            
            white_ball_center = None
            hovered_ball = None
            
            if circles is not None:
                circles = np.uint16(np.around(circles))
                
                for i in circles[0, :]:
                    # تحويل الإحداثيات إلى أرقام صحيح عادية لتجنب مشكلة نصوص البايثون في الصورة
                    cx, cy, r = int(i[0]), int(i[1]), int(i[2])
                    ball_center = (cx, cy)
                    
                    # استخراج منطقة الكرة لفحص لونها
                    y1, y2 = max(0, cy-r), min(monitor["height"], cy+r)
                    x1, x2 = max(0, cx-r), min(monitor["width"], cx+r)
                    ball_roi = frame[y1:y2, x1:x2]
                    
                    # 1. التعرف التلقائي على الكرة البيضاء
                    if is_white_ball(ball_roi):
                        white_ball_center = ball_center
                        cv2.circle(frame, ball_center, r, (255, 255, 255), 3) # دائرة بيضاء سميكة للكرة البيضاء
                        cv2.putText(frame, "CUE", (cx - 15, cy - r - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                    else:
                        cv2.circle(frame, ball_center, r, (0, 255, 255), 1) # دائرة صفراء لبقية الكرات
                    
                    # تحقق إذا كان الماوس يقف حالياً فوق هذه الكرة
                    if calculate_distance((mouse_x, mouse_y), ball_center) <= r:
                        hovered_ball = ball_center
                        # إضاءة مؤقتة باللون الأزرق للكرة التي يقف عليها الماوس للإرشاد
                        cv2.circle(frame, ball_center, r + 4, (255, 0, 0), 2)

            # 2. ميزة زر الـ Z: قفل التحديد على الكرة المطلوبة عند ضغط الزر
            if keyboard.is_pressed('z') and hovered_ball is not None:
                locked_ball_center = hovered_ball
                print(f"[LOCK] تم تحديد وقفل الكرة المستهدفة عند الإحداثيات: {locked_ball_center}")

            # 3. حساب المسار والمسافة من الكرة البيضاء -> المستهدفة -> أقرب بوكيت
            if locked_ball_center:
                # رسم علامة خضراء سميكة تثبت أن هذه هي الكرة المطلوبة للتحليل
                cv2.circle(frame, locked_ball_center, 25, (0, 255, 0), 3)
                cv2.putText(frame, "TARGET", (locked_ball_center[0] - 25, locked_ball_center[1] - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                # البحث عن أقرب وأسهل بوكيت للكرة المستهدفة المقفلة
                best_pocket = None
                min_distance = float('inf')
                for pocket in pockets:
                    dist = calculate_distance(locked_ball_center, pocket)
                    if dist < min_distance:
                        min_distance = dist
                        best_pocket = pocket
                
                # رسم خطوط التحليل الذكي
                if best_pocket:
                    # خط أزرق من الكرة المستهدفة إلى الجيب المستهدف
                    cv2.line(frame, locked_ball_center, best_pocket, (255, 0, 0), 3)
                    
                    # إذا تم رصد الكرة البيضاء، ارسم خط تكتيكي من البيضاء إلى الكرة المستهدفة
                    if white_ball_center:
                        cv2.line(frame, white_ball_center, locked_ball_center, (255, 255, 255), 2)
                    
                    # عرض الإحداثيات النظيفة بدون مشاكل Numpy المرة السابقة
                    info_text = f"Target Ball: {locked_ball_center} -> Pocket: {best_pocket} | Distance: {int(min_distance)}px"
                    cv2.putText(frame, info_text, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            # عرض الواجهة العائمة
            cv2.imshow(window_name, frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
        cv2.destroyAllWindows()

if __name__ == "__main__":
    start_analysis()
