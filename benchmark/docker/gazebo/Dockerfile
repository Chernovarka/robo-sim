FROM ubuntu:26.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl gnupg cmake g++ make pkg-config && \
    curl -fsSL https://packages.osrfoundation.org/gazebo.gpg -o /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] https://packages.osrfoundation.org/gazebo/ubuntu-stable resolute main" > /etc/apt/sources.list.d/gazebo-stable.list && \
    apt-get update && apt-get install -y --no-install-recommends libgz-sim10-dev gz-sim10-server && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app/benchmark
COPY CMakeLists.txt gazebo_runner.cpp /app/benchmark/
COPY worlds/ /app/benchmark/worlds/
RUN cmake -S . -B /app/gazebo-build -DCMAKE_BUILD_TYPE=Release && cmake --build /app/gazebo-build -j 2
ENV HOME=/tmp
ENTRYPOINT ["/app/gazebo-build/robosim_gazebo_benchmark"]
