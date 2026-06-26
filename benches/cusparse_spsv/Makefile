CUDA_HOME ?= /usr/local/cuda
NVCC ?= $(CUDA_HOME)/bin/nvcc
REPO_ROOT := $(abspath ../..)

TARGET := cusparse_spsv_baseline
SRC := cusparse_spsv_baseline.cu

NVCCFLAGS := -std=c++17 -O3 -DNDEBUG -m64 -gencode=arch=compute_89,code=sm_89
INCLUDES := -I$(REPO_ROOT)/benches/common -I$(CUDA_HOME)/include
LIBS := -L$(CUDA_HOME)/lib64 -lcusparse -lcudart

all: $(TARGET)

$(TARGET): $(SRC) $(REPO_ROOT)/benches/common/benchmark_config.h $(REPO_ROOT)/benches/common/result_csv.h
	$(NVCC) $(NVCCFLAGS) $(INCLUDES) -DDEFAULT_REPO_ROOT=\"$(REPO_ROOT)\" $< -o $@ $(LIBS)

.PHONY: clean
clean:
	rm -f $(TARGET)
