# 串口协议手册

# 连接方式

**串口TTL参数: **

****波特率：**`921600`**

bps数据位：**`8 `**

奇偶校验：`无` 

停止位：`1`

# mavlink协议了解

## 命令格式

同一总线上共可以挂载多达 255 个（视总线负载情况而定）驱动，为了防止总线冲突，每个驱动需要设置 不同的 ID，ID 编号为 0\~255。

主控通过总线向目标驱动发送命令帧（CMD），当对应 CompID 的设备收到命令后，会在 0\.25 ms 内 返回：

- 一条 ACK帧（执行确认）

- 或一条 消息帧（返回数据内容）

\(命令帧、ACK帧与消息帧之间的区别见下方“概念介绍”\)，帧报文封装格式如下：

### 协议封装格式

|**内容**|**字节长度**|**定义**|**备注**|
|---|---|---|---|
|**Magic**<br>****|1|包头<br>|0xFD|
|**Len**|1|数据长度|Payload长度|
|**Incompat\_flags**|1|无标志|0|
|**Compat\_flags**||无标志|0|
|**Seq**|1|包号|0\-255|
|**SysId \(sender\)**|1|发送端id|范围 1\~255|
|**CompId \(sender\)**|1|发送端组件id|0 \~255,默认0x19|
|**MSG\_ID\[0:2\]**|3|消息ID\(低位在前\)|详见“消息”部分|
|**Payload\[0\-255\]**|0\-255|消息内容|依消息解析|
|**Checksum**|2|校验\*（低位在前）|详见“校验部分”|

Payload 空字节截断机制： 

如果 Payload 的结尾部分有 0x00，在消息发送前，将会对 Payload 尾部连续的 0x00 进行丢弃， 只发送前面的部分，从而节省带宽。因此，接收端需要通过对比文档中定义的 Payload 内容长度和实际接收到的长度，若实际接收的长度不足，则进行补零。 



## 概念介绍

1. 不同帧如何区分:

|**CMD**|**ACK**|**MSG**|
|---|---|---|
|MSG\_ID\[0:2\] = 76 |MSG\_ID\[0:2\] = 77|其他均为MSG<br>|

2. SYSID: 一个完整系统，发送端系统ID

3. COMPID: 发送端组件ID 注:一个系统中不能存在相同的COMPID！

4. TargetSysId：接收方系统ID 

5. TargetCompID：接收方组件ID   

6. CMD帧: 主控发起的一次动作控制或信息请求；接收设备收到后需执行操作，并返回 ACK 或消息帧；

7. ACK帧： 响应 CMD 帧的结果确认，表示命令是否执行成功；若命令为“请求型”，则消息帧返回数据。

8. 消息帧：用于传输设备状态、参数信息等；可为响应 CMD 的数据帧或周期性主动上报帧。



## CMD命令发送接口

```C++
/**
@brief Encode a command_long struct
@param sysId ID of this system
@param compId ID of this component (e.g. 200 for IMU)
@param targetSystem ID of the target system (0 for broadcast)
@param targetComponent ID of the target component (0 for broadcast)
@param command Command ID to send
@param param1 ~ param7 Parameters for the command
@note 发送命令给电机，命令参数见对应CMD表格
      当 targetSystem 与 targetComponent 都为 0 时，表示广播
*/
void Custom_Send_Cmd(uint8_t sysId, uint8_t compId,
         uint8_t targetSystem, uint8_t targetComponent,uint16_t command,
         float param1, float param2, float param3, float param4,
         float param5, float param6, float param7)
{
    mavlink_command_long_t command_long;
    mavlink_message_t msg;
    uint8_t buf[MAVLINK_MAX_PACKET_LEN] = {0};  // 存放封包数据

    command_long.target_system = targetSystem;
    command_long.target_component = targetComponent;
    command_long.command = command;
    command_long.param1 = param1;
    command_long.param2 = param2;
    command_long.param3 = param3;
    command_long.param4 = param4;
    command_long.param5 = param5;
    command_long.param6 = param6;
    command_long.param7 = param7;
    command_long.confirmation = 0;

    // 组包
    mavlink_msg_command_long_encode(sysId, compId, &msg, &command_long);

    // 实际发送数据长度（包括帧开销）
    uint16_t len = mavlink_msg_to_send_buffer(buf, &msg);

    // 底层串口/总线发送接口（需自行实现）   
    // TODO: 实现数据发送函数
    // 示例：uart_send(buf, len);
}
```



接收方在收到一条 CMD命令后，返回给发送方（如主控器）的一个回执或确认信，用于明确告知命令的处理结果。

### ACK反馈结果

|结果|值|备注|
|---|---|---|
|MAV\_RESULT\_ACCEPTED|0|命令有效（已支持且参数合法），并已成功执行|
|MAV\_RESULT\_TEMPORARILY\_REJECTED|1|命令有效，但当前无法执行。用于表示临时性问题，例如状态机忙碌等，稍后尝试|
|MAV\_RESULT\_DENIED|2|命令无效（虽受支持，但参数不合法）稍后尝试|
|MAV\_RESULT\_UNSUPPORTED|3|命令不被支持（未知命令）|
|MAV\_RESULT\_FAILED|4|令有效，但执行失败。用于表示非临时性或意外错误，例如内存不足、未校准传感器等，需先解决问题再重试|
|MAV\_RESULT\_IN\_PROGRESS|5|命令有效，正在执行中。|
|MAV\_RESULT\_CANCELLED|6|命令已取消（例如接收到 \`COMMAND\_CANCEL\` 消息后）|
|MAV\_RESULT\_COMMAND\_LONG\_ONLY|7|命令仅接受通过 \`COMMAND\_LONG\` 方式发送|
|MAV\_RESULT\_COMMAND\_INT\_ONLY|8|命令仅接受通过 \`COMMAND\_INT\` 方式发送|
|MAV\_RESULT\_COMMAND\_UNSUPPORTED\_MAV\_FRAME|9|命令无效，因需要指定坐标系，但当前帧类型不被支持|
|MAV\_RESULT\_ENUM\_END|10|枚举结束标识（无实际用途，仅标识边界）。|

**驱动回复**

```C

//ACK帧:
MAVLINK_MSG_ID_COMMAND_ACK 77
//回复解包
static inline void mavlink_msg_command_ack_decode(const mavlink_message_t* msg, mavlink_command_ack_t* command_ack)
```



## 接收解包

当主控接收到消息帧时，使用xxxx\_decode\(\.\.\.\.\)会自动解析数据到对应的结构体中,详见 附录 接收示例



# 电机数据消息

## 电机状态1

该消息包含电机**母线电压、母线电流、电机温度、驱动（MCU）温度**信息。

**消息结构：**

```C
#define MAVLINK_MSG_ID_MOTOR_STATUS_INFO_1 51500

typedef struct *__mavlink_motor_status_info_1_t* {
    float bus_voltage;       /*< Bus voltage, unit: V.*/
    float bus_current;       /*< Bus current, unit: A.*/
    float motor_temperature; /*< Motor temperature, unit: °C.*/
    float MCU_temperature;   /*< Drive (MCU) temperature, unit: °C.*/
} *mavlink_motor_status_info_1_t*;
```

|param|含义|
|---|---|
|bus\_voltage|母线电压|
|bus\_current|母线电流|
|motor\_temperature|电机温度|
|MCU\_temperature|MCU温度|

**解包接口：**

```C++
static inline uint16_t mavlink_msg_motor_status_info_1_encode(uint8_t system_id, uint8_t component_id, mavlink_message_t* msg, const mavlink_motor_status_info_1_t* motor_status_info_1)
```

## 电机状态2

该消息包含**电流/转矩相关量、电机转速、输出功率、编码器位置**等信息。

```C
#define MAVLINK_MSG_ID_MOTOR_STATUS_INFO_2 51501

typedef struct *__mavlink_motor_status_info_2_t* {
    float torque_current;   /*< torque value, unit: A。*/
    float motor_speed;      /*< Motor speed, unit: rpm.*/
    float output_power;     /*< Output power, unit: W.*/
    int64_t encoder_position; /*< Encoder position, unit: P.*/
} *mavlink_motor_status_info_2_t*;
```

|param|含义|
|---|---|
|torque\_current|转矩值|
|motor\_speed|电机速度|
|output\_power|输出功率|
|encoder\_position|编码器值|

**解包接口：**

```C++
static inline void mavlink_msg_motor_status_info_2_decode(const *mavlink_message_t** *msg*, *mavlink_motor_status_info_2_t** *motor_status_info_2*);
```

## 电机状态3

该消息包含**三相电流（A/B/C 相）**，单位：A。

```C++
#define MAVLINK_MSG_ID_MOTOR_STATUS_INFO_3 51502

