#include <gz/sim/Server.hh>
#include <gz/sim/ServerConfig.hh>
#include <gz/sim/System.hh>
#include <gz/sim/EntityComponentManager.hh>
#include <gz/sim/components/Model.hh>
#include <gz/sim/components/Name.hh>
#include <gz/sim/components/Pose.hh>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <fstream>
#include <iostream>
#include <memory>
#include <optional>
#include <sstream>
#include <string>
#include <vector>

class HeightMonitor final : public gz::sim::System, public gz::sim::ISystemPostUpdate {
public:
    void PostUpdate(const gz::sim::UpdateInfo &info,
                    const gz::sim::EntityComponentManager &manager) override {
        if (info.paused || info.iterations < 2095) return;
        std::vector<double> current;
        manager.Each<gz::sim::components::Model,
                     gz::sim::components::Name,
                     gz::sim::components::Pose>(
            [&](const gz::sim::Entity &,
                const gz::sim::components::Model *,
                const gz::sim::components::Name *name,
                const gz::sim::components::Pose *pose) {
                if (name->Data().rfind("box_", 0) == 0) {
                    current.push_back(pose->Data().Pos().Z());
                }
                return true;
            });
        heights = std::move(current);
    }

    std::vector<double> heights;
};

std::string readFile(const std::string &path) {
    std::ifstream input(path);
    if (!input) return "";
    std::ostringstream output;
    output << input.rdbuf();
    return output.str();
}

std::optional<double> cpuSeconds() {
    std::istringstream input(readFile("/sys/fs/cgroup/cpu.stat"));
    std::string label;
    long long value;
    while (input >> label >> value) {
        if (label == "usage_usec") return value / 1000000.0;
    }
    return std::nullopt;
}

std::string firstLine(const std::string &path) {
    auto content = readFile(path);
    auto location = content.find('\n');
    if (location != std::string::npos) content.resize(location);
    return content;
}

int main(int argc, char **argv) {
    if (argc != 4) {
        std::cerr << "usage: gazebo_benchmark SCENARIO COUNT WORLD_PATH\n";
        return 2;
    }
    const std::string scenario = argv[1];
    const int count = std::stoi(argv[2]);
    if ((scenario != "rest" && scenario != "drop") ||
        (count != 1 && count != 8 && count != 32)) return 2;

    constexpr unsigned int warmupSteps = 100;
    constexpr unsigned int measuredSteps = 2000;
    constexpr double physicsDt = 0.01;
    gz::sim::ServerConfig config;
    if (!config.SetSdfFile(argv[3])) return 3;
    gz::sim::Server server(config);
    auto monitor = std::make_shared<HeightMonitor>();
    auto added = server.AddSystem(monitor);
    if (!added.has_value() || !added.value()) return 4;

    if (!server.Run(true, warmupSteps, false)) return 5;
    const auto startingIterations = server.IterationCount();
    const auto startingCpu = cpuSeconds();
    const auto beginning = std::chrono::steady_clock::now();
    if (!server.Run(true, measuredSteps, false)) return 6;
    const auto finished = std::chrono::steady_clock::now();
    const auto endingCpu = cpuSeconds();
    const auto endingIterations = server.IterationCount();
    const double elapsed = std::chrono::duration<double>(finished - beginning).count();

    const bool stepValid = startingIterations.has_value() && endingIterations.has_value() &&
        endingIterations.value() == startingIterations.value() + measuredSteps;
    const bool heightValid = static_cast<int>(monitor->heights.size()) == count &&
        std::all_of(monitor->heights.begin(), monitor->heights.end(), [](double height) {
            return std::isfinite(height) && std::abs(height - 0.06) < 0.035;
        });
    const bool valid = stepValid && heightValid;
    double minHeight = 0.0;
    double maxHeight = 0.0;
    if (!monitor->heights.empty()) {
        minHeight = *std::min_element(monitor->heights.begin(), monitor->heights.end());
        maxHeight = *std::max_element(monitor->heights.begin(), monitor->heights.end());
    }
    std::cout << "ROBOSIM_RESULT={\"engine\":\"gazebo\",\"scenario\":\"" << scenario
              << "\",\"count\":" << count
              << ",\"measured_steps\":" << measuredSteps
              << ",\"dt_s\":" << physicsDt
              << ",\"core_wall_s\":" << elapsed
              << ",\"core_cpu_s\":";
    if (startingCpu && endingCpu) std::cout << endingCpu.value() - startingCpu.value();
    else std::cout << "null";
    std::cout << ",\"steps_per_second\":" << measuredSteps / elapsed
              << ",\"memory_peak_bytes\":" << (firstLine("/sys/fs/cgroup/memory.peak").empty() ? "0" : firstLine("/sys/fs/cgroup/memory.peak"))
              << ",\"physics_valid\":" << (valid ? "true" : "false")
              << ",\"heights_min_m\":" << minHeight
              << ",\"heights_max_m\":" << maxHeight
              << ",\"cpu_max\":\"" << firstLine("/sys/fs/cgroup/cpu.max")
              << "\",\"memory_max\":\"" << firstLine("/sys/fs/cgroup/memory.max")
              << "\",\"cpuset_effective\":\"" << firstLine("/sys/fs/cgroup/cpuset.cpus.effective")
              << "\",\"memory_swap_max\":\"" << firstLine("/sys/fs/cgroup/memory.swap.max")
              << "\"}" << std::endl;
    return valid ? 0 : 7;
}
