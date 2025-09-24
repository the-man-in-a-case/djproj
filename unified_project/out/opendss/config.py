# -*- coding: utf-8 -*-
"""
电力系统仿真配置文件
包含所有系统参数和设置，设计为具有可扩展性，可适应不同数量的燃气发电机和负载点
"""

# ==================== 基础路径配置 ====================
# BASE_DSS_DIRECTORY = "IEEE118Bus_modified"
# MASTER_DSS_FILE_NAME = "master_file.dss"

BASE_DSS_DIRECTORY = "New_Topo"
MASTER_DSS_FILE_NAME = "master_file.dss"

# ==================== 燃气发电机配置 ====================
# 燃气发电机名称列表 - 可根据需要扩展
# GAS_GENERATOR_NAMES = [
#     "Gen_at_10_1",
#     "Gen_at_12_1",
#     "Gen_at_18_1",
#     "Gen_at_19_1",
#     "Gen_at_46_1",
#     "Gen_at_49_1",
#     "Gen_at_69_1"
# ]

GAS_GENERATOR_NAMES = [
    "002_1_9",
    "002_1_10",
    "002_1_2_161",
    "002_1_4_345",
    "002_1_4_161",
    "002_1_3"
]

# 设置每个发电机的目标功率占额定功率的百分比 - 默认为90%，可针对每个发电机单独设置
# GENERATOR_POWER_PERCENTAGES = {
#     # 特定发电机的设置
#     "Gen_at_10_1": 1.0,
#     "Gen_at_12_1": 1.0,
#     "Gen_at_18_1": 1.0,
#     "Gen_at_19_1": 1.0,
#     "Gen_at_46_1": 1.0,
#     "Gen_at_49_1": 1.0,
#     "Gen_at_69_1": 1.0
# }
GENERATOR_POWER_PERCENTAGES = {
    # 特定发电机的设置
    "002_1_9": 1.0,
    "002_1_10": 1.0,
    "002_1_2_161": 1.0,
    "002_1_4_345": 1.0,
    "002_1_4_161": 1.0,
    "002_1_3": 1.0
}

# ==================== 燃气节点与发电机映射关系 ====================
# 燃气节点与发电机的对应关系，一个燃气节点可以对应一个或多个发电机
GAS_NODE_TO_GENERATOR_MAP = {
    "gas9": "002_1_9",
    "gas10": "002_1_10",
    "gas21": "002_1_2_161",
    "gas4": ["002_1_4_345", "002_1_4_161"],  # 这两个发电机使用相同的燃气量
    "gas1": "002_1_3"
}

# 获取任何发电机的功率百分比，如果未特别指定则返回默认值
def get_generator_power_percentage(gen_name, default=0.9):
    return GENERATOR_POWER_PERCENTAGES.get(gen_name, default)

# 热率曲线参数: F_i = α_i + β_i * P_i + γ_i * P_i^2
ALPHA = 0.0      # 基础燃气消耗 (MMSCM)
BETA = 0.00516   # 一次项系数 (MMSCM/MW)
GAMMA = 0.0      # 二次项系数 (MMSCM/MW²)

# ==================== 压缩机负载配置 ====================
# 压缩机负载名称列表 - 可根据需要扩展
COMPRESSOR_LOAD_NAMES = [
    "load_22_73",
    "load_22_74",
    "load_22_75",
    "load_22_76",
    "load_22_77",
    "load_22_78",
    "load_22_79"
]

# ==================== 仿真参数配置 ====================
SIMULATION_SETTINGS = {
    "hour": 0,
    "mode": "daily",
    "maxiterations": 5000,
    "stepsize": "30s",
    "number": 1
}

# ==================== 输出文件配置 ====================
OUTPUT_FILES = {
    "power_send": "power_send.csv",
    "all_elements_power": "all_elements_power.csv",
}

# ==================== InfluxDB配置 ====================
INFLUXDB_CONFIG = {
    'url': 'http://localhost:8086',
    'token': "YOUR_TOKEN_HERE",
    'org': "my-org",
    'bucket': "simulation_data",
    'org_id': "YOUR_ORG_ID",
    'id': "simulation_instance",
    "enable_storage": False  # 是否启用InfluxDB存储
}