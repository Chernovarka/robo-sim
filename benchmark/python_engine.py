import argparse
import json
import importlib.metadata
import math
import time
from xml.etree import ElementTree as ET

from spec import BODY_MASS, BODY_SIZE, MEASURED_STEPS, TIME_STEP, WARMUP_STEPS, body_positions


def read_metric(path):
    try:
        with open(path, encoding='utf-8') as metric_file:
            return metric_file.read().strip()
    except OSError:
        return None


def cpu_seconds():
    raw = read_metric('/sys/fs/cgroup/cpu.stat') or ''
    for line in raw.splitlines():
        if line.startswith('usage_usec '):
            return int(line.split()[1]) / 1_000_000
    return None


def pybullet_run(count, scenario):
    import pybullet as physics
    client = physics.connect(physics.DIRECT)
    try:
        physics.setGravity(0, 0, -9.81)
        physics.setTimeStep(TIME_STEP)
        physics.setRealTimeSimulation(0)
        physics.setPhysicsEngineParameter(numSolverIterations=50)
        ground_shape = physics.createCollisionShape(physics.GEOM_PLANE)
        physics.createMultiBody(baseMass=0, baseCollisionShapeIndex=ground_shape)
        box_shape = physics.createCollisionShape(physics.GEOM_BOX, halfExtents=[size / 2 for size in BODY_SIZE])
        bodies = [physics.createMultiBody(baseMass=BODY_MASS, baseCollisionShapeIndex=box_shape,
                                         basePosition=position)
                  for position in body_positions(count, scenario)]
        for body in bodies:
            physics.changeDynamics(body, -1, lateralFriction=0.8)
        for _ in range(WARMUP_STEPS):
            physics.stepSimulation()
        before_cpu = cpu_seconds()
        start = time.perf_counter()
        for _ in range(MEASURED_STEPS):
            physics.stepSimulation()
        elapsed = time.perf_counter() - start
        after_cpu = cpu_seconds()
        heights = [physics.getBasePositionAndOrientation(body)[0][2] for body in bodies]
        return elapsed, before_cpu, after_cpu, heights
    finally:
        physics.disconnect(client)


def mujoco_xml(count, scenario):
    root = ET.Element('mujoco', model='selection')
    ET.SubElement(root, 'option', timestep=str(TIME_STEP), gravity='0 0 -9.81', integrator='Euler')
    world = ET.SubElement(root, 'worldbody')
    ET.SubElement(world, 'geom', name='ground', type='plane', size='5 5 0.1',
                  friction='0.8 0.005 0.001')
    for index, position in enumerate(body_positions(count, scenario)):
        body = ET.SubElement(world, 'body', name=f'box_{index}', pos=' '.join(map(str, position)))
        ET.SubElement(body, 'freejoint')
        ET.SubElement(body, 'geom', type='box', size=' '.join(str(size / 2) for size in BODY_SIZE),
                      mass=str(BODY_MASS), friction='0.8 0.005 0.001')
    return ET.tostring(root, encoding='unicode')


def mujoco_run(count, scenario):
    import mujoco
    model = mujoco.MjModel.from_xml_string(mujoco_xml(count, scenario))
    data = mujoco.MjData(model)
    for _ in range(WARMUP_STEPS):
        mujoco.mj_step(model, data)
    before_cpu = cpu_seconds()
    start = time.perf_counter()
    for _ in range(MEASURED_STEPS):
        mujoco.mj_step(model, data)
    elapsed = time.perf_counter() - start
    after_cpu = cpu_seconds()
    heights = [float(data.xpos[mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, f'box_{index}')][2])
               for index in range(count)]
    return elapsed, before_cpu, after_cpu, heights


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('engine', choices=('pybullet', 'mujoco'))
    parser.add_argument('scenario', choices=('rest', 'drop'))
    parser.add_argument('count', type=int, choices=(1, 8, 32))
    arguments = parser.parse_args()
    if arguments.engine == 'pybullet':
        elapsed, before_cpu, after_cpu, heights = pybullet_run(arguments.count, arguments.scenario)
    else:
        elapsed, before_cpu, after_cpu, heights = mujoco_run(arguments.count, arguments.scenario)
    expected_z = BODY_SIZE[2] / 2
    physically_valid = all(math.isfinite(height) and abs(height - expected_z) < 0.035 for height in heights)
    core_cpu = after_cpu - before_cpu if before_cpu is not None and after_cpu is not None else None
    result = {
        'engine': arguments.engine, 'scenario': arguments.scenario, 'count': arguments.count,
        'engine_version': importlib.metadata.version(arguments.engine),
        'measured_steps': MEASURED_STEPS, 'dt_s': TIME_STEP,
        'core_wall_s': round(elapsed, 6), 'core_cpu_s': round(core_cpu, 6) if core_cpu is not None else None,
        'steps_per_second': round(MEASURED_STEPS / elapsed, 4),
        'memory_peak_bytes': int(read_metric('/sys/fs/cgroup/memory.peak') or 0),
        'physics_valid': physically_valid,
        'heights_min_m': round(min(heights), 5), 'heights_max_m': round(max(heights), 5),
        'cpu_max': read_metric('/sys/fs/cgroup/cpu.max'),
        'memory_max': read_metric('/sys/fs/cgroup/memory.max'),
        'cpuset_effective': read_metric('/sys/fs/cgroup/cpuset.cpus.effective'),
        'memory_swap_max': read_metric('/sys/fs/cgroup/memory.swap.max')
    }
    print('ROBOSIM_RESULT=' + json.dumps(result), flush=True)
    if not physically_valid:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
