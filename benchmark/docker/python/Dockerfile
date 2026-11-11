FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1
RUN python -m pip install --no-cache-dir --only-binary=:all: pybullet==3.2.7 mujoco==3.16.0 && python -m pip check
WORKDIR /app/benchmark
COPY spec.py python_engine.py /app/benchmark/
ENTRYPOINT ["python", "python_engine.py"]
