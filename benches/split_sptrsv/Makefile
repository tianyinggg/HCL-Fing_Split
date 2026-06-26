CUDA_HOME ?= /usr/local/cuda
NVCC ?= $(CUDA_HOME)/bin/nvcc
REPO_ROOT := $(abspath ../..)
SPLIT_DIR := $(REPO_ROOT)/Split_SpTRSV

TARGET := split_sptrsv_baseline
SRC := split_sptrsv_baseline.cu
SPLIT_SRCS := \
	$(SPLIT_DIR)/src/SILU.cpp \
	$(SPLIT_DIR)/src/SILU_GPU.cu \
	$(SPLIT_DIR)/src/matrix.cpp

NVCCFLAGS := -std=c++17 -O3 -DNDEBUG -m64 -gencode=arch=compute_89,code=sm_89
INCLUDES := -I$(REPO_ROOT)/benches/common -I$(SPLIT_DIR)/include -I/usr/include/mkl -I$(CUDA_HOME)/include
LIBS := -L$(CUDA_HOME)/lib64 -lcusparse -lcublas -lcudart -lufget -lmkl_rt -lpthread -lm -ldl

all: $(TARGET)

$(TARGET): $(SRC) $(SPLIT_SRCS) $(REPO_ROOT)/benches/common/benchmark_config.h $(REPO_ROOT)/benches/common/csrbin_utils.h $(REPO_ROOT)/benches/common/result_csv.h
	$(NVCC) $(NVCCFLAGS) $(INCLUDES) -DDEFAULT_REPO_ROOT=\"$(REPO_ROOT)\" $(SRC) $(SPLIT_SRCS) -o $@ $(LIBS)

.PHONY: clean
clean:
	rm -f $(TARGET)
