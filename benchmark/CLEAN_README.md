# RoboSim — выбор физического симулятора

Цель этапа — выбрать два движка из PyBullet, MuJoCo и Gazebo Jetty по производительности, пиковому потреблению оперативной памяти и корректности исполнения одинаковых физических нагрузок под лимитами Docker.

## Запуск

```bash
python benchmark/make_worlds.py
python -m unittest discover -s benchmark -p 'test_*.py' -v
docker build -f benchmark/docker/python/Dockerfile -t robosim-selection-python:v1 benchmark
docker build -f benchmark/docker/gazebo/Dockerfile -t robosim-selection-gazebo:v1 benchmark
python benchmark/run.py --pilot
python benchmark/report.py data/selection/pilot.jsonl --output docs/SELECTION_PILOT.md
python benchmark/run.py --main
python benchmark/report.py data/selection/main.jsonl --output docs/SELECTION_RESULTS.md
```

Запускай из корня репозитория. Для отборочного решения используй **основной** прогон, а не пилотный.

Исходные параметры: `benchmark/spec.py`, ресурсные ограничения: `benchmark/profile.json`, протокол: `docs/RESEARCH_PROTOCOL.md`.

В `data/selection/` сохраняются сырые результаты всех запусков; файл отчёта создаётся автоматически и должен проверяться вместе с ними. Никаких маршрутов и алгоритмов навигации в этом этапе нет.
