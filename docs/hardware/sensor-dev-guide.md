# 绝影Lite3 感知开发要点

> 来源：绝影Lite3感知开发手册(beta) V2.2.3

## ROS 环境

### 版本支持
- ROS1 Melodic (Ubuntu 18.04)
- ROS2 Humble (Ubuntu 20.04+)

### 查看版本
```bash
# ROS1
echo $ROS_VERSION  # 输出: 1
rosversion -d      # 输出: melodic

# ROS2
echo $ROS_VERSION  # 输出: 2
ros2 --version
```

## 深度相机

### 驱动安装
```bash
# Intel RealSense (深度相机)
sudo apt install ros-$ROS_DISTRO-realsense2-camera
```

### 相机测试
```bash
# ROS1
roslaunch realsense2_camera rs_launch.py

# ROS2
ros2 launch realsense2_camera rs_launch.py
```

### 常用话题
| 话题 | 类型 | 说明 |
|------|------|------|
| /camera/color/image_raw | sensor_msgs/Image | 彩色图像 |
| /camera/depth/image_raw | sensor_msgs/Image | 深度图像 |
| /camera/infra1/image_raw | sensor_msgs/Image | 红外左图 |
| /camera/depth/points | pointcloud2/PointCloud2 | 点云 |

## 激光雷达

### 支持的雷达型号
- 速腾聚创 RS-LiDAR-16
- 禾赛 AT128
- 镭神 Clio16
- 其他 ROS 兼容雷达

### 驱动启动
```bash
# 速腾聚创
roslaunch rs_lidar_start start.launch

# 禾赛
roslaunch at128_driver start.launch
```

## SLAM 建图

### Cartographer (ROS1)
```bash
# 启动建图
roslaunch cartographer_ros offline_backpack_2d.launch

# 保存地图
rosrun cartographer_ros cartographer_pbstream_to_mapping_pbstream \
    -asset_basename=/tmp/map
```

### Nav2 (ROS2)
```bash
# 启动导航
ros2 launch nav2_bringup navigation_launch.py

# 建图
ros2 launch nav2_bringup cartographer_launch.py
```

## 识别跟随功能包

### 功能介绍
- 视觉目标识别
- 自动跟随
- 停障辅助

### 使用方法
```bash
# 启动跟随
roslaunch deeprobotics_follow follow.launch

# 停止跟随
rosservice call /deeprobotics_follow/stop_follow
```

### 二次开发
```python
# 订阅图像话题
image_sub = rospy.Subscriber('/camera/color/image_raw', Image, callback)

# 调用识别服务
result = rospy.ServiceProxy('/deeprobotics_follow/recognize', Recognize)
```

## 常用命令

```bash
# 查看所有话题
rostopic list

# 查看话题信息
rostopic info /camera/color/image_raw

# 查看消息内容
rostopic echo /camera/color/image_raw

# 录制数据
rosbag record -O map.bag /camera/color/image_raw /scan

# 播放数据
rosbag play map.bag
```

## 注意事项

1. 确保 ROS 版本与手册一致
2. 深度相机需要良好光照
3. 激光雷达需要稳定安装
4. 建图前确保环境光照充足
5. 注意电池电量，避免中途断电
