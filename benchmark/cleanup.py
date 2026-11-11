import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
OLD_PATHS = (
    'build', 'configs', 'docker', 'scripts', 'tests',
    'data/benchmark_s3_waypoints.csv', 'data/experiments',
    'docs/CONTAINER_RUNNER_V1.md', 'docs/EXPERIMENT_V2.md',
    'docs/MUJOCO_URDF_SEARCH.md', 'docs/SEARCH_CONTROLLER_V1.md',
    'README_EXPERIMENT_V2.md', 'README_GAZEBO_SEARCH.md', 'README_SEARCH_V1.md',
    'README_INSTALL.md',
    'src/robo_sim/checker', 'src/robo_sim/controllers',
    'src/robo_sim/experiments', 'src/robo_sim/scenes',
    'src/robo_sim/sensors', 'src/robo_sim/simulators',
    'src/robo_sim/tasks', 'src/robo_sim/utils',
    'README.md',
)
IGNORE = ('build/', '.venv/', '__pycache__/', '*.pyc', 'benchmark/worlds/')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    arguments = parser.parse_args()
    if not (ROOT / 'benchmark' / 'spec.py').exists():
        raise SystemExit('Benchmark package not found in the project root')
    present = [path for path in OLD_PATHS if (ROOT / path).exists()]
    print('Files and directories to move outside this project:')
    for path in present:
        print('  ', path)
    print('Keep: benchmark/, docs/RESEARCH_PROTOCOL.md, docs/SELECTION_REPORT_PRELIMINARY.md,')
    print('      data/selection/, src/robo_sim/robots/, pyproject.toml, uv.lock, .git/')
    if not arguments.apply:
        print('Dry run only. To archive old files and create the clean README:')
        print('  python benchmark/cleanup.py --apply')
        return
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = ROOT.parent / f'{ROOT.name}-legacy-{stamp}'
    if backup.exists():
        raise SystemExit(f'Archive already exists: {backup}')
    backup.mkdir()
    for relative in present:
        source = ROOT / relative
        destination = backup / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
    fresh_readme = (ROOT / 'benchmark' / 'CLEAN_README.md').read_text(encoding='utf-8')
    (ROOT / 'README.md').write_text(fresh_readme, encoding='utf-8')
    ignore_file = ROOT / '.gitignore'
    existing = ignore_file.read_text(encoding='utf-8') if ignore_file.exists() else ''
    extra = ''.join(f'{value}\n' for value in IGNORE if value not in existing.splitlines())
    if extra:
        ignore_file.write_text(existing.rstrip() + '\n' + extra, encoding='utf-8')
    print('Old project files archived at:', backup)
    print('No archive contents were deleted. Review git diff and git status before committing.')


if __name__ == '__main__':
    main()