typedef struct *__mavlink_motor_status_info_3_t* {
    float phase_current_a; /*< Phase current A, unit: A.*/
    float phase_current_b; /*< Phase current B, unit: A.*/
    float phase_current_c; /*< Phase current C, unit: A.*/
} *mavlink_motor_status_info_3_t*;
```

|param|含义|
|---|---|
|phase\_current\_a|U相电流|
|phase\_current\_b|V相电流|
|phase\_current\_c|W相电流|

**解包接口：**

```C++
static inline void mavlink_msg_motor_status_info_3_decode(const *mavlink_message_t** *msg*, *mavlink_motor_status_info_3_t** *motor_status_info_3*);
```



## 电机状态4

该消息包含**状态字、故障字、警告字**。

```C++
#define MAVLINK_MSG_ID_MOTOR_STATUS_INFO_4 51503

typedef struct *__mavlink_motor_status_info_4_t* {
    uint32_t Statusword; /*< Motor status word.*/
    uint32_t Error_word; /*< Motor error word.*/
    uint32_t Alarm_word; /*< Motor alarm word.*/
} *mavlink_motor_status_info_4_t*;
```

|param|含义|
|---|---|
|Statusword|状态字|
|Error\_word|错误字|
|Alarm\_word|警告字|

**解包接口：**

```C++
static inline void mavlink_msg_motor_status_info_4_decode(const *mavlink_message_t** *msg*, *mavlink_motor_status_info_4_t** *motor_status_info_4*);
```

![image\.png](图片和附件/image%201.png)



```Thrift
typedef enum MOTOR_STATUSWORD_FLAG
{
   MOTOR_STATUSWORD_TARGET_REACHED=1, /* Bit 0: Target reached | */
   MOTOR_STATUSWORD_ZERO_SPEED_REACHED=2, /* Bit 1: Zero speed reached | */
   MOTOR_STATUSWORD_HOMING_COMPLETE=4, /* Bit 2: Homing complete | */
   MOTOR_STATUSWORD_POSITION_REACHED=8, /* Bit 3: Position reached | */
   MOTOR_STATUSWORD_VELOCITY_REACHED=16, /* Bit 4: Velocity reached | */
   MOTOR_STATUSWORD_TORQUE_REACHED=32, /* Bit 5: Torque reached | */
   MOTOR_STATUSWORD_ENABLED=64, /* Bit 6: Enabled state | */
   MOTOR_STATUSWORD_FLAG_ENUM_END=65, /*  | */
} MOTOR_STATUSWORD_FLAG;
```

```SQL
typedef enum MOTOR_ERRORWORD_FLAG
{
   MOTOR_ERROR_E3230_DRIVER_PEAK_CURRENT_OVERLOAD=1, /* Bit 0 [E3230]: Driver peak current overload protection | */
   MOTOR_ERROR_EF005_DRIVER_OVERLOAD=2, /* Bit 1 [EF005]: Driver overload | */
   MOTOR_ERROR_E3210_BUS_OVERVOLTAGE=4, /* Bit 2 [E3210]: Bus overvoltage | */
   MOTOR_ERROR_E3220_BUS_UNDERVOLTAGE=8, /* Bit 3 [E3220]: Bus undervoltage | */
   MOTOR_ERROR_E4210_DRIVER_OVERTEMP=16, /* Bit 4 [E4210]: Driver overtemperature | */
   MOTOR_ERROR_E4220_DRIVER_UNDERTEMP=32, /* Bit 5 [E4220]: Driver undertemperature | */
   MOTOR_ERROR_E8400_MOTOR_OVERSPEED=64, /* Bit 6 [E8400]: Motor overspeed | */
   MOTOR_ERROR_E8611_POSITION_TRACKING_ERROR=128, /* Bit 7 [E8611]: Position tracking error too large | */
   MOTOR_ERROR_E7306_LOAD_ENCODER_ERROR=256, /* Bit 8 [E7306]: Load-side encoder error | */
   MOTOR_ERROR_E7305_MOTOR_ENCODER_ERROR=512, /* Bit 9 [E7305]: Motor-side encoder error | */
   MOTOR_ERROR_E5530_FLASH_STORAGE_ERROR=1024, /* Bit 10 [E5530]: FLASH storage error | */
   MOTOR_ERROR_EF006_DRV_INIT_ERROR=2048, /* Bit 11 [EF006]: DRV initialization error | */
   MOTOR_ERROR_EF008_CURRENT_SAMPLING_ERROR=4096, /* Bit 12 [EF008]: Current sampling error | */
   MOTOR_ERROR_EFF07_HARDWARE_SHORT_CIRCUIT=8192, /* Bit 13 [EFF07]: Hardware short-circuit protection | */
   MOTOR_ERROR_E2312_SOFTWARE_OVERCURRENT=16384, /* Bit 14 [E2312]: Software overcurrent protection | */
   MOTOR_ERROR_EFF09_BUS_VOLTAGE_DETECT_ABNORMAL=32768, /* Bit 15 [EFF09]: Bus voltage detection abnormality | */
   MOTOR_ERROR_EFF0A_CAN_BUS_DISCONNECT=65536, /* Bit 16 [EFF0A]: CAN bus disconnection | */
   MOTOR_ERROR_E7121_MOTOR_OVERHEAT=131072, /* Bit 17 [E7121]: Motor overheating | */
   MOTOR_ERROR_EFF0B_MOTOR_LOW_TEMPERATURE=262144, /* Bit 18 [EFF0B]: Motor low temperature | */
   MOTOR_ERROR_E4310_MCU_OVERTEMP=524288, /* Bit 19 [E4310]: MCU overtemperature | */
   MOTOR_ERROR_E4320_MCU_UNDERTEMP=1048576, /* Bit 20 [E4320]: MCU undertemperature | */
   MOTOR_ERRORWORD_FLAG_ENUM_END=1048577, /*  | */
} MOTOR_ERRORWORD_FLAG;
```

```Thrift
typedef enum MOTOR_ALARMWORD_FLAG
{
   MOTOR_ALARM_DRIVER_HIGH_TEMP=1, /* Bit 0: Driver high temperature warning | */
   MOTOR_ALARM_DRIVER_LOW_TEMP=2, /* Bit 1: Driver low temperature warning | */
   MOTOR_ALARM_MOTOR_HIGH_TEMP=4, /* Bit 2: Motor high temperature warning | */
   MOTOR_ALARM_MOTOR_LOW_TEMP=8, /* Bit 3: Motor low temperature warning | */
   MOTOR_ALARM_MCU_HIGH_TEMP=16, /* Bit 4: MCU high temperature warning | */
   MOTOR_ALARM_MCU_LOW_TEMP=32, /* Bit 5: MCU low temperature warning | */
   MOTOR_ALARM_MOTOR_NTC_ABNORMAL=64, /* Bit 6: Motor NTC abnormality warning | */
   MOTOR_ALARMWORD_FLAG_ENUM_END=65, /*  | */
} MOTOR_ALARMWORD_FLAG;
```

## 电机限制参数表

该消息存储着电机的限制参数。

```C
#define MAVLINK_MSG_ID_MOTOR_RESTRICTPARAM 51504

typedef struct __mavlink_motor_restrictparam_t {
 int64_t Position_range_limit_Minimal_position_limit; /*<  Position range limit minimal position limit.*/
 int64_t Position_range_limit_Maximal_position_limit; /*<  Position range limit maximal position limit.*/
 int64_t Software_position_limit_Minimal_position_limit; /*<  Software position limit minimal position limit.*/
 int64_t Software_position_limit_Maximal_position_limit; /*<  Software position limit maximal position limit.*/
 float Max_profile_velocity; /*<  Max profile velocity limit, unit: RPM.*/
 float Max_motor_speed; /*<  Max motor speed, unit: RPM.*/
 float Max_acceleration; /*<  Max acceleration limit, unit: RPM/s.*/
 float Max_deceleration; /*<  Max deceleration limit, unit: RPM/s.*/
 float Max_current; /*<  Max current limit, unit: A.*/
 uint8_t Position_limit_enable; /*<  Position limit enable switch.*/
} mavlink_motor_restrictparam_t;
```

|param|含义|
|---|---|
|Position\_range\_limit\_Minimal\_position\_limit|位置溢出最小值|
|Position\_range\_limit\_Maximal\_position\_limit|位置溢出最大值|
|Software\_position\_limit\_Minimal\_position\_limit|应用位置下限|
|Software\_position\_limit\_Maximal\_position\_limit|应用位置上限|
|Max\_profile\_velocity|应用速度限制|
|Max\_motor\_speed|电机最大转速|
|Max\_acceleration|应用加速度限制|
|Max\_deceleration|应用减速度限制|
|Max\_current|应用电流限制|
|Position\_limit\_enable|位置限位使能开关|

**解包接口：**

```C
static inline void mavlink_msg_motor_restrictparam_decode(const mavlink_message_t* msg, mavlink_motor_restrictparam_t* motor_restrictparam)
```

## 电机保护参数表

该消息存储着电机的保护参数。

```C++
#define MAVLINK_MSG_ID_MOTOR_PROTECTPARAM 51505

