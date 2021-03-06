import cv2
import numpy as np
import paddlehub as hub
from paddlehub.common.logger import logger
import time
import math
import os
import matplotlib.pyplot as plt 
import matplotlib.image as mpimg
import win32con
import win32api

#定义三个全局变量用于判断是否执行操作
#2020年4月17日00:18:30 看样子眨眼是不好检测了,先处理嘴吧
openMouse=0
openLeftEye=0
openRightEye=0

class HeadPostEstimation(object):
    """
    头部姿态识别
    """
    NOD_ACTION = 1
    SHAKE_ACTION = 2
    def __init__(self, face_detector=None):
        self.module = hub.Module(name="face_landmark_localization", face_detector_module=face_detector)
        # 头部3D关键点坐标
        self.model_points = np.array([
            [6.825897, 6.760612, 4.402142],
            [1.330353, 7.122144, 6.903745],
            [-1.330353, 7.122144, 6.903745],
            [-6.825897, 6.760612, 4.402142],
            [5.311432, 5.485328, 3.987654],
            [1.789930, 5.393625, 4.413414],
            [-1.789930, 5.393625, 4.413414],
            [-5.311432, 5.485328, 3.987654],
            [2.005628, 1.409845, 6.165652],
            [-2.005628, 1.409845, 6.165652],
            [2.774015, -2.080775, 5.048531],
            [-2.774015, -2.080775, 5.048531],
            [0.000000, -3.116408, 6.097667],
            [0.000000, -7.415691, 4.070434],
            [-7.308957, 0.913869, 0.000000],
            [7.308957, 0.913869, 0.000000],
            [0.746313,0.348381,6.263227],
            [0.000000,0.000000,6.763430],
            [-0.746313,0.348381,6.263227],
            ], dtype='float')

        # 点头动作index是0， 摇头动作index是1
        # 当连续30帧上下点头动作幅度超过15度时，认为发生了点头动作
        # 当连续30帧上下点头动作幅度超过45度时，认为发生了摇头动作，由于摇头动作较为敏感，故所需幅度更大
        self._index_action = {0:'nod', 1:'shake'}
        self._frame_window_size = 15
        self._pose_threshold = {0: 15/180 * math.pi,
                                1: 45/180 * math.pi}
        # 头部3D投影点
        self.reprojectsrc = np.float32([
            [10.0, 10.0, 10.0],
            [10.0, 10.0, -10.0], 
            [10.0, -10.0, -10.0],
            [10.0, -10.0, 10.0], 
            [-10.0, 10.0, 10.0], 
            [-10.0, 10.0, -10.0], 
            [-10.0, -10.0, -10.0],
            [-10.0, -10.0, 10.0]])
        # 头部3D投影点连线
        self.line_pairs = [
            [0, 1], [1, 2], [2, 3], [3, 0],
            [4, 5], [5, 6], [6, 7], [7, 4],
            [0, 4], [1, 5], [2, 6], [3, 7]
        ]

    @property
    def frame_window_size(self):
        return self._frame_window_size
    
    @frame_window_size.setter
    def frame_window_size(self, value):
        assert isinstance(value, int)
        self._frame_window_size = value

    @property
    def pose_threshold(self):
        return self._pose_threshold
    
    @pose_threshold.setter
    def pose_threshold(self, dict_value):
        assert list(dict_value.keys()) == [0,1,2]
        self._pose_threshold = dict_value

    def get_face_landmark(self, image):
        """
        预测人脸的68个关键点坐标
        images(ndarray): 单张图片的像素数据
        """
        try:
            # 选择GPU运行，use_gpu=True，并且在运行整个教程代码之前设置CUDA_VISIBLE_DEVICES环境变量
            res = self.module.keypoint_detection(images=[image], use_gpu=False)
            
            img = image

            tmp_img = image.copy()
            for index, point in enumerate(res[0]['data'][0]):
                # cv2.putText(img, str(index), (int(point[0]), int(point[1])), cv2.FONT_HERSHEY_COMPLEX, 3, (0,0,255), -1)
                cv2.circle(tmp_img, (int(point[0]), int(point[1])), 2, (0, 0, 255), -1)

            res_img_path = 'face_landmark.jpg'
            cv2.imwrite(res_img_path, tmp_img)

            img = mpimg.imread(res_img_path) 
            # 展示预测68个关键点结果
            #下面用于绘图
            # plt.figure(figsize=(10,10))
            # plt.imshow(img) 
            # plt.axis('off') 
            #plt.show()
            return True, res[0]['data'][0],img
        except Exception as e:
            logger.error("Get face landmark localization failed! Exception: %s " % e)
            return False, None , None
        
    def get_image_points_from_landmark(self, face_landmark):
        """
        从face_landmark_localization的检测结果抽取姿态估计需要的点坐标
        """
        #计算一个系数,鼻子顶部到下巴尖的长度为100
        coe = 1000/(face_landmark[8][1]-face_landmark[27][1])
        mouseSize = (face_landmark[67][1]-face_landmark[61][1])*coe
        # print("coe",coe)
        #print("leftEyeSize\t\t\t",(face_landmark[47][1]-face_landmark[43][1])*coe)
        # print("rightEyeSize\t",(face_landmark[40][1]-face_landmark[38][1])*coe)
        #print("mouseSize\t",mouseSize)
        global openMouse
        if mouseSize >= 20 :
            if openMouse == 0 :
                vk_code = 0x74
                win32api.keybd_event(vk_code,win32api.MapVirtualKey(vk_code,0),0,0)
                time.sleep(0.02)
                win32api.keybd_event(vk_code, win32api.MapVirtualKey(vk_code, 0), win32con.KEYEVENTF_KEYUP, 0)
                print("openMouseOnce")
            openMouse = 1 
        else:
            openMouse = 0

        # print("\neye38")
        # print(face_landmark[37])
        # print("eye42")
        # print(face_landmark[41])
        image_points = np.array([
            face_landmark[17], face_landmark[21], 
            face_landmark[22], face_landmark[26], 
            face_landmark[36], face_landmark[39], 
            face_landmark[42], face_landmark[45], 
            face_landmark[31], face_landmark[35],
            face_landmark[48], face_landmark[54],
            face_landmark[57], face_landmark[8],
            face_landmark[14], face_landmark[2], 
            face_landmark[32], face_landmark[33],
            face_landmark[34], 
            ], dtype='float')
        return image_points
    
    def caculate_pose_vector(self, image_points):
        """
        获取旋转向量和平移向量
        """
        # 相机视角
        center = (self.img_size[1]/2, self.img_size[0]/2)
        focal_length = center[0] / np.tan(60/ 2 * np.pi / 180)
        camera_matrix = np.array([
            [focal_length, 0, center[0]],
            [0, focal_length, center[1]],
            [0, 0, 1]],
            dtype = "float")
        # 假设没有畸变
        dist_coeffs = np.zeros((4,1))
        
        success, rotation_vector, translation_vector= cv2.solvePnP(self.model_points, 
                                                                   image_points,
                                                                   camera_matrix, 
                                                                   dist_coeffs)
                                                                   
        reprojectdst, _ = cv2.projectPoints(self.reprojectsrc, rotation_vector, translation_vector, camera_matrix, dist_coeffs)

        return success, rotation_vector, translation_vector, camera_matrix, dist_coeffs, reprojectdst

    def caculate_euler_angle(self, rotation_vector, translation_vector):
        """
        将旋转向量转换为欧拉角
        """
        rvec_matrix = cv2.Rodrigues(rotation_vector)[0]
        proj_matrix = np.hstack((rvec_matrix, translation_vector))
        euler_angles = cv2.decomposeProjectionMatrix(proj_matrix)[6]
        pitch, yaw, roll = [math.radians(_) for _ in euler_angles]
        return pitch, yaw, roll



    def classify_pose_in_euler_angles(self, video, poses=3):
        """
        根据欧拉角分类头部姿态(点头nod/摇头shake)
        video 表示不断产生图片的生成器
        pose=1 表示识别点头动作
        pose=2 表示识别摇头动作
        pose=3 表示识别点头和摇头动作
        """
        frames_euler = []
        self.nod_time = self.totate_time = self.shake_time = time.time()
        self.action_time = 0
        index_action ={0:[self.NOD_ACTION], 1:[self.SHAKE_ACTION]}
        plt.figure(figsize=(10,10))

        for index, img in enumerate(video(), start=1):
            #从这里可以得到每张图片,可以在这里调用图片操作方法
            
            # plt.imshow(img) 
            # plt.axis('off') 
            # plt.show()
            self.img_size = img.shape

            success, face_landmark,newImg = self.get_face_landmark(img)
            img=newImg 

            for i, action in enumerate(index_action):
                if i == 0:
                    index_action[action].append((20, int(self.img_size[0]/2 + 110)))
                elif i == 1:
                    index_action[action].append((120, int(self.img_size[0]/2 + 110)))

            if not success:
                logger.info("Get face landmark localization failed! Please check your image!")
                continue

            image_points = self.get_image_points_from_landmark(face_landmark)
            success, rotation_vector, translation_vector, camera_matrix, dist_coeffs, reprojectdst = self.caculate_pose_vector(image_points)
            
            if not success:
                logger.info("Get rotation and translation vectors failed!")
                continue

            # 画出投影正方体
            alpha=0.3
            if not hasattr(self, 'before'):
                self.before = reprojectdst
            else:
                reprojectdst = alpha * self.before + (1-alpha)* reprojectdst
            reprojectdst = tuple(map(tuple, reprojectdst.reshape(8, 2)))
            for start, end in self.line_pairs:
                cv2.line(img, reprojectdst[start], reprojectdst[end], (0, 0, 255))

            # 计算头部欧拉角
            pitch, yaw, roll = self.caculate_euler_angle(rotation_vector, translation_vector)
            cv2.putText(img, "pitch: " + "{:7.2f}".format(pitch), (20, int(self.img_size[0]/2 -10)), cv2.FONT_HERSHEY_SIMPLEX,
                        0.75, (0, 0, 255), thickness=2)
            cv2.putText(img, "yaw: " + "{:7.2f}".format(yaw), (20, int(self.img_size[0]/2 + 30) ), cv2.FONT_HERSHEY_SIMPLEX,
                        0.75, (0, 0, 255), thickness=2)
            cv2.putText(img, "roll: " + "{:7.2f}".format(roll), (20, int(self.img_size[0]/2 +70)), cv2.FONT_HERSHEY_SIMPLEX,
                        0.75, (0, 0, 255), thickness=2)
            for index, action in enumerate(index_action):
                cv2.putText(img, "{}".format(self._index_action[action]), index_action[action][1], 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (50, 50, 50), thickness=2)
            frames_euler.append([index, img, pitch, yaw, roll])

            # 转换成摄像头可显示的格式
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            final_action = None
            if len(frames_euler) > self.frame_window_size:
                # 比较当前头部动作欧拉角与过去的欧拉角，只有动作幅度幅度超过阈值，则判定发生相应的动作
                # picth值用来判断点头动作
                # yaw值用来判断摇头动作
                current = [pitch, yaw, roll]
                tmp = [abs(pitch), abs(yaw)]
                max_index = tmp.index(max(tmp))
                max_probability_action = index_action[max_index][0]
                for start_idx, start_img, p, y, r in frames_euler[0:int(self.frame_window_size/2)]:
                    start = [p, y, r]
                    if poses & max_probability_action and abs(start[max_index]-current[max_index]) >= self.pose_threshold[max_index]:
                        frames_euler = []
                        final_action = max_index
                        self.action_time = time.time()
                        yield {self._index_action[max_index]: [(start_idx, start_img), (index, img)]}
                        break
                else:
                    # 丢弃过时的视频帧
                    frames_euler.pop(0)
            # 动作判定发生则高亮显示0.5s
            if self.action_time !=0  and time.time() - self.action_time < 0.5:
                cv2.putText(img_rgb, "{}".format(self._index_action[max_index]), index_action[max_index][1], 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 255), thickness=2)
            
            # 本地显示预测视频框，AIStudio项目不支持显示视频框
            cv2.imshow('Pose Estimation', img_rgb)
            # 写入预测结果
            video_writer.write(img_rgb)


# 打开摄像头
capture  = cv2.VideoCapture(0) 
# capture  = cv2.VideoCapture('./test_sample.mov')
fps = capture.get(cv2.CAP_PROP_FPS)
size = (int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
        int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)))
# 将预测结果写成视频
video_writer = cv2.VideoWriter('result.mp4', cv2.VideoWriter_fourcc(*'mp4v'), fps, size)

def generate_image():
    while True:
        # frame_rgb即视频的一帧数据
        ret, frame_rgb = capture.read() 
        # 按q键即可退出
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        if frame_rgb is None:
            break
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
        yield frame_bgr
    capture.release()
    video_writer.release()
    cv2.destroyAllWindows()

head_post = HeadPostEstimation()
for res in head_post.classify_pose_in_euler_angles(video=generate_image, poses=HeadPostEstimation.NOD_ACTION | HeadPostEstimation.SHAKE_ACTION):
    print(list(res.keys()))