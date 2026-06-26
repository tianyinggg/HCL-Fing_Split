CXX ?= g++
REPO_ROOT := $(abspath ../..)

TARGET := mkl_baseline
SRC := mkl_baseline.cpp

CXXFLAGS := -std=c++17 -O3 -DNDEBUG -I$(REPO_ROOT)/benches/common -I/usr/include/mkl
LIBS := -lmkl_rt -lpthread -lm -ldl

all: $(TARGET)

$(TARGET): $(SRC) $(REPO_ROOT)/benches/common/benchmark_config.h $(REPO_ROOT)/benches/common/csrbin_utils.h $(REPO_ROOT)/benches/common/result_csv.h
	$(CXX) $(CXXFLAGS) -DDEFAULT_REPO_ROOT=\"$(REPO_ROOT)\" $< -o $@ $(LIBS)

.PHONY: clean
clean:
	rm -f $(TARGET)