typedef struct __mavlink_motor_protectparam_t {
 float Bus_under_voltage_threshold; /*<  Bus under voltage threshold, unit: V.*/
 float Bus_over_voltage_threshold; /*<  Bus over voltage threshold, unit: V.*/
 float Drive_overload_current_duration; /*<  Drive overload current duration, unit: s.*/
 float Drive_peak_current_duration; /*<  Drive peak current duration, unit: s.*/
 float Drive_temperature_threshold_time; /*<  Drive temperature threshold time, unit: s.*/
 float Drive_low_temperature_fault_threshold; /*<  Drive low temperature fault threshold, unit: ¡ヮ*/
 float Drive_high_temperature_fault_threshold; /*<  Drive high temperature fault threshold, unit: ¡ヮ*/
 float Overspeed_threshold; /*<  Overspeed threshold, unit: RPM.*/
 float Drive_overcurrent_threshold; /*<  Drive overcurrent threshold, unit: A.*/
 uint32_t Protection_enable; /*<  Protection enable switch.*/
 float Motor_low_temperature_fault_threshold; /*<  Motor low temperature fault threshold, unit: ¡ヮ*/
 float Motor_high_temperature_fault_threshold; /*<  Motor high temperature fault  threshold, unit: ¡ヮ*/
 float Can_timeout; /*<  CAN timeout, unit: s.*/
 float Motor_low_temperature_warning_threshold; /*<  Motor low temperature warning threshold, unit: ¡ヮ*/
 float Motor_high_temperature_warning_threshold; /*<  Motor high temperature warning threshold, unit: ¡ヮ*/
 float Mcu_temperature_threshold_time; /*<  MCU temperature threshold time, unit: s.*/
 float Mcu_low_temperature_fault_threshold; /*<  MCU low temperature fault threshold, unit: ¡ヮ*/
 float Mcu_high_temperature_fault_threshold; /*<  MCU high temperature fault threshold, unit: ¡ヮ*/
 float Mcu_low_temperature_warning_threshold; /*<  MCU low temperature warning threshold, unit: ¡ヮ*/
 float Mcu_high_temperature_warning_threshold; /*<  MCU high temperature warning threshold, unit: ¡ヮ*/
 float Drive_low_temperature_warning_threshold; /*<  Drive low temperature warning threshold, unit: ¡ヮ*/
 float Drive_high_temperature_warning_threshold; /*<  Drive high temperature warning threshold, unit: ¡ヮ*/
} mavlink_motor_protectparam_t;
```

|param\_index|含义|
|---|---|
|Bus\_under\_voltage\_threshold|母线欠压阈值|
|Bus\_over\_voltage\_threshold|母线过压阈值|
|Drive\_overload\_current\_duration|驱动器过载持续时间|
|Drive\_peak\_current\_duration|驱动器峰值电流持续时间|
|Drive\_temperature\_threshold\_time|驱动器温度保护阈值时间|
|Drive\_low\_temperature\_fault\_threshold|驱动器低温报错阈值|
|Drive\_high\_temperature\_fault\_threshold|驱动器高温报错阈值|
|Overspeed\_threshold|过速阈值|
|Drive\_overcurrent\_threshold|驱动器过流保护阈值|
|Protection\_enable|保护生效|
|Motor\_low\_temperature\_fault\_threshold|电机低温报错阈值|
|Motor\_high\_temperature\_fault\_threshold|电机高温报错阈值|
|Can\_timeout|CAN通讯超时时间|
|Motor\_low\_temperature\_warning\_threshold|电机低温警告阈值|
|Motor\_high\_temperature\_warning\_threshold|电机高温警告阈值|
|Mcu\_temperature\_threshold\_time|MCU温度保护阈值时间|
|Mcu\_low\_temperature\_fault\_threshold|MCU低温报错阈值|
|Mcu\_high\_temperature\_fault\_threshold|MCU高温报错阈值|
|Mcu\_low\_temperature\_warning\_threshold|MCU低温警告阈值|
|Mcu\_high\_temperature\_warning\_threshold|MCU高温警告阈值|
|Drive\_low\_temperature\_warning\_threshold|驱动器低温警告阈值|
|Drive\_high\_temperature\_warning\_threshold|驱动器高温警告阈值|

**解包接口：**

```C
static inline void mavlink_msg_motor_protectparam_decode(const mavlink_message_t* msg, mavlink_motor_protectparam_t* motor_protectparam)
```



## **电机控制参数表**

该消息为**电流环/速度环/位置环等控制参数**的一次性回读。

```C++
#define MAVLINK_MSG_ID_MOTOR_PARAMETER_CONTROL_TABLE 51506

typedef struct *__mavlink_motor_parameter_control_table_t* {
    float kp_ld; /*< d-axis kp control gain.*/
    float ki_ld; /*< d-axis ki control integral gain.*/
    float kp_lq; /*< q-axis kp control gain.*/
    float ki_lq; /*< q-axis ki control integral gain.*/
    float kp_p;  /*< Position loop proportional coefficient.*/
    float kp_s;  /*< Speed loop proportional coefficient.*/
    float ki_s;  /*< Speed loop integral coefficient.*/
    float aff;   /*< Acceleration feedforward coefficient.*/
    float vff;   /*< Speed feedforward coefficient.*/
    float j_kt;  /*< Inertial coefficient, unit: kg·m²/(N·m/A).*/
} *mavlink_motor_parameter_control_table_t*;
```

|param|含义|
|---|---|
|kp\_ld|电流环D轴KP|
|ki\_ld|电流环D轴KI|
|kp\_lq|电流环Q轴KP|
|ki\_lq|电流环Q轴KI|
|kp\_p|位置环KP|
|kp\_s|速度环KP|
|ki\_s|速度环KI|
|aff|加速度前馈系数|
|vff8|速度前馈系数|
|j\_kt|惯性系数|

**解包接口：**

```C++
static inline void mavlink_msg_motor_parameter_control_table_decode(const *mavlink_message_t** *msg*, *mavlink_motor_parameter_control_table_t** *motor_parameter_control_table*);
```

## **电机 MAVLIN\_ID信息**

该消息读取当前节点的MAVLINL\_ID。

```C++
#define MAVLINK_MSG_ID_MOTOR_SYS_COMP_ID_INFO 51507


typedef struct __mavlink_motor_sys_comp_id_info_t {
 uint8_t sysId; /*<  System ID.*/
 uint8_t compId; /*<  Component ID.*/
} mavlink_motor_sys_comp_id_info_t;
```

|param|含义|
|---|---|
|sysId|系统ID|
|compId1|组件ID|

**解包接口：**

```C++
static inline void mavlink_msg_motor_sys_comp_id_info_decode(const mavlink_message_t* msg, mavlink_motor_sys_comp_id_info_t* motor_sys_comp_id_info)
```



## **电机 CAN ID 信息**

该消息读取当前配置的 CAN 节点ID。

```C++
#define MAVLINK_MSG_ID_MOTOR_CAN_ID_INFO 51508

typedef struct *__mavlink_motor_can_id_info_t* {
    uint8_t canId; /*< CAN ID.*/
} *mavlink_motor_can_id_info_t*;
```

|param\_index|含义|
|---|---|
|canId|CANID|

**解包接口：**

```C++
static inline void mavlink_msg_motor_can_id_info_decode(const *mavlink_message_t** *msg*, *mavlink_motor_can_id_info_t** *motor_can_id_info*);
```

## **电机心跳包**

该消息为电机定时返回消息，频率为1Hz。可通过监控此消息来知晓设备是否在线，通讯是否正常。

```C++
#define MAVLINK_MSG_ID_HEARTBEAT 0


