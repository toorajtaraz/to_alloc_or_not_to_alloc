#!/usr/bin/env bash
set -euo pipefail

############################
# Environment configuration
############################

PROJECT_ROOT="/home/toorajtaraz/Documents/projects/lab/mem_alloc_exprs"
ALLOC_LIB_DIR="$PROJECT_ROOT/installed_for_mem_alloc_exprs/lib64"

export LD_LIBRARY_PATH="$PROJECT_ROOT/installed_for_mem_alloc_exprs/lib:${LD_LIBRARY_PATH:-}"
export PATH="$PROJECT_ROOT/installed_for_mem_alloc_exprs/bin:${PATH}"

PYTHON_SCRIPT="src/count_mem_calls.py"


########################################
# Allocators to test
########################################
# key = label, value = allocator .so
# empty value → GNU / system malloc

declare -A ALLOCATORS=(
  [gnu]="gnu"
  [mimalloc]="libmimalloc.so"
  # [jemalloc]="libjemalloc.so"
  # [hoard]="libhoard.so"
)

########################################
# Commands to test
########################################

COMMANDS=(
  'foamTestTutorial -parallel -full mesh/moveDynamicMesh/bendJunction'
  # add more commands here
)

########################################
# Result storage
########################################
# Indexed as:
# results["allocator|command|metric"]
#
# metric ∈
# total_mean total_min total_max
# user_mean  user_min  user_max
# system_mean system_min system_max

declare -A results

########################################
# Run experiments
########################################

for allocator in "${!ALLOCATORS[@]}"; do
  allocator_lib="${ALLOCATORS[$allocator]}"

  for cmd in "${COMMANDS[@]}"; do
    echo "Running allocator=${allocator}"
    echo "  command=${cmd}"

    if [[ -n "$allocator_lib" ]]; then
      output=$(
        python "$PYTHON_SCRIPT" \
          -c "$cmd" \
          time \
          --iters 1 \
          --ldpreload "$ALLOC_LIB_DIR" \
          --allocator-replacement "$allocator_lib"
      )
    else
      # GNU malloc (no replacement)
      output=$(
        python "$PYTHON_SCRIPT" \
          -c "$cmd" \
          time \
          --iters 1
      )
    fi

    ####################################
    # Parse output
    ####################################
    # Expect exactly 3 lines:
    # total:  mean min max
    # user:   mean min max
    # system: mean min max

    readarray -t lines <<< "$output"

    if [[ "${#lines[@]}" -ne 3 ]]; then
      echo "ERROR: Expected 3 lines of output, got ${#lines[@]}"
      echo "Output was:"
      echo "$output"
      exit 1
    fi

    read total_mean total_min total_max <<< "${lines[0]}"
    read user_mean  user_min  user_max  <<< "${lines[1]}"
    read sys_mean   sys_min   sys_max   <<< "${lines[2]}"

    key_prefix="${allocator}|${cmd}"

    results["$key_prefix|total_mean"]="$total_mean"
    results["$key_prefix|total_min"]="$total_min"
    results["$key_prefix|total_max"]="$total_max"

    results["$key_prefix|user_mean"]="$user_mean"
    results["$key_prefix|user_min"]="$user_min"
    results["$key_prefix|user_max"]="$user_max"

    results["$key_prefix|system_mean"]="$sys_mean"
    results["$key_prefix|system_min"]="$sys_min"
    results["$key_prefix|system_max"]="$sys_max"
  done
done

########################################
# Dump results (CSV)
########################################

echo
echo "allocator,command,"\
"total_mean,total_min,total_max,"\
"user_mean,user_min,user_max,"\
"system_mean,system_min,system_max"

for allocator in "${!ALLOCATORS[@]}"; do
  for cmd in "${COMMANDS[@]}"; do
    key_prefix="${allocator}|${cmd}"

    echo "${allocator},\"${cmd}\","\
"${results[$key_prefix|total_mean]},"\
"${results[$key_prefix|total_min]},"\
"${results[$key_prefix|total_max]},"\
"${results[$key_prefix|user_mean]},"\
"${results[$key_prefix|user_min]},"\
"${results[$key_prefix|user_max]},"\
"${results[$key_prefix|system_mean]},"\
"${results[$key_prefix|system_min]},"\
"${results[$key_prefix|system_max]}"
  done
done

