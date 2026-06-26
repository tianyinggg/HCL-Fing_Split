#ifndef HCL_FING_SPLIT_BENCHES_COMMON_CSRBIN_UTILS_H_
#define HCL_FING_SPLIT_BENCHES_COMMON_CSRBIN_UTILS_H_

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace bench_common {

struct CsrMatrix {
  std::string name;
  int n = 0;
  int nnz = 0;
  uint64_t diag_filled = 0;
  std::vector<int> row_ptr;
  std::vector<int> col_idx;
  std::vector<double> values;
};

inline std::string BaseNameNoExt(const std::string& path) {
  size_t slash = path.find_last_of("/\\");
  std::string name = slash == std::string::npos ? path : path.substr(slash + 1);
  size_t dot = name.find_last_of('.');
  if (dot != std::string::npos) {
    name = name.substr(0, dot);
  }
  return name;
}

template <typename T>
inline void ReadExact(std::ifstream& in, T* data, size_t count, const std::string& what) {
  in.read(reinterpret_cast<char*>(data), static_cast<std::streamsize>(sizeof(T) * count));
  if (!in) {
    throw std::runtime_error("failed to read " + what);
  }
}

inline CsrMatrix ReadCsrbin(const std::string& path) {
  static const char kMagic[8] = {'C', 'S', 'R', 'L', 'O', 'W', '1', '\0'};
  constexpr uint32_t kRequiredFlags = 0x01 | 0x02 | 0x04 | 0x08;
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    throw std::runtime_error("failed to open csrbin: " + path);
  }

  char magic[8];
  uint32_t version = 0;
  uint32_t flags = 0;
  uint64_t n = 0;
  uint64_t nnz = 0;
  uint64_t diag_filled = 0;
  ReadExact(in, magic, 8, "magic");
  ReadExact(in, &version, 1, "version");
  ReadExact(in, &flags, 1, "flags");
  ReadExact(in, &n, 1, "n");
  ReadExact(in, &nnz, 1, "nnz");
  ReadExact(in, &diag_filled, 1, "diag_filled");

  if (std::memcmp(magic, kMagic, 8) != 0) {
    throw std::runtime_error("invalid csrbin magic");
  }
  if (version != 1) {
    throw std::runtime_error("unsupported csrbin version");
  }
  if ((flags & kRequiredFlags) != kRequiredFlags) {
    throw std::runtime_error("csrbin is not lower/sorted/double/0-based");
  }
  if (n > static_cast<uint64_t>(std::numeric_limits<int>::max()) ||
      nnz > static_cast<uint64_t>(std::numeric_limits<int>::max())) {
    throw std::runtime_error("sanity baselines currently require n and nnz <= INT_MAX");
  }

  std::vector<uint64_t> raw_row_ptr(n + 1);
  std::vector<uint32_t> raw_col_idx(nnz);
  std::vector<double> values(nnz);
  ReadExact(in, raw_row_ptr.data(), raw_row_ptr.size(), "row_ptr");
  ReadExact(in, raw_col_idx.data(), raw_col_idx.size(), "col_idx");
  ReadExact(in, values.data(), values.size(), "values");

  CsrMatrix matrix;
  matrix.name = BaseNameNoExt(path);
  matrix.n = static_cast<int>(n);
  matrix.nnz = static_cast<int>(nnz);
  matrix.diag_filled = diag_filled;
  matrix.row_ptr.resize(raw_row_ptr.size());
  matrix.col_idx.resize(raw_col_idx.size());
  for (size_t i = 0; i < raw_row_ptr.size(); ++i) {
    matrix.row_ptr[i] = static_cast<int>(raw_row_ptr[i]);
  }
  for (size_t i = 0; i < raw_col_idx.size(); ++i) {
    matrix.col_idx[i] = static_cast<int>(raw_col_idx[i]);
  }
  matrix.values = std::move(values);
  if (matrix.row_ptr.empty() || matrix.row_ptr.front() != 0 ||
      matrix.row_ptr.back() != matrix.nnz) {
    throw std::runtime_error("invalid csr row_ptr");
  }
  return matrix;
}

inline std::vector<double> ReadRhs(const std::string& path, int n) {
  std::ifstream in(path);
  if (!in) {
    throw std::runtime_error("failed to open rhs: " + path);
  }
  std::vector<double> rhs;
  rhs.reserve(static_cast<size_t>(n));
  double value = 0.0;
  while (in >> value) {
    rhs.push_back(value);
  }
  if (rhs.size() != static_cast<size_t>(n)) {
    throw std::runtime_error("rhs length mismatch");
  }
  return rhs;
}

inline double Residual(const CsrMatrix& matrix, const std::vector<double>& x,
                       const std::vector<double>& b) {
  long double diff2 = 0.0;
  long double b2 = 0.0;
  for (int row = 0; row < matrix.n; ++row) {
    long double ax = 0.0;
    for (int idx = matrix.row_ptr[row]; idx < matrix.row_ptr[row + 1]; ++idx) {
      ax += static_cast<long double>(matrix.values[idx]) *
            static_cast<long double>(x[matrix.col_idx[idx]]);
    }
    long double diff = ax - static_cast<long double>(b[row]);
    diff2 += diff * diff;
    b2 += static_cast<long double>(b[row]) * static_cast<long double>(b[row]);
  }
  if (b2 == 0.0) {
    return diff2 == 0.0 ? 0.0 : std::numeric_limits<double>::infinity();
  }
  return std::sqrt(static_cast<double>(diff2 / b2));
}

inline double Median(std::vector<double> values) {
  if (values.empty()) {
    throw std::runtime_error("median of empty vector");
  }
  std::sort(values.begin(), values.end());
  size_t mid = values.size() / 2;
  if (values.size() % 2 == 1) {
    return values[mid];
  }
  return 0.5 * (values[mid - 1] + values[mid]);
}

inline std::string FormatDouble(double value) {
  std::ostringstream out;
  out << std::setprecision(17) << value;
  return out.str();
}

inline void WriteVectorText(const std::string& path, const std::vector<double>& values) {
  std::filesystem::path out_path(path);
  if (out_path.has_parent_path()) {
    std::filesystem::create_directories(out_path.parent_path());
  }
  std::ofstream out(path);
  if (!out) {
    throw std::runtime_error("failed to open vector output: " + path);
  }
  out << std::setprecision(17);
  for (double value : values) {
    out << value << '\n';
  }
}

}  // namespace bench_common

#endif  // HCL_FING_SPLIT_BENCHES_COMMON_CSRBIN_UTILS_H_