typedef struct __mavlink_heartbeat_t {
 uint32_t custom_mode; /*<  A bitfield for use for autopilot-specific flags*/
 uint8_t type; /*<  Vehicle or component type. For a flight controller component the vehicle type (quadrotor, helicopter, etc.). For other components the component type (e.g. camera, gimbal, etc.). This should be used in preference to component id for identifying the component type.*/
 uint8_t autopilot; /*<  Autopilot type / class. Use MAV_AUTOPILOT_INVALID for components that are not flight controllers.*/
 uint8_t base_mode; /*<  System mode bitmap.*/
 uint8_t system_status; /*<  System status flag.*/
 uint8_t mavlink_version; /*<  MAVLink version, not writable by user, gets added by protocol because of magic data type: uint8_t_mavlink_version*/
} mavlink_heartbeat_t;
```

|system\_status|含义|
|---|---|
|MAV\_STATE\_UNINIT = 0 |未初始化|
|MAV\_STATE\_BOOT = 1  |启动中|
|MAV\_STATE\_CALIBRATING = 2 |校准中|
|MAV\_STATE\_STANDBY = 3|待命/就绪|
|MAV\_STATE\_ACTIVE = 4 |活动/运行中|
|MAV\_STATE\_CRITICAL = 5 |严重故障|
|MAV\_STATE\_EMERGENCY = 6 |紧急情况|
|MAV\_STATE\_POWEROFF = 7|关机|
|MAV\_STATE\_FLIGHT\_TERMINATION = 8|飞行终止|

**备注：**默认正常设备上线状态为`MAV_STATE_ACTIVE = 4 `

**解包接口：**

```C++
static inline void mavlink_msg_heartbeat_decode(const mavlink_message_t* msg, mavlink_heartbeat_t* heartbeat);
```



## **电机执行结果ACK**

命令执行结果。

```C++
#define MAVLINK_MSG_ID_COMMAND_ACK 77

