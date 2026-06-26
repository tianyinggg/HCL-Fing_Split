#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
out_dir="${repo_root}/logs/env"
mkdir -p "${out_dir}"

(nvidia-smi || true) > "${out_dir}/nvidia-smi.txt" 2>&1
(nvcc --version || true) > "${out_dir}/nvcc_version.txt" 2>&1
(gcc --version || true) > "${out_dir}/gcc_version.txt" 2>&1

if [[ -x "${repo_root}/Split_SpTRSV/build/silu_test" ]]; then
  (ldd "${repo_root}/Split_SpTRSV/build/silu_test" || true) > "${out_dir}/ldd_split.txt" 2>&1
fi

if [[ -x "${repo_root}/HCL-Fing/sptrsv_double" ]]; then
  (ldd "${repo_root}/HCL-Fing/sptrsv_double" || true) > "${out_dir}/ldd_hcl.txt" 2>&1
fi
