import sys
import cv2
import win32gui
import win32con
import logging
import platform
import numpy as np
from datetime import datetime
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import QTimer, Qt, QPoint
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QSlider
logging.basicConfig(level=logging.INFO)

if platform.system() == "Windows":
    from win32gui import FindWindow, ShowWindow
    from win32con import SW_HIDE, SW_SHOW
else:
    def FindWindow(cls, title):return 0
    def ShowWindow(hwnd, cmd_show):pass
class VideoPlayer(QWidget):

    DEFAULT_ROI = (100, 100, 200, 320) # 默认ROI
    CHANGE_THRESHOLD = 30000 # 默认阈值
    def __init__(self): # 初始化
        super().__init__() # 调用父类初始化
        self.enable_change_detection = True # 启用变化检测

        # 打开摄像头
        self.cap = cv2.VideoCapture(0) # 打开摄像头
        if not self.cap.isOpened(): # 如果摄像头未能成功打开
            raise RuntimeError("摄像头未能成功打开，请检查设备") # 退出程序

        self.hide_windows = False # 隐藏窗口
        self.window_handle = -1 # 窗口句柄

        # 设置窗口初始信息
        self.setGeometry(100, 100, 200, 320)  # 自行修改窗口尺寸，适配下面的画面展示
        self.setWindowTitle('Video Player') # 窗口标题
        self.label = QLabel(self) # 标签
        self.slider = QSlider(Qt.Horizontal) # 滑动条
        self.slider.setRange(10, 99) # 设置滑动条范围
        self.slider.setTickInterval(5) # 刻度间隔
        self.slider.setTickPosition(QSlider.TicksBelow) # 刻度位置
        self.slider.setValue(40) # 设置初始值
        self.set_opacity(self.slider.value()) # 设置透明度
        self.slider.valueChanged.connect(self.set_opacity_and_update_label) # 连接滑动条值改变事件
        self.opacity_label = QLabel(str(self.slider.value()), self) # 标签
        opacity_layout = QHBoxLayout() # 水平布局
        opacity_layout.addWidget(self.slider) # 添加滑动条
        opacity_layout.addWidget(self.opacity_label) # 添加标签
        layout = QVBoxLayout() # 垂直布局
        layout.addLayout(opacity_layout) # 添加水平布局
        layout.addWidget(self.label) # 添加标签
        self.setLayout(layout) # 设置布局
        self.setWindowFlag(Qt.FramelessWindowHint) # 设置无边框
        self.setWindowFlag(Qt.WindowStaysOnTopHint) # 设置窗口置顶
        self.drag_position = QPoint() # 拖动位置
        self.roi = self.DEFAULT_ROI # 设置ROI
        self._init_ui() # 初始化UI
        self._init_timers() # 初始化定时器

        # 用于存储上一帧的ROI，进行对比
        self.previous_roi = None # 上一帧的ROI
        self.show() # 显示窗口
    def _init_timers(self):
        # 创建定时器
        self.timer = QTimer(self) # 创建定时器
        self.timer.timeout.connect(self.show_frame) # 连接定时器超时事件
        self.timer.start(30) # 每隔30毫秒调用一次

        self.change_detected_timer = QTimer(self) # 创建定时器
        self.change_detected_timer.setSingleShot(True) # 设置单次触发
        self.change_detected_timer.timeout.connect(self.reset_hide_window) # 连接定时器超时事件

    # 按下 ESC 键，关闭应用
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape: # 按下 ESC 键
            self.close() # 关闭应用

    # 设置窗体透明度
    def set_opacity_and_update_label(self, value):
        self.set_opacity(value) # 设置透明度
        self.opacity_label.setText(str(value)) # 更新标签

    # 将滑动条的值映射到0.1-1.0的范围
    def set_opacity(self, value):
        opacity = value / 100.0 # 透明度
        self.setWindowOpacity(opacity) # 设置窗口透明度

    # 鼠标可以拖动窗体
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft() # 拖动位置
            event.accept() # 接受事件

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position) # 移动窗体
            event.accept() # 接受事件
    # 从摄像头获取画面
    def show_frame(self):

        ret, frame = self.cap.read() # 读取摄像头画面
        if ret and self.enable_change_detection:
            # 获取指定区域的画面
            # 这是楼主环境下需要监控的区域大小，请自行调整
            x, y, w, h = self.roi # 指定区域
            roi = frame[y:y + h, x:x + w] # 获取指定区域的画面

            # 在这里对ROI进行翻转、镜像等处理
            # roi = cv2.flip(roi, 1)  # 1表示水平翻转
            roi = cv2.rotate(roi, cv2.ROTATE_180)  # 旋转180度
            roi = cv2.resize(roi, (w//2, h//2))# 缩小一半

            # 变化检测
            if self.previous_roi is not None:
                # 计算两帧之间的差异
                diff = cv2.absdiff(self.previous_roi, roi)
                gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
                _, thresh = cv2.threshold(gray_diff, 30, 255, cv2.THRESH_BINARY)
                change_detected = np.sum(thresh) > 30000  # 预警值
                if change_detected:
                    # 触发特定动作
                    self.on_change_detected(np.sum(thresh))

                # 叠加差异图像到原始视频帧上
                diff_image = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
                overlay = cv2.addWeighted(roi, 0.7, diff_image, 0.3, 0)

                # 获取当前时间并添加到图像上
                cv2.putText(overlay, f"{datetime.now()}", (4, 10), cv2.FONT_HERSHEY_SIMPLEX, 0.37, (255, 255, 255), 1)
                # 添加 np.sum(thresh) 和 self.hide_windows 的值
                hide_windows_status = f'{"Hidden" if self.hide_windows else "Visible"} thresh: {np.sum(thresh)}'
                text_color = (0, 0, 255) if change_detected else (255, 255, 255)
                cv2.putText(overlay, f'{hide_windows_status}', (4, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.4, text_color, 1)

                # 使用叠加后的图像
                display_image = overlay
            else:
                display_image = roi

            # 更新上一帧
            self.previous_roi = roi

            rgb_image = cv2.cvtColor(display_image, cv2.COLOR_BGR2RGB)  # 转换颜色通道
            h, w, ch = rgb_image.shape # 获取图像的形状
            bytes_per_line = ch * w # 每行的字节数
            q_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888) # 创建QImage对象
            pixmap = QPixmap.fromImage(q_image) # 从QImage对象创建QPixmap对象
            self.label.setPixmap(pixmap) # 设置标签的图像

    # 这里可以执行你想要的特定动作
    def on_change_detected(self, value): # 检测到变化
        logging.info(f"{datetime.now()}  检测到变化！阈值：{value}") # 打印检测到的变化
        if not self.hide_windows: # 如果窗口未隐藏
            self.hide_windows = True # 隐藏窗口
            logging.info(f'{datetime.now()}  hide_windows:{"隐藏" if self.hide_windows else "可见"}')
            self.hide_other_window()  # 隐藏指定窗口
        self.change_detected_timer.start(30000)  # 启动30秒定时器
        self.setWindowTitle(f'Video Player - {"隐藏" if self.hide_windows else "可见"}')

    # 替换为您要隐藏的窗口的信息
    def hide_other_window(self):
        window_class = None # 窗口类
        window_title = "无标题 - 记事本" # 窗口标题
        # 查找窗口句柄
        self.hwnd = win32gui.FindWindow(window_class, window_title) # 查找窗口句柄
        if self.hwnd: # 如果窗口句柄存在
            # 隐藏窗口
            win32gui.ShowWindow(self.hwnd, win32con.SW_HIDE) # 隐藏窗口

    def reset_hide_window(self):
        self.hide_windows = False # 隐藏窗口
        logging.info(f'{datetime.now()}  hide_windows:{"隐藏" if self.hide_windows else "可见"}') # 打印隐藏窗口状态
        self.setWindowTitle('Video Player - 可见') # 设置窗口标题
        # 恢复窗口
        if self.hwnd: # 如果窗口句柄存在
            win32gui.ShowWindow(self.hwnd, win32con.SW_SHOW) # 显示窗口

    # 退出程序
    def closeEvent(self, event):
        self.timer.stop() # 停止定时器
        self.cap.release() # 释放摄像头
        super().closeEvent(event) # 调用父类关闭事件


if __name__ == '__main__':
    app = QApplication(sys.argv) # 创建应用程序
    player = VideoPlayer() # 创建视频播放器

    # def update_frame():
    #     player.show_frame() # 显示帧
    #     # 递归调用自身，实现无限循环
    #     QTimer.singleShot(30, update_frame) # 每隔30毫秒调用一次

    # update_frame()  # 第一次调用
    sys.exit(app.exec_()) # 执行应用程序