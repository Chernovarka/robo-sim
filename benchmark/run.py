import argparse
from datetime import datetime, timezone
import json
import platform
import random
from pathlib import Path
import subprocess
import time
import uuid

from spec import BODY_COUNTS, ENGINES, RESULTS_DIR, SCENARIOS, get_profile

IMAGES = {
    'pybullet': 'robosim-selection-python:v1',
    'mujoco': 'robosim-selection-python:v1',
    'gazebo': 'robosim-selection-gazebo:v1',
}


def execute(engine, scenario, count, repetition, profile):
    container_name = f'robosim-selection-{uuid.uuid4().hex[:12]}'
    memory = int(profile['memory_bytes'])
    command = [
        'docker', 'run', '--name', container_name,
        '--cpus', str(profile['cpus']), '--cpuset-cpus', profile['cpuset_cpus'],
        '--memory', str(memory), '--memory-swap', str(memory),
        '--pids-limit', str(profile['pids_limit']),
        '--network', 'none', '--read-only', '--tmpfs', '/tmp:rw,nosuid,nodev,size=256m',
        '--security-opt', 'no-new-privileges', '--cap-drop', 'ALL',
        '--init', '-e', 'HOME=/tmp',
        IMAGES[engine],
    ]
    if engine == 'gazebo':
        command += [scenario, str(count), f'/app/benchmark/worlds/{scenario}_{count}.sdf']
    else:
        command += [engine, scenario, str(count)]
    timed_out = False
    outer_start = time.perf_counter()
    returncode = None
    stdout = ''
    stderr = ''
    state = {}
    try:
        try:
            process = subprocess.run(command, capture_output=True, text=True,
                                     timeout=profile['timeout_seconds'], check=False)
            stdout, stderr, returncode = process.stdout, process.stderr, process.returncode
        except subprocess.TimeoutExpired as error:
            timed_out = True
            stdout = error.stdout.decode('utf-8', 'replace') if isinstance(error.stdout, bytes) else (error.stdout or '')
            stderr = error.stderr.decode('utf-8', 'replace') if isinstance(error.stderr, bytes) else (error.stderr or '')
            subprocess.run(['docker', 'kill', container_name], capture_output=True, timeout=20)
            returncode = 124
        inspected = subprocess.run(['docker', 'inspect', '--format', '{{json .State}}', container_name],
                                   capture_output=True, text=True, timeout=20)
        if inspected.returncode == 0:
            state = json.loads(inspected.stdout)
    finally:
        subprocess.run(['docker', 'rm', '-f', container_name], capture_output=True, timeout=20)
    wall_total = time.perf_counter() - outer_start
    measurements = None
    for line in stdout.splitlines():
        if line.startswith('ROBOSIM_RESULT='):
            try:
                measurements = json.loads(line.split('=', 1)[1])
            except json.JSONDecodeError:
                measurements = None
    measurement_valid = bool(measurements) and (
        measurements.get('engine') == engine and
        measurements.get('scenario') == scenario and
        measurements.get('count') == count and
        measurements.get('measured_steps') == profile['measured_steps'] and
        measurements.get('dt_s') == profile['physics_dt_seconds'] and
        isinstance(measurements.get('core_wall_s'), (int, float)) and
        measurements.get('core_wall_s', 0) > 0 and
        measurements.get('memory_peak_bytes', 0) > 0
    )
    resource_valid = bool(measurements) and (
        measurements.get('cpu_max') == '200000 100000' and
        measurements.get('cpuset_effective') == profile['cpuset_cpus'] and
        measurements.get('memory_max') == str(memory) and
        measurements.get('memory_swap_max') == '0'
    )
    valid = (returncode == 0 and not timed_out and not state.get('OOMKilled', False)
             and measurement_valid and measurements.get('physics_valid', False) and resource_valid)
    return {
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'engine': engine, 'scenario': scenario, 'count': count, 'repetition': repetition,
        'image': IMAGES[engine], 'container_wall_s': round(wall_total, 6),
        'returncode': returncode, 'timed_out': timed_out,
        'oom_killed': state.get('OOMKilled', False),
        'valid': bool(valid), 'resource_valid': bool(resource_valid),
        'measurement_valid': bool(measurement_valid),
        'measurements': measurements, 'stderr_tail': stderr[-2000:],
        'stdout_tail': stdout[-1000:] if measurements is None else '',
        'host_platform': platform.platform(),
    }


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--pilot', action='store_true')
    group.add_argument('--main', action='store_true')
    group.add_argument('--repeats', type=int)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--overwrite', action='store_true')
    arguments = parser.parse_args()
    profile = get_profile()
    repetitions = (arguments.repeats if arguments.repeats is not None else
                   profile['repeats_main'] if arguments.main else profile['repeats_pilot'])
    if repetitions <= 0:
        parser.error('Number of repetitions must be positive')
    label = 'main' if arguments.main else 'pilot' if arguments.repeats is None else f'repeats_{repetitions}'
    output = arguments.output or RESULTS_DIR / f'{label}.jsonl'
    if output.exists() and not arguments.overwrite:
        parser.error(f'{output} already exists. Use --output with a new path or --overwrite')
    output.parent.mkdir(parents=True, exist_ok=True)
    image_ids = {}
    for image in sorted(set(IMAGES.values())):
        check = subprocess.run(['docker', 'image', 'inspect', image], capture_output=True, text=True)
        if check.returncode != 0:
            parser.error(f'Docker image unavailable: {image}. Build images first.')
        image_ids[image] = json.loads(check.stdout)[0]['Id']
    tasks = [(scenario, count, repetition)
             for scenario in SCENARIOS
             for count in BODY_COUNTS
             for repetition in range(repetitions)]
    random.Random(20261111).shuffle(tasks)
    total = len(tasks) * len(ENGINES)
    with output.open('w', encoding='utf-8') as destination:
        completed = 0
        for scenario, count, repetition in tasks:
            start_index = repetition % len(ENGINES)
            engine_order = ENGINES[start_index:] + ENGINES[:start_index]
            for engine in engine_order:
                completed += 1
                record = execute(engine, scenario, count, repetition, profile)
                record['image_id'] = image_ids[IMAGES[engine]]
                destination.write(json.dumps(record, ensure_ascii=False) + '\n')
                destination.flush()
                measurement = record['measurements'] or {}
                core = measurement.get('core_wall_s')
                print(f'{completed}/{total} {engine:8} {scenario:4} count={count:2} '
                      f'repeat={repetition:2} valid={record["valid"]} core_s={core}', flush=True)
    print(f'Raw results: {output}')


if __name__ == '__main__':
    main()
