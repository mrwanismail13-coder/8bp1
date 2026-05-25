import cv2
import numpy as np
import mss
import math

# إعدادات التقاط الشاشة (يمكنك تعديل الإحداثيات لتناسب نافذة اللعبة)
# تركها هكذا يلتقط الربع العلوي الأيسر كمثال، أو الشاشة كاملة
monitor = {"top": 100, "left": 100, "width": 800, "height": 600}

def calculate_distance(p1, p2):
    """حساب المسافة الإقليدية بين نقطتين"""
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def analyze_billiards():
    with mss.mss() as sct:
        print("بدء التحليل... اضغط 'q' في أي وقت للخروج.")
        
        while True:
            # 1. التقاط الشاشة بسرعة عالية جداً
            img = np.array(sct.grab(monitor))
            
            # تحويل الصورة إلى BGR (لأن mss تلتقط بصيغة BGRA)
            frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # تنعيم الصورة لتقليل الضوضاء قبل رصد الدوائر
            blurred = cv2.GaussianBlur(gray, (9, 9), 2)
            
            # 2. التعرف على الكرات والبوكتات (Hough Circles)
            # تم ضبط البارامترات تقريبياً، يمكنك تعديلها حسب حجم الكرات في لعبتك
            circles = cv2.HoughCircles(
                blurred, 
                cv2.HOUGH_GRADIENT, 
                dp=1, 
                minDist=30, 
                param1=50, 
                param2=30, 
                minRadius=10, 
                maxRadius=40
            )
            
            # محاكاة لإحداثيات البوكتات (الجيوب الستة التقليدية بطاولة البلياردو)
            # ملاحظة للبحث: يفضل تحديدها يدوياً بناءً على أبعاد الطاولة في اللعبة
            pockets = [
                (20, 20),   (400, 15),   (780, 20),  # الجيوب العلوية
                (20, 580),  (400, 585),  (780, 580)  # الجيوب السفلية
            ]
            
            # رسم البوكتات على الشاشة للتوضيح
            for pocket in pockets:
                cv2.circle(frame, pocket, 15, (0, 0, 255), 2) # دوائر حمراء للجيوب
            
            if circles is not None:
                circles = np.uint16(np.around(circles))
                
                best_ball = None
                best_pocket = None
                min_distance = float('inf')
                
                # البحث عن أقرب (أسهل) كرة لأي جيب
                for i in circles[0, :]:
                    ball_center = (i[0], i[1])
                    ball_radius = i[2]
                    
                    # رسم دائرة خفيفة حول كل الكرات المرصودة كخطوة أولى
                    cv2.circle(frame, ball_center, ball_radius, (255, 255, 0), 1)
                    
                    for pocket in pockets:
                        dist = calculate_distance(ball_center, pocket)
                        
                        # هنا نحدد "الأسهل" بناءً على أقصر مسافة كمرحلة أولى
                        if dist < min_distance:
                            min_distance = dist
                            best_ball = ball_center
                            best_pocket = pocket
                
                # 3. رسم دائرة على الكرة الأسهل وربطها بالبوكت بذكر الإحداثيات
                if best_ball and best_pocket:
                    # رسم دائرة خضراء سميكة حول الكرة الأسهل
                    cv2.circle(frame, best_ball, 20, (0, 255, 0), 3)
                    
                    # رسم خط من منتصف الكرة إلى منتصف البوكت
                    cv2.line(frame, best_ball, best_pocket, (255, 0, 0), 2)
                    
                    # حساب وعرض الإحداثيات والمسافة على الشاشة
                    text = f"Ball: {best_ball} -> Pocket: {best_pocket} | Dist: {int(min_distance)}px"
                    cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            
            # عرض النافذة التحليلية الحية
            cv2.imshow("Esports Accessibility & Analysis Tool", frame)
            
            # كسر الحلقة عند الضغط على زر 'q'
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
        cv2.destroyAllWindows()

if __name__ == "__main__":
    analyze_billiards()
