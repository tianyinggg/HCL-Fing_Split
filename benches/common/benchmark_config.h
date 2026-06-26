#ifndef HCL_FING_SPLIT_BENCHES_COMMON_BENCHMARK_CONFIG_H_
#define HCL_FING_SPLIT_BENCHES_COMMON_BENCHMARK_CONFIG_H_

#include <algorithm>
#include <cctype>
#include <fstream>
#include <map>
#include <stdexcept>
#include <string>

namespace bench_common {

inline std::string TrimConfig(std::string value) {
  const char* ws = " \t\r\n";
  size_t first = value.find_first_not_of(ws);
  if (first == std::string::npos) {
    return "";
  }
  size_t last = value.find_last_not_of(ws);
  return value.substr(first, last - first + 1);
}

inline std::string LowerConfig(std::string value) {
  std::transform(value.begin(), value.end(), value.begin(),
                 [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
  return value;
}

inline std::string StripConfigQuotes(std::string value) {
  value = TrimConfig(value);
  if (value.size() >= 2 &&
      ((value.front() == '"' && value.back() == '"') ||
       (value.front() == '\'' && value.back() == '\''))) {
    return value.substr(1, value.size() - 2);
  }
  return value;
}

inline std::string ReadConfigValue(const std::string& path, const std::string& key,
                                   const std::string& fallback) {
  std::ifstream in(path);
  if (!in) {
    return fallback;
  }
  std::string line;
  const std::string prefix = key + ":";
  while (std::getline(in, line)) {
    size_t comment = line.find('#');
    if (comment != std::string::npos) {
      line = line.substr(0, comment);
    }
    line = TrimConfig(line);
    if (line.rfind(prefix, 0) == 0) {
      return StripConfigQuotes(line.substr(prefix.size()));
    }
  }
  return fallback;
}

inline int ReadIntConfig(const std::string& path, const std::string& key, int fallback) {
  std::string value = ReadConfigValue(path, key, "");
  if (value.empty()) {
    return fallback;
  }
  return std::stoi(value);
}

inline void ApplyTimingConfig(const std::string& config_path, std::string* mode,
                              int* warmup, int* repeat_solve,
                              int* repeat_analysis, std::string* statistic) {
  *mode = LowerConfig(*mode);
  if (*mode != "quick" && *mode != "benchmark") {
    throw std::runtime_error("--mode must be quick or benchmark");
  }

  if (*mode == "quick") {
    if (*warmup < 0) {
      *warmup = ReadIntConfig(config_path, "quick_warmup", 1);
    }
    if (*repeat_solve < 0) {
      *repeat_solve = ReadIntConfig(config_path, "quick_repeat_solve", 3);
    }
    if (*repeat_analysis < 0) {
      *repeat_analysis = ReadIntConfig(config_path, "quick_repeat_analysis", 3);
    }
  } else {
    if (*warmup < 0) {
      *warmup = ReadIntConfig(config_path, "warmup", 5);
    }
    if (*repeat_solve < 0) {
      *repeat_solve = ReadIntConfig(config_path, "repeat_solve", 50);
    }
    if (*repeat_analysis < 0) {
      *repeat_analysis = ReadIntConfig(config_path, "repeat_analysis", 10);
    }
  }

  *statistic = LowerConfig(ReadConfigValue(config_path, "statistic", "median"));
  if (*statistic != "median") {
    throw std::runtime_error("only statistic: median is supported");
  }
  if (*warmup < 0 || *repeat_solve <= 0 || *repeat_analysis <= 0) {
    throw std::runtime_error("warmup must be >= 0 and repeats must be > 0");
  }
}

inline void FillTimingRow(std::map<std::string, std::string>* row,
                          const std::string& mode, int warmup,
                          int repeat_solve, int repeat_analysis,
                          const std::string& statistic) {
  (*row)["mode"] = mode;
  (*row)["warmup"] = std::to_string(warmup);
  (*row)["repeat_solve"] = std::to_string(repeat_solve);
  (*row)["repeat_analysis"] = std::to_string(repeat_analysis);
  (*row)["statistic"] = statistic;
}

}  // namespace bench_common

#endif  // HCL_FING_SPLIT_BENCHES_COMMON_BENCHMARK_CONFIG_H_