typedef struct *__mavlink_command_ack_t* {
    uint16_t command;
    uint8_t result;
    uint8_t progress;
    int32_t result_param2;
    uint8_t target_system;
    uint8_t target_component;
} *mavlink_command_ack_t*;
```

|结果|值|备注|
|---|---|---|
|MAV\_RESULT\_ACCEPTED|0|命令有效（已支持且参数合法），并已成功执行|
|MAV\_RESULT\_TEMPORARILY\_REJECTED|1|命令有效，但当前无法执行。用于表示临时性问题，例如状态机忙碌等，稍后尝试|
|MAV\_RESULT\_DENIED|2|命令无效（虽受支持，但参数不合法）稍后尝试|
|MAV\_RESULT\_UNSUPPORTED|3|命令不被支持（未知命令）|
|MAV\_RESULT\_FAILED|4|令有效，但执行失败。用于表示非临时性或意外错误，例如内存不足、未校准传感器等，需先解决问题再重试|
|MAV\_RESULT\_IN\_PROGRESS|5|命令有效，正在执行中。|
|MAV\_RESULT\_CANCELLED|6|命令已取消（例如接收到 \`COMMAND\_CANCEL\` 消息后）|
|MAV\_RESULT\_COMMAND\_LONG\_ONLY|7|命令仅接受通过 \`COMMAND\_LONG\` 方式发送|
|MAV\_RESULT\_COMMAND\_INT\_ONLY|8|命令仅接受通过 \`COMMAND\_INT\` 方式发送|
|MAV\_RESULT\_COMMAND\_UNSUPPORTED\_MAV\_FRAME|9|命令无效，因需要指定坐标系，但当前帧类型不被支持|
|MAV\_RESULT\_ENUM\_END|10|枚举结束标识（无实际用途，仅标识边界）。|

**解包接口：**

```C++
static inline void mavlink_msg_command_ack_decode(const *mavlink_message_t** *msg*, *mavlink_command_ack_t** *command_ack*);
```









# 电机命令API

### 读取电机状态 1 命令

该命令读取当前电机的温度、电压和错误状态标志。

**Cmd\-Param**

|命令字段|类型|描述|
|---|---|---|
|目标系统|uint8\_t|远端系统ID|
|目标组件|uint8\_t|电机组件ID|
|command|Uint16\_t|MAV\_CMD\_READ\_MOTOR\_STATUS\_1=51600|
|confirmation|Uint8\_t|0|
|参数1|float|\-|
|参数2|float|\-|
|参数3|float|\-|
|参数4|float|\-|
|参数5|float|\-|
|参数6|float|\-|
|参数7|float|\-|

**发送接口**

```C
Custom_Send_Cmd(...);
```

**驱动回复**

[电机控制协议手册](https://tcnyx5kk9u7c.feishu.cn/wiki/FwE7w2rONiH1RrkPrmHcXLnVnDg#share-LJD0dl9Wqo3EZ6x5TCAchc9BnVg)

### **读取电机状态 2 命令**

该命令读取当前电机转矩电流、输出功率、转速、编码器值。

**Cmd\-Param**

|命令字段|类型|描述|
|---|---|---|
|目标系统|uint8\_t|远端系统ID|
|目标组件|uint8\_t|电机组件ID|
|command|Uint16\_t|MAV\_CMD\_READ\_MOTOR\_STATUS\_2=51601|
|confirmation|Uint8\_t|0|
|参数1|float|\-|
|参数2|float|\-|
|参数3|float|\-|
|参数4|float|\-|
|参数5|float|\-|
|参数6|float|\-|
|参数7|float|\-|

```C
Custom_Send_Cmd(...);
```

**驱动回复**

[电机控制协议手册](https://tcnyx5kk9u7c.feishu.cn/wiki/FwE7w2rONiH1RrkPrmHcXLnVnDg#share-A4DNdaOoSoeqDCxn2YVcEQxznvF)

### 读取电机状态 3 命令

该命令读取当前电机的温度和 3 相电流数据

**Cmd\-Param**

|命令字段|类型|描述|
|---|---|---|
|目标系统|uint8\_t|远端系统ID|
|目标组件|uint8\_t|电机组件ID|
|command|Uint16\_t|MAV\_CMD\_READ\_MOTOR\_STATUS\_3=51602|
|confirmation|Uint8\_t|0|
|参数1|float|\-|
|参数2|float|\-|
|参数3|float|\-|
|参数4|float|\-|
|参数5|float|\-|
|参数6|float|\-|
|参数7|float|\-|

```C
Custom_Send_Cmd(...);
```



**驱动回复**

[电机控制协议手册](https://tcnyx5kk9u7c.feishu.cn/wiki/FwE7w2rONiH1RrkPrmHcXLnVnDg#share-ItZ0ddMShoAkZExrt3vcChZDn3r)



### 读取电机状态 4 命令

该命令读取当前电机的状态，错误，警告信息。

**Cmd\-Param**

|命令字段|类型|描述|
|---|---|---|
|目标系统|uint8\_t|远端系统ID|
|目标组件|uint8\_t|电机组件ID|
|command|Uint16\_t|MAV\_CMD\_READ\_MOTOR\_STATUS\_3=51603|
|confirmation|Uint8\_t|0|
|参数1|float|\-|
|参数2|float|\-|
|参数3|float|\-|
|参数4|float|\-|
|参数5|float|\-|
|参数6|float|\-|
|参数7|float|\-|

```C
Custom_Send_Cmd(...);
```



**驱动回复**

[电机控制协议手册](https://tcnyx5kk9u7c.feishu.cn/wiki/FwE7w2rONiH1RrkPrmHcXLnVnDg#share-Cp3WddHDHoXdhZx5DeYcAwupnBd)



### 清除电机错误标志命令

该命令清除当前电机的错误状态。

**Cmd\-Param**

|命令字段|类型|描述|
|---|---|---|
|目标系统|uint8\_t|远端系统ID|
|目标组件|uint8\_t|电机组件ID|
|command|Uint16\_t|MAV\_CMD\_CLEAR\_MOTOR\_ERR\_SIGNS=51604|
|confirmation|Uint8\_t|0|
|参数1|float|\-|
|参数2|float|\-|
|参数3|float|\-|
|参数4|float|\-|
|参数5|float|\-|
|参数6|float|\-|
|参数7|float|\-|

```C
Custom_Send_Cmd(...);
```

**驱动回复**

执行结果见: “**ACK反馈结果**。

[电机控制协议手册](https://tcnyx5kk9u7c.feishu.cn/wiki/FwE7w2rONiH1RrkPrmHcXLnVnDg#share-GcNHdbMLjo0JdSx7dQIcahQHnYg)

**备注：**

电机状态没有恢复正常时，错误标志无法清除。



### 电机失能命令

失能电机。

**Cmd\-Param**

|命令字段|类型|描述|
|---|---|---|
|目标系统|uint8\_t|远端系统ID|
|目标组件|uint8\_t|电机组件ID|
|command|Uint16\_t|MAV\_CMD\_CLOSE\_MOTOR=51605|
|confirmation|Uint8\_t|0|
|参数1|float|\-|
|参数2|float|\-|
|参数3|float|\-|
|参数4|float|\-|
|参数5|float|\-|
|参数6|float|\-|
|参数7|float|\-|

```C
Custom_Send_Cmd(...);
```

**驱动回复:**

执行结果见: “**ACK反馈结果**。

[电机控制协议手册](https://tcnyx5kk9u7c.feishu.cn/wiki/FwE7w2rONiH1RrkPrmHcXLnVnDg#share-GcNHdbMLjo0JdSx7dQIcahQHnYg)



### **电机使能命令**

使能电机，使能前要先设置好电机运行模式和参数，上电电机默认控模式。

**Cmd\-Param**

|命令字段|类型|描述|
|---|---|---|
|目标系统|uint8\_t|远端系统ID|
|目标组件|uint8\_t|电机组件ID|
|command|Uint16\_t|MAV\_CMD\_OPEN\_MOTOR=51606|
|confirmation|Uint8\_t|0|
|参数1|float|\-|
|参数2|float|\-|
|参数3|float|\-|
|参数4|float|\-|
|参数5|float|\-|
|参数6|float|\-|
|参数7|float|\-|

```C
Custom_Send_Cmd(...);
```

**驱动回复:**

执行结果见: “**ACK反馈结果**。

[电机控制协议手册](https://tcnyx5kk9u7c.feishu.cn/wiki/FwE7w2rONiH1RrkPrmHcXLnVnDg#share-GcNHdbMLjo0JdSx7dQIcahQHnYg)

### **电机紧急停止命令**

电机运行时停止。

**Cmd\-Param**

|命令字段|类型|描述|
|---|---|---|
|目标系统|uint8\_t|远端系统ID|
|目标组件|uint8\_t|电机组件ID|
|command|Uint16\_t|MAV\_CMD\_EMERGENCY\_STOP\_MOTOR=51607|
|confirmation|Uint8\_t|0|
|参数1|float|\-|
|参数2|float|\-|
|参数3|float|\-|
|参数4|float|\-|
|参数5|float|\-|
|参数6|float|\-|
|参数7|float|\-|

```C
Custom_Send_Cmd(...);
```

**驱动回复:**

执行结果见: “**ACK反馈结果**。

[电机控制协议手册](https://tcnyx5kk9u7c.feishu.cn/wiki/FwE7w2rONiH1RrkPrmHcXLnVnDg#share-GcNHdbMLjo0JdSx7dQIcahQHnYg)



### **转矩闭环控制命令**

主机发送该命令以控制电机以期望转矩电流输出\.

**Cmd\-Param**

|命令字段|类型|描述|
|---|---|---|
|目标系统|uint8\_t|远端系统ID|
|目标组件|uint8\_t|电机组件ID|
|command|Uint16\_t|MAV\_CMD\_MOTOR\_TORQUE\_CLOSED\_LOOP\_CONTROL=51609|
|confirmation|Uint8\_t|0|
|参数1|float|Target\_torque（力矩目标值，单位：A）|
|参数2|float|Torque\_slope（力矩上升斜率，单位：A/S）|
|参数3|float|\-|
|参数4|float|\-|
|参数5|float|\-|
|参数6|float|\-|
|参数7|float|\-|

```C
Custom_Send_Cmd(...);
```

**备注：**

1. 该命令下，电机的期望力矩由最大电流值限制。

**驱动回复 **

执行结果见: “**ACK反馈结果**。

[电机控制协议手册](https://tcnyx5kk9u7c.feishu.cn/wiki/FwE7w2rONiH1RrkPrmHcXLnVnDg#share-GcNHdbMLjo0JdSx7dQIcahQHnYg)

### **速度闭环控制命令**

主机发送该命令以控制电机以期望速度运行。

**Cmd\-Param**

|命令字段|类型|描述|
|---|---|---|
|目标系统|uint8\_t|远端系统ID|
|目标组件|uint8\_t|电机组件ID|
|command|Uint16\_t|MAV\_CMD\_MOTOR\_SPEED\_CLOSED\_LOOP\_CONTROL=51610|
|confirmation|Uint8\_t|0|
|参数1|float|Target\_velocity（目标速度，单位RPM）|
|参数2|float|Profile\_acceleration（轮廓加速度，单位RPM/S）|
|参数3|float|Profile\_deceleration（轮廓减速度，单位RPM/S）|
|参数4|float|\-|
|参数5|float|\-|
|参数6|float|\-|
|参数7|float|\-|

```C
Custom_Send_Cmd(...);
```

**备注：**

1. 该命令下，电机的期望速度由应用速度值限制。

2. 该命令下，电机的最大加速度由应用加速度值限制。 

3. 该命令下，电机的最大减速度由应用减速度值限制。

**驱动回复 **

执行结果见: “**ACK反馈结果**。

[电机控制协议手册](https://tcnyx5kk9u7c.feishu.cn/wiki/FwE7w2rONiH1RrkPrmHcXLnVnDg#share-GcNHdbMLjo0JdSx7dQIcahQHnYg)

### **位置闭环控制命令**

主机发送该命令以控制电机运行到期望位置。

**Cmd\-Param**

|命令字段|类型|描述|
|---|---|---|
|目标系统|uint8\_t|远端系统ID|
|目标组件|uint8\_t|电机组件ID|
|command|Uint16\_t|MAV\_CMD\_MOTOR\_POSITION\_CLOSED\_LOOP\_CONTROL=51611|
|confirmation|Uint8\_t|0|
|参数1|int64\_t|Target\_position（目标位置，**单位P**）|
|参数2|float|Profile\_velocity（轮廓速度，单位RPM）|
|参数3|float|Profile\_acceleration（轮廓加速度，单位RPM/S）|
|参数4|float|Profile\_deceleration（轮廓减速度，单位RPM/S）|
|参数5|float|\-|
|参数6|float|\-|
|参数7|float|\-|

```C
Custom_Send_Cmd(...);
```

**备注：**

1. 该命令下，电机的目标由应用位置上/下限制值限制。

2. 该命令下，电机的期望速度由应用速度值限制。

3. 该命令下，电机的最大加速度由应用加速度值限制。 

4. 该命令下，电机的最大减速度由应用减速度值限制。

**驱动回复 **

执行结果见: “**ACK反馈结果**。

[电机控制协议手册](https://tcnyx5kk9u7c.feishu.cn/wiki/FwE7w2rONiH1RrkPrmHcXLnVnDg#share-GcNHdbMLjo0JdSx7dQIcahQHnYg)

### **MIT控制命令**

MIT模式控制电机

**Cmd\-Param**

|命令字段|类型|描述|
|---|---|---|
|目标系统|uint8\_t|远端系统ID|
|目标组件|uint8\_t|电机组件ID|
|command|Uint16\_t|MAV\_CMD\_MOTOR\_MIT\_CONTROL=51612|
|confirmation|Uint8\_t|0|
|参数1|float|MIT\_feedforward\_torque（前馈力矩，单位：N/M）|
|参数2|int64\_t|MIT\_target\_position（ 目标位置，单位：P）|
|参数3|float|MIT\_target\_velocity（ 目标速度，单位：RPM）|
|参数4|float|MIT\_max\_current（ 最大输出电流，单位：A）|
|参数5|float|MIT\_kp（位置刚度 ，单位：NM/rad）|
|参数6|float|MIT\_kd（速度阻尼系数 ，单位：NM/\(rad/s\)）|
|参数7|float|\-|

```C
Custom_Send_Cmd(...);
```

**备注：**

1. 该命令下，电机的目标由应用位置上/下限制值限制。

2. 该命令下，电机的期望速度由应用速度值限制。

3. 该命令下，电机的最大加速度由应用加速度值限制。 

4. 该命令下，电机的最大减速度由应用减速度值限制。

**驱动回复 **

执行结果见: “**ACK反馈结果**。

[电机控制协议手册](https://tcnyx5kk9u7c.feishu.cn/wiki/FwE7w2rONiH1RrkPrmHcXLnVnDg#share-GcNHdbMLjo0JdSx7dQIcahQHnYg)







### **读取电机mavlink\_ID**

主机发送该命令读取当前电机的系统id和组件id。

**Cmd\-Param**

|命令字段|类型|描述|
|---|---|---|
|目标系统|uint8\_t|远端系统ID|
|目标组件|uint8\_t|电机组件ID|
|command|Uint16\_t|MAV\_CMD\_MOTOR\_READ\_MAVID=51614|
|confirmation|Uint8\_t|0|
|参数1|float|\-|
|参数2|float|\-|
|参数3|float|\-|
|参数4|float|\-|
|参数5|float|\-|
|参数6|float|\-|
|参数7|float|\-|

```C
Custom_Send_Cmd(...);
```



**驱动回复 **

消息：电机mavlink\_id[电机控制协议手册](https://tcnyx5kk9u7c.feishu.cn/wiki/FwE7w2rONiH1RrkPrmHcXLnVnDg#share-DjZfdkDuZo5UoVxjFZZcd0C5nDP)



### **设置系统ID**

主机发送该命令修改电机的系统ID。

**Cmd\-Param**

|命令字段|类型|描述|
|---|---|---|
|目标系统|uint8\_t|远端系统ID|
|目标组件|uint8\_t|电机组件ID|
|command|Uint16\_t|MAV\_CMD\_MOTOR\_SET\_SYS\_ID=51615|
|confirmation|Uint8\_t|0|
|参数1|float|sysId|
|参数2|float|\-|
|参数3|float|\-|
|参数4|float|\-|
|参数5|float|\-|
|参数6|float|\-|
|参数7|float|\-|

```C
Custom_Send_Cmd(...);
```

**驱动回复 **

执行结果见: “**ACK反馈结果**。

[电机控制协议手册](https://tcnyx5kk9u7c.feishu.cn/wiki/FwE7w2rONiH1RrkPrmHcXLnVnDg#share-GcNHdbMLjo0JdSx7dQIcahQHnYg)





### **设置组件ID**

主机发送该命令修改电机的组件ID。

**Cmd\-Param**

|命令字段|类型|描述|
|---|---|---|
|目标系统|uint8\_t|远端系统ID|
|目标组件|uint8\_t|电机组件ID|
|command|Uint16\_t|MAV\_CMD\_MOTOR\_SET\_COMP\_ID=51616|
|confirmation|Uint8\_t|0|
|参数1|float|compId|
|参数2|float|\-|
|参数3|float|\-|
|参数4|float|\-|
|参数5|float|\-|
|参数6|float|\-|
|参数7|float|\-|

```C
Custom_Send_Cmd(...);
```

**驱动回复 **

执行结果见: “**ACK反馈结果**。

[电机控制协议手册](https://tcnyx5kk9u7c.feishu.cn/wiki/FwE7w2rONiH1RrkPrmHcXLnVnDg#share-GcNHdbMLjo0JdSx7dQIcahQHnYg)



### **设置CAN\-ID**

主机发送该命令修改电机的组件ID。

**Cmd\-Param**

|命令字段|类型|描述|
|---|---|---|
|目标系统|uint8\_t|远端系统ID|
|目标组件|uint8\_t|电机组件ID|
|command|Uint16\_t|MAV\_CMD\_MOTOR\_SET\_CAN\_ID=51617|
|confirmation|Uint8\_t|0|
|参数1|float|compId|
|参数2|float|\-|
|参数3|float|\-|
|参数4|float|\-|
|参数5|float|\-|
|参数6|float|\-|
|参数7|float|\-|

```C
Custom_Send_Cmd(...);
```

**驱动回复 **

执行结果见: “**ACK反馈结果**。

[电机控制协议手册](https://tcnyx5kk9u7c.feishu.cn/wiki/FwE7w2rONiH1RrkPrmHcXLnVnDg#share-GcNHdbMLjo0JdSx7dQIcahQHnYg)



### 查询CAN\-ID

主机发送该命令读取当前电机的控制参数。

**Cmd\-Param**

|命令字段|类型|描述|
|---|---|---|
|目标系统|uint8\_t|远端系统ID|
|目标组件|uint8\_t|电机组件ID|
|command|Uint16\_t|MAV\_CMD\_MOTOR\_READ\_CAN\_ID=51618|
|confirmation|Uint8\_t|0|
|参数1|float|\-|
|参数2|float|\-|
|参数3|float|\-|
|参数4|float|\-|
|参数5|float|\-|
|参数6|float|\-|
|参数7|float|\-|

```C
Custom_Send_Cmd(...);
```



**驱动回复 **

消息：[电机控制协议手册](https://tcnyx5kk9u7c.feishu.cn/wiki/FwE7w2rONiH1RrkPrmHcXLnVnDg#share-ELG1ddRkdoBDRsxcuJ2ckiwfnGd)







### **读取控制参数命令**

主机发送该命令读取当前电机的控制参数。

**Cmd\-Param**

|命令字段|类型|描述|
|---|---|---|
|目标系统|uint8\_t|远端系统ID|
|目标组件|uint8\_t|电机组件ID|
|command|Uint16\_t|MAV\_CMD\_MOTOR\_READ\_CONTROL\_PARAMETER=51619|
|confirmation|Uint8\_t|0|
|参数1|float|\-|
|参数2|float|\-|
|参数3|float|\-|
|参数4|float|\-|
|参数5|float|\-|
|参数6|float|\-|
|参数7|float|\-|

```C
Custom_Send_Cmd(...);
```



**驱动回复 **

消息：电机控制参数表[电机控制协议手册](https://tcnyx5kk9u7c.feishu.cn/wiki/FwE7w2rONiH1RrkPrmHcXLnVnDg#share-N8NldQTjEoQfYdxfkyRce4APncf)







### **写入控制参数命令**

主机发送该命令修改电机的控制参数。

**Cmd\-Param**

|命令字段|类型|描述|
|---|---|---|
|目标系统|uint8\_t|远端系统ID|
|目标组件|uint8\_t|电机组件ID|
|command|Uint16\_t|MAV\_CMD\_MOTOR\_WRITE\_CONTROL\_PARAMETER=51614|
|confirmation|Uint8\_t|0|
|参数1|float|controlParamID（所要修改的参数对应枚举号）|
|参数2|float|controlParamValue（新值）|
|参数3|float|\-|
|参数4|float|\-|
|参数5|float|\-|
|参数6|float|\-|
|参数7|float|\-|

|controlParamID|含义|
|---|---|
|0|电流环D轴KP|
|1|电流环D轴KI|
|2|电流环Q轴KP|
|3|电流环Q轴KI|
|4|位置环KP|
|5|速度环KP|
|6|速度环KI|
|7|加速度前馈系数|
|8|速度前馈系数|
|9|惯性系数|

```C
typedef enum MOTOR_CONTROL_PARAM_ID
{
   MOTOR_CONTROL_PARAM_KP_LD=0, /* D-axis current loop proportional gain (kp_ld) | */
   MOTOR_CONTROL_PARAM_KI_LD=1, /* D-axis current loop integral gain (ki_ld) | */
   MOTOR_CONTROL_PARAM_KP_LQ=2, /* Q-axis current loop proportional gain (kp_lq) | */
   MOTOR_CONTROL_PARAM_KI_LQ=3, /* Q-axis current loop integral gain (ki_lq) | */
   MOTOR_CONTROL_PARAM_KP_P=4, /* Position loop proportional coefficient (kp_p) | */
   MOTOR_CONTROL_PARAM_KP_S=5, /* Speed loop proportional coefficient (kp_s) | */
   MOTOR_CONTROL_PARAM_KI_S=6, /* Speed loop integral coefficient (ki_s) | */
   MOTOR_CONTROL_PARAM_AFF=7, /* Acceleration feedforward coefficient (aff) | */
   MOTOR_CONTROL_PARAM_VFF=8, /* Speed feedforward coefficient (vff) | */
   MOTOR_CONTROL_PARAM_J_KT=9, /* Inertial coefficient (j_kt), unit kg*m^2/(N*m/A) | */
   MOTOR_CONTROL_PARAM_ID_ENUM_END=10, /*  | */
} MOTOR_CONTROL_PARAM_ID;
```

```C
Custom_Send_Cmd(...);
```

**驱动回复 **

执行结果见: “**ACK反馈结果**。

[电机控制协议手册](https://tcnyx5kk9u7c.feishu.cn/wiki/FwE7w2rONiH1RrkPrmHcXLnVnDg#share-GcNHdbMLjo0JdSx7dQIcahQHnYg)



### **读取电机保护参数命令**

主机发送该命令读取当前电机的保护参数。

**Cmd\-Param**

|命令字段|类型|描述|
|---|---|---|
|目标系统|uint8\_t|远端系统ID|
|目标组件|uint8\_t|电机组件ID|
|command|Uint16\_t|MAV\_CMD\_MOTOR\_READ\_PROTECT\_PARAM=51621|
|confirmation|Uint8\_t|0|
|参数1|float|\-|
|参数2|float|\-|
|参数3|float|\-|
|参数4|float|\-|
|参数5|float|\-|
|参数6|float|\-|
|参数7|float|\-|

```C
Custom_Send_Cmd(...);
```



**驱动回复 **

消息：电机保护参数表[电机控制协议手册](https://tcnyx5kk9u7c.feishu.cn/wiki/FwE7w2rONiH1RrkPrmHcXLnVnDg#share-VotUdOELdo5K3zx8WkbcVVOknfb)



### 设置电机保护参数值

主机发送该命令修改电机的保护参数。

**Cmd\-Param**

|命令字段|类型|描述|
|---|---|---|
|目标系统|uint8\_t|远端系统ID|
|目标组件|uint8\_t|电机组件ID|
|command|Uint16\_t|MAV\_CMD\_MOTOR\_WRITE\_PROTECT\_PARAM=51622|
|confirmation|Uint8\_t|0|
|参数1|float|param\_index（所要修改的参数对应枚举号）|
|参数2|float|param\_value（新值）|
|参数3|float|\-|
|参数4|float|\-|
|参数5|float|\-|
|参数6|float|\-|
|参数7|float|\-|

|param\_index|含义|
|---|---|
|0|母线欠压阈值|
|1|母线过压阈值|
|2|驱动器过载持续时间|
|3|驱动器峰值电流持续时间|
|4|驱动器过流保护阈值|
|5|驱动器高温报错阈值|
|6|驱动器低温报错阈值|
|7|驱动器高温警告阈值|
|8|驱动器低温警告阈值|
|9|过速阈值|
|10|电机低温报错阈值|
|11|电机高温报错阈值|
|12|电机低温警告阈值|
|13|电机高温警告阈值|
|14|MCU温度保护阈值时间|
|15|MCU低温报错阈值|
|16|MCU高温报错阈值|
|17|MCU低温警告阈值|
|18|MCU高温警告阈值|
|19|CAN通讯超时时间|
|20|保留|

```C
typedef enum MOTOR_PROTECT_PARAM_INDEX
{
   BUS_UNDER_VOLTAGE_THRESHOLD=0, /* Bus under voltage threshold [V] | */
   BUS_OVER_VOLTAGE_THRESHOLD=1, /* Bus over voltage threshold [V] | */
   DRIVE_OVERLOAD_DURATION=2, /* Driver overload duration [s] | */
   DRIVE_PEAK_CURRENT_DURATION=3, /* Driver peak current duration [s] | */
   DRIVE_OVERCURRENT_THRESHOLD=4, /* Driver overcurrent threshold [A] | */
   DRIVE_HIGH_TEMP_FAULT_THRESHOLD=5, /* Driver high temperature fault threshold [¡ポ | */
   DRIVE_LOW_TEMP_FAULT_THRESHOLD=6, /* Driver low temperature fault threshold [¡ポ | */
   DRIVE_HIGH_TEMP_WARNING_THRESHOLD=7, /* Driver high temperature warning threshold [¡ポ | */
   DRIVE_LOW_TEMP_WARNING_THRESHOLD=8, /* Driver low temperature warning threshold [¡ポ | */
   OVERSPEED_THRESHOLD=9, /* Overspeed threshold [RPM] | */
   MOTOR_PROTECT_INDEX_MOTOR_LOW_TEMP_FAULT=10, /* Motor low temperature fault threshold [¡ポ | */
   MOTOR_PROTECT_INDEX_MOTOR_HIGH_TEMP_FAULT=11, /* Motor high temperature fault threshold [¡ポ | */
   MOTOR_LOW_TEMP_WARNING_THRESHOLD=12, /* Motor low temperature warning threshold [¡ポ | */
   MOTOR_HIGH_TEMP_WARNING_THRESHOLD=13, /* Motor high temperature warning threshold [¡ポ | */
   MCU_TEMP_THRESHOLD_TIME=14, /* MCU temperature threshold time [s] | */
   MCU_LOW_TEMP_FAULT_THRESHOLD=15, /* MCU low temperature fault threshold [¡ポ | */
   MCU_HIGH_TEMP_FAULT_THRESHOLD=16, /* MCU high temperature fault threshold [¡ポ | */
   MCU_LOW_TEMP_WARNING_THRESHOLD=17, /* MCU low temperature warning threshold [¡ポ | */
   MCU_HIGH_TEMP_WARNING_THRESHOLD=18, /* MCU high temperature warning threshold [¡ポ | */
   CAN_TIMEOUT=19, /* CAN communication timeout [s] | */
   MOTOR_PROTECT_PARAM_INDEX_ENUM_END=20, /*  | */
} MOTOR_PROTECT_PARAM_INDEX;
```

```C
Custom_Send_Cmd(...);
```

**驱动回复 **

执行结果见: “**ACK反馈结果**。

[电机控制协议手册](https://tcnyx5kk9u7c.feishu.cn/wiki/FwE7w2rONiH1RrkPrmHcXLnVnDg#share-GcNHdbMLjo0JdSx7dQIcahQHnYg)





### **读取电机限制参数命令**

主机发送该命令读取当前电机的限制参数。

**Cmd\-Param**

|命令字段|类型|描述|
|---|---|---|
|目标系统|uint8\_t|远端系统ID|
|目标组件|uint8\_t|电机组件ID|
|command|Uint16\_t|MAV\_CMD\_MOTOR\_READ\_RESTRICT\_PARAM=51623|
|confirmation|Uint8\_t|0|
|参数1|float|\-|
|参数2|float|\-|
|参数3|float|\-|
|参数4|float|\-|
|参数5|float|\-|
|参数6|float|\-|
|参数7|float|\-|

```C
Custom_Send_Cmd(...);
```



**驱动回复 **

消息：电机限制参数表[电机控制协议手册](https://tcnyx5kk9u7c.feishu.cn/wiki/FwE7w2rONiH1RrkPrmHcXLnVnDg#share-QyMwdAKsGoBmQcxwBafct71Rn4f)

### 设置电机限制参数值

主机发送该命令修改电机的限制参数。

**Cmd\-Param**

|命令字段|类型|描述|
|---|---|---|
|目标系统|uint8\_t|远端系统ID|
|目标组件|uint8\_t|电机组件ID|
|command|Uint16\_t|MAV\_CMD\_MOTOR\_SET\_RESTRICT\_PARAM=51622|
|confirmation|Uint8\_t|0|
|参数1|float|param\_index（所要修改的参数对应枚举号）|
|参数2|float|param\_value（新值）|
|参数3|float|\-|
|参数4|float|\-|
|参数5|float|\-|
|参数6|float|\-|
|参数7|float|\-|

|param\_index|含义|
|---|---|
|0|位置溢出最小值|
|1|位置溢出最大值|
|2|应用位置下限|
|3|应用位置上限|
|4|应用速度限制（输出端）|
|5|电机最大转速\(电机端\)|
|6|应用加速度限制|
|7|应用减速度限制|
|8|应用电流限制|
|9|位置限位使能开关|

```C
typedef enum MOTOR_RESTRICT_PARAM_INDEX
{
   POSITION_RANGE_LIMIT_MINIMAL=0, /* Position range limit minimal position limit [P] | */
   POSITION_RANGE_LIMIT_MAXIMAL=1, /* Position range limit maximal position limit [P] | */
   SOFTWARE_POSITION_LIMIT_MINIMAL=2, /* Software position limit minimal position limit [P] | */
   SOFTWARE_POSITION_LIMIT_MAXIMAL=3, /* Software position limit maximal position limit [P] | */
   MAX_PROFILE_VELOCITY=4, /* Max profile velocity limit [RPM] | */
   MAX_MOTOR_SPEED=5, /* Max motor speed [RPM] | */
   MAX_ACCELERATION=6, /* Max acceleration limit [RPM/s] | */
   MAX_DECELERATION=7, /* Max deceleration limit [RPM/s] | */
   MAX_CURRENT=8, /* Max current limit [A] | */
   POSITION_LIMIT_ENABLE=9, /* Position limit enable switch | */
   MOTOR_RESTRICT_PARAM_INDEX_ENUM_END=10, /*  | */
} MOTOR_RESTRICT_PARAM_INDEX;
```

```C
Custom_Send_Cmd(...);
```

**驱动回复 **

执行结果见: “**ACK反馈结果**。

[电机控制协议手册](https://tcnyx5kk9u7c.feishu.cn/wiki/FwE7w2rONiH1RrkPrmHcXLnVnDg#share-GcNHdbMLjo0JdSx7dQIcahQHnYg)





### **参数保存至FLASH**

主机发送该命令可以将设置的参数保存至电机flash中。

**Cmd\-Param**

|命令字段|类型|描述|
|---|---|---|
|目标系统|uint8\_t|远端系统ID|
|目标组件|uint8\_t|电机组件ID|
|command|Uint16\_t|MAV\_CMD\_MOTOR\_FLASH\_SAVE=51625|
|confirmation|Uint8\_t|0|
|参数1|float|\-|
|参数2|float|\-|
|参数3|float|\-|
|参数4|float|\-|
|参数5|float|\-|
|参数6|float|\-|
|参数7|float|\-|

```C
Custom_Send_Cmd(...);
```

**驱动回复 **

执行结果见: “**ACK反馈结果**。

[电机控制协议手册](https://tcnyx5kk9u7c.feishu.cn/wiki/FwE7w2rONiH1RrkPrmHcXLnVnDg#share-GcNHdbMLjo0JdSx7dQIcahQHnYg)

# 附录

## mavlink协议包

https://gitee\.com/cai\-chaozheng/YONIQ

![image\.png](图片和附件/image.png)

将该文件夹拷贝到自己工程即可。



## 命令发送接口封装示例



**命令发送接口（也可自己封装）**

```C++
/**
@brief Encode a command_long struct
@param sysId ID of this system
@param compId ID of this component (e.g. 200 for IMU)
@param targetSystem ID of the target system (0 for broadcast)
@param targetComponent ID of the target component (0 for broadcast)
@param command Command ID to send
@param param1 ~ param7 Parameters for the command

*/
void Custom_Send_Cmd(uint8_t sysId, uint8_t compId,
         uint8_t targetSystem, uint8_t targetComponent,uint16_t command,
         float param1, float param2, float param3, float param4,
         float param5, float param6, float param7)
{
    mavlink_command_long_t command_long;
    mavlink_message_t msg;
    uint8_t buf[MAVLINK_MAX_PACKET_LEN] = {0};  // 存放封包数据

    command_long.target_system = targetSystem;
    command_long.target_component = targetComponent;
    command_long.command = command;
    command_long.param1 = param1;
    command_long.param2 = param2;
    command_long.param3 = param3;
    command_long.param4 = param4;
    command_long.param5 = param5;
    command_long.param6 = param6;
    command_long.param7 = param7;
    command_long.confirmation = 0;

    // 组包
    mavlink_msg_command_long_encode(sysId, compId, &msg, &command_long);

    // 实际发送数据长度（包括帧开销）
    uint16_t len = mavlink_msg_to_send_buffer(buf, &msg);

    // 底层串口/总线发送接口（需自行实现）   
    // TODO: 实现数据发送函数
    // 示例：
    uart_send(buf, len);
}
```



### 读取电机状态1

```C
void Read_status1(uint8_t sysId, uint8_t compId,
         uint8_t targetSystem, uint8_t targetComponent){

    Custom_Send_Cmd(sysId,compId,targetSystem,targetComponent,MAV_CMD_READ_MOTOR_STATUS_1,0,0,0,0,0,0,0);        

}

