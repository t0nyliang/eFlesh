#!/bin/bash

# Simple build script for microstructure_inflators
# This script builds the essential tools needed for eFlesh

set -e  # Exit on any error

echo "Building microstructure_inflators..."

# Create build directory
mkdir -p build
cd build

# Configure with CMake
echo "Configuring with CMake..."
cmake -DCMAKE_BUILD_TYPE=release ..

# Build the essential tools
echo "Building essential tools..."
make -j$(nproc) stitch_cells_cli
make -j$(nproc) cut_cells_cli  
make -j$(nproc) stack_cells

echo "Build completed successfully!"
echo "Built tools:"
echo "  - stitch_cells_cli"
echo "  - cut_cells_cli"
echo "  - stack_cells" 