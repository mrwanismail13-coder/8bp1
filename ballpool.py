import cv2
import numpy as np
import mss
import math

def calculate_distance(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def start_analysis():
    # إعدادات التقاط الشاشة الافتراضية
    monitor = {"top": 100, "left": 100, "width": 800, "height": 600}
    
    # إحداثيات جيوب الطاولة الستة
    pockets = [
        (20, 20),   (400, 15),   (780, 20),  
        (20, 580),  (400, 585),  (780, 580)  
    ]

    with mss.mss() as sct:
        while True:
            img = np.array(sct.grab(monitor))
            frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (9, 9), 2)
            
            for pocket in pockets:
                cv2.circle(frame, pocket, 15, (0, 0, 255), 2)
            
            circles = cv2.HoughCircles(
                blurred, cv2.HOUGH_GRADIENT, dp=1, minDist=35,
                param1=50, param2=30, minRadius=12, maxRadius=35
            )
            
            if circles is not None:
                circles = np.uint16(np.around(circles))
                best_ball = None
                best_pocket = None
                min_distance = float('inf')
                
                for i in circles[0, :]:
                    ball_center = (i[0], i[1])
                    ball_radius = i[2]
                    cv2.circle(frame, ball_center, ball_radius, (255, 255, 0), 1)
                    
                    for pocket in pockets:
                        dist = calculate_distance(ball_center, pocket)
                        if dist < min_distance:
                            min_distance = dist
                            best_ball = ball_center
                            best_pocket = pocket
                
                if best_ball and best_pocket:
                    cv2.circle(frame, best_ball, 22, (0, 255, 0), 3)
                    cv2.line(frame, best_ball, best_pocket, (255, 0, 0), 2)
                    
                    info_text = f"Ball: {best_ball} -> Pocket: {best_pocket} | Dist: {int(min_distance)}px"
                    cv2.putText(frame, info_text, (15, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2)
            
            cv2.imshow("AI Billiards Analysis Tool", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        cv2.destroyAllWindows()

if __name__ == "__main__":
    start_analysis()