```

### 读取电机状态2

```C
void Read_status1(uint8_t sysId, uint8_t compId,
         uint8_t targetSystem, uint8_t targetComponent){

    Custom_Send_Cmd(sysId,compId,targetSystem,targetComponent,MAV_CMD_READ_MOTOR_STATUS_2,0,0,0,0,0,0,0);        

}
```

### 转矩闭环控制

```C
void Motor_Torque_Control(uint8_t sysId, uint8_t compId,
         uint8_t targetSystem, uint8_t targetComponent
         float Target_torque,float Torque_slope){

    Custom_Send_Cmd(sysId,compId,targetSystem,targetComponent,MAV_CMD_MOTOR_TORQUE_CLOSED_LOOP_CONTROL,Target_torque,Torque_slope,0,0,0,0,0);        

}
```

### 速度闭环控制

```C
void Motor_speed_Control(uint8_t sysId, uint8_t compId,
         uint8_t targetSystem, uint8_t targetComponent
         float Target_velocity,float Profile_acceleration,float Profile_deceleration){

    Custom_Send_Cmd(sysId,compId,targetSystem,targetComponent,MAV_CMD_MOTOR_SPEED_CLOSED_LOOP_CONTROL,Target_velocity,Profile_acceleration,Profile_deceleration,0,0,0,0);        

}
```



### 位置闭环控制

```C
void Motor_speed_Control(uint8_t sysId, uint8_t compId,
         uint8_t targetSystem, uint8_t targetComponent
         int64_tTarget_position,float Profile_velocity,float Profile_acceleration,float Profile_deceleration){

    Custom_Send_Cmd(sysId,compId,targetSystem,targetComponent,MAV_CMD_MOTOR_POSITION_CLOSED_LOOP_CONTROL,Target_position,Profile_velocity,Profile_acceleration,Profile_deceleration,0,0,0);        

}
```



### MIT控制

```C
void Motor_speed_Control(uint8_t sysId, uint8_t compId,
         uint8_t targetSystem, uint8_t targetComponent
        float MIT_feedforward_torque,int64_t MIT_target_position,float MIT_target_velocity,float MIT_max_current,float MIT_kp,float MIT_kd){

    Custom_Send_Cmd(sysId,compId,targetSystem,targetComponent,MAV_CMD_MOTOR_MIT_CONTROL,MIT_feedforward_torque,MIT_target_position,MIT_target_velocity,MIT_max_current,MIT_kp,MIT_kd,0);        

}
```



### 解包接口示例

```C++
typedef struct
{
    uint8_t ack_valid;
    mavlink_command_ack_t ack;

    uint8_t status1_valid;
    mavlink_motor_status_info_1_t status1;

    uint8_t status2_valid;
    mavlink_motor_status_info_2_t status2;

    uint8_t status3_valid;
    mavlink_motor_status_info_3_t status3;

    uint8_t status4_valid;
    mavlink_motor_status_info_4_t status4;
} MotorMavlinkState;
static mavlink_message_t s_parse_msg;
static mavlink_status_t s_parse_status;
static MotorMavlinkState s_motor_state;

