CUDA_HOME ?= /usr/local/cuda
NVCC ?= $(CUDA_HOME)/bin/nvcc
REPO_ROOT := $(abspath ../..)
HCL_DIR := $(REPO_ROOT)/HCL-Fing

TARGET := hcl_fing_baseline
SRC := hcl_fing_baseline.cu
HCL_SRCS := \
	$(HCL_DIR)/analysis/analysis_csr.cu \
	$(HCL_DIR)/solver/solve_csr_multirow.cu

NVCCFLAGS := -std=c++17 -O3 -DNDEBUG -m64 -gencode=arch=compute_89,code=sm_89
INCLUDES := -I$(REPO_ROOT)/benches/common -I$(HCL_DIR)/header -I$(CUDA_HOME)/include
LIBS := -L$(CUDA_HOME)/lib64 -lcudart

all: $(TARGET)

$(TARGET): $(SRC) $(HCL_SRCS) $(REPO_ROOT)/benches/common/benchmark_config.h $(REPO_ROOT)/benches/common/csrbin_utils.h $(REPO_ROOT)/benches/common/result_csv.h
	$(NVCC) $(NVCCFLAGS) $(INCLUDES) -DDEFAULT_REPO_ROOT=\"$(REPO_ROOT)\" $(SRC) $(HCL_SRCS) -o $@ $(LIBS)

.PHONY: clean
clean:
	rm -f $(TARGET)
