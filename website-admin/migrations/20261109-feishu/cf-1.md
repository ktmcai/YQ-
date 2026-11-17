# YONIQ LINK CF\-1

**电机CANFD\-USB/UART\-USB快速调试器**

本产品需配合**YONIQ STUDIO**上位机使用，目的是帮助用户快速进行电机测试,参数标定以及固件升级等。

**产品近照**

![37fbc691f5a83e6e2a4f4723be5fc71d\.jpg](图片和附件/37fbc691f5a83e6e2a4f4723be5fc71d.jpg)



![50684fbacd923411ab2095035c9620d3\.jpg](图片和附件/50684fbacd923411ab2095035c9620d3.jpg)



![96d32a6056b4f023908e1b7541e2edce\.jpg](图片和附件/96d32a6056b4f023908e1b7541e2edce.jpg)



# 接口说明

YONIQ LINK CF\-1支持两种通讯模式：**CANFD**和**UART**

## CANFD\-USB模式

### 接线

### 说明

1. 使用此模式时请务必确认总线上的其它设备支持CANFD通讯，如果和不支持CANFD的设备通用会引发总线报错。

2. YONIQ LINK的默认波特率为1\+2M，因此只有电机的波特率设为1M或2M时才会支持使用调试器，否则会引发总线错误或收不到数据。（特别说明：电机波特率为1M时电机CANOPEN协议启用的是标准CAN，仲裁段和数据段均为1M，当电机波特率设为2M时电机CANOPEN协议使用的是CANFD格式，此时的波特率为1\+2M）。

3. 使用CANFD调试时请务必将调试器功能拨钮拨到CAN模式（120Ω，0Ω中的一个），且注意是否要添加终端电阻。

4. 每个电机的sysid和compid必须不同，sysid可选范围为**1:30**，compid可选范围：**1\-255**\.

## UART\-USB模式

### 接线

### 说明

1. 使用串口调试时请务必将调试器功能拨钮拨到串口模式。

# 连线示例



![0bed8834e99c9e1b6fdfef56be7b4aac\.jpg](图片和附件/0bed8834e99c9e1b6fdfef56be7b4aac.jpg)



![795b171ae15f9a3d8c8e551042c7354a\.jpg](图片和附件/795b171ae15f9a3d8c8e551042c7354a.jpg)

串口连接时仅能监控单个设备。