/* 处理一帧完整 MAVLink 消息 */
static void MotorMavlink_ProcessMessage(const mavlink_message_t *msg)
{
    if (msg == NULL) {
        return;
    }

    /*
     * 如需限制只接收指定电机，可以打开下面的判断：
     *
     * if (msg->sysid != 1 || msg->compid != 1) {
     *     return;
     * }
     */

    switch (msg->msgid) {
    case MAVLINK_MSG_ID_COMMAND_ACK:
        mavlink_msg_command_ack_decode(msg, &s_motor_state.ack);
        s_motor_state.ack_valid = 1;
        break;

    case MAVLINK_MSG_ID_MOTOR_STATUS_INFO_1:
        mavlink_msg_motor_status_info_1_decode(
            msg, &s_motor_state.status1);
        s_motor_state.status1_valid = 1;
        break;

    case MAVLINK_MSG_ID_MOTOR_STATUS_INFO_2:
        mavlink_msg_motor_status_info_2_decode(
            msg, &s_motor_state.status2);
        s_motor_state.status2_valid = 1;
        break;

    case MAVLINK_MSG_ID_MOTOR_STATUS_INFO_3:
        mavlink_msg_motor_status_info_3_decode(
            msg, &s_motor_state.status3);
        s_motor_state.status3_valid = 1;
        break;

    case MAVLINK_MSG_ID_MOTOR_STATUS_INFO_4:
        mavlink_msg_motor_status_info_4_decode(
            msg, &s_motor_state.status4);
        s_motor_state.status4_valid = 1;
        break;

    default:
        break;
    }
}

/* 每收到一个 UART 字节，就调用一次 */
void MotorMavlink_RxByte(uint8_t byte)
{
    if (mavlink_parse_char(MAVLINK_COMM_0,
                           byte,
                           &s_parse_msg,
                           &s_parse_status)) {
        MotorMavlink_ProcessMessage(&s_parse_msg);
    }
}
```





