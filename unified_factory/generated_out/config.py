
# -*- coding: utf-8 -*-
""" 自动生成的电力系统仿真配置文件 """

BASE_DSS_DIRECTORY = "New_Topo"
MASTER_DSS_FILE_NAME = "master_file.dss"

GAS_GENERATOR_NAMES = [
"002_1_9",
"002_1_10",
"002_1_2_161",
"002_1_4_345",
"002_1_4_161",
"002_1_3"
]

GENERATOR_POWER_PERCENTAGES = {
"002_1_9": 1.0,
"002_1_10": 1.0,
"002_1_2_161": 1.0,
"002_1_4_345": 1.0,
"002_1_4_161": 1.0,
"002_1_3": 1.0
}

GAS_NODE_TO_GENERATOR_MAP = {
"gas9": "002_1_9",
"gas10": "002_1_10",
"gas21": "002_1_2_161",
"gas4": ["002_1_4_345", "002_1_4_161"],
"gas1": "002_1_3"
}

def get_generator_power_percentage(gen_name, default=0.9):
    return GENERATOR_POWER_PERCENTAGES.get(gen_name, default)

ALPHA = 0.0
BETA = 0.00516
GAMMA = 0.0

COMPRESSOR_LOAD_NAMES = [
"load_22_73",
"load_22_74",
"load_22_75",
"load_22_76",
"load_22_77",
"load_22_78",
"load_22_79"
]

SIMULATION_SETTINGS = {"hour": 0, "maxiterations": 5000, "mode": "daily", "number": 1, "stepsize": "30s"}
OUTPUT_FILES = {"all_elements_power": "all_elements_power.csv", "power_send": "power_send.csv"}
INFLUXDB_CONFIG = {"bucket": "simulation_data", "enable_storage": false, "id": "simulation_instance", "org": "my-org", "org_id": "YOUR_ORG_ID", "token": "YOUR_TOKEN_HERE", "url": "http://localhost:8086"}