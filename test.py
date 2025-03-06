import cv2
for i in range(3):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        print(f"摄像头索引 {i} 可用")
        cap.release()