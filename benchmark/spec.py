import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = Path(__file__).resolve().parent
RESULTS_DIR = PROJECT_ROOT / 'data' / 'selection'
TIME_STEP = 0.01
WARMUP_STEPS = 100
MEASURED_STEPS = 2000
BODY_MASS = 2.0
BODY_SIZE = (0.30, 0.24, 0.12)
BODY_COUNTS = (1, 8, 32)
SCENARIOS = ('rest', 'drop')
ENGINES = ('pybullet', 'mujoco', 'gazebo')


def body_positions(count, scenario):
    if count not in BODY_COUNTS or scenario not in SCENARIOS:
        raise ValueError('Invalid workload')
    height = BODY_SIZE[2] / 2 + (0.001 if scenario == 'rest' else 0.54)
    return [(0.75 + 0.70 * (index % 6), 0.75 + 0.70 * (index // 6), height)
            for index in range(count)]


def get_profile():
    return json.loads((BENCHMARK_DIR / 'profile.json').read_text())
