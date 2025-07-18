# Prepare dependencies
#
# For each third-party library, if the appropriate target doesn't exist yet,
# download it via external project, and add_subdirectory to build it alongside
# this project.

### Configuration
set(MICRO_ROOT     "${CMAKE_CURRENT_LIST_DIR}/..")
set(MICRO_EXTERNAL "${MICRO_ROOT}/3rdparty")

# Download and update 3rdparty libraries
list(APPEND CMAKE_MODULE_PATH ${CMAKE_CURRENT_LIST_DIR})
list(REMOVE_DUPLICATES CMAKE_MODULE_PATH)
include(MicroDownloadExternal)

################################################################################
# Required libraries
################################################################################

# Eigen
if(NOT TARGET Eigen3::Eigen)
    add_library(micro_eigen INTERFACE)
    micro_download_eigen()
    target_include_directories(micro_eigen SYSTEM INTERFACE ${MICRO_EXTERNAL}/eigen)
    add_library(Eigen3::Eigen ALIAS micro_eigen)
endif()

# openvdb
if (MICRO_WITH_OPENVDB)
    if(NOT TARGET openvdb)
        include(openvdb)
        get_target_property(realTarget openvdb ALIASED_TARGET)
        target_compile_definitions(${realTarget} INTERFACE -DMICRO_WITH_OPENVDB)
    endif()
endif()

# TBB library configuration
# We need tbbmalloc which MeshFEM doesn't build by default
if(NOT TARGET TBB::tbb)
    # First try to find system TBB
    find_package(TBB QUIET)
    
    if(TBB_FOUND)
        # System TBB found, create interface target
        add_library(tbb_tbb INTERFACE)
        add_library(TBB::tbb ALIAS tbb_tbb)
        target_link_libraries(tbb_tbb INTERFACE TBB::tbb)
        
        # Check if tbbmalloc is available
        if(TARGET TBB::tbbmalloc)
            target_link_libraries(tbb_tbb INTERFACE TBB::tbbmalloc)
        endif()
        
        target_compile_definitions(tbb_tbb INTERFACE -DMICRO_WITH_TBB)
        message(STATUS "Using system TBB")
    else()
        # System TBB not found, download and build from source
        message(STATUS "System TBB not found, downloading and building from source")
        micro_download_tbb()
        
        # Configure oneTBB build options for modern CMake build
        set(TBB_TEST OFF CACHE BOOL "Build TBB tests" FORCE)
        set(TBB_EXAMPLES OFF CACHE BOOL "Build TBB examples" FORCE)
        set(TBB_BENCH OFF CACHE BOOL "Build TBB benchmarks" FORCE)
        set(TBB_STRICT OFF CACHE BOOL "Use strict mode" FORCE)
        set(TBB_PYTHON OFF CACHE BOOL "Build Python bindings" FORCE)
        set(TBB_CPF OFF CACHE BOOL "Build CPF" FORCE)
        set(TBB_TBBMALLOC ON CACHE BOOL "Build tbbmalloc" FORCE)
        set(TBB_TBBMALLOC_PROXY OFF CACHE BOOL "Build tbbmalloc_proxy" FORCE)
        
        # Add TBB subdirectory - oneTBB uses modern CMake
        add_subdirectory(${MICRO_EXTERNAL}/tbb tbb EXCLUDE_FROM_ALL)
        
        # Create interface target using modern oneTBB targets
        add_library(tbb_tbb INTERFACE)
        add_library(TBB::tbb ALIAS tbb_tbb)
        target_link_libraries(tbb_tbb INTERFACE TBB::tbb)
        
        # Check if tbbmalloc is available and link it
        if(TARGET TBB::tbbmalloc)
            target_link_libraries(tbb_tbb INTERFACE TBB::tbbmalloc)
        endif()
        
        target_compile_definitions(tbb_tbb INTERFACE -DMICRO_WITH_TBB)
        
        message(STATUS "Built oneTBB from source")
    endif()
endif()

# C++11 threads
find_package(Threads REQUIRED) # provides Threads::Threads

# json library
if(NOT TARGET nlohmann_json::nlohmann_json)
    add_library(meshfem_json INTERFACE)
    micro_download_json()
    target_include_directories(meshfem_json SYSTEM INTERFACE ${MICRO_EXTERNAL}/json)
    target_include_directories(meshfem_json SYSTEM INTERFACE ${MICRO_EXTERNAL}/json/nlohmann)
    add_library(nlohmann_json::nlohmann_json ALIAS meshfem_json)
endif()

# Optional library
if(NOT TARGET optional::optional)
    micro_download_optional()
    add_library(optional_lite INTERFACE)
    target_include_directories(optional_lite SYSTEM INTERFACE ${MICRO_EXTERNAL}/optional/include)
    add_library(optional::optional ALIAS optional_lite)
endif()

# Triangle library
# include(triangle)
if(NOT TARGET triangle::triangle)
    micro_download_triangle()
    add_subdirectory(${MICRO_EXTERNAL}/triangle triangle)
    target_include_directories(triangle SYSTEM INTERFACE ${MICRO_EXTERNAL}/triangle)
    add_library(triangle::triangle ALIAS triangle)
endif()

# MeshFEM library
# if(NOT TARGET MeshFEM)
#     micro_download_meshfem()
#     option(MESHFEM_WITH_CERES "Compile MeshFEM with Ceres" ${MICRO_WITH_CERES})
#     add_subdirectory(${MICRO_EXTERNAL}/MeshFEM MeshFEM)
# endif()

# CLI11 library
if(MICRO_BUILD_BINARIES)
 if(NOT TARGET CLI11::CLI11)
     micro_download_cli11()
     add_library(CLI11 INTERFACE)
     target_include_directories(CLI11 SYSTEM INTERFACE ${MICRO_EXTERNAL}/CLI11/include)
     add_library(CLI11::CLI11 ALIAS CLI11)
 endif()
endif()

# CGAL library
if(NOT TARGET CGAL::CGAL)
    micro_download_cgal()
    set(CGAL_DIR ${MICRO_EXTERNAL}/cgal)
    find_package(CGAL CONFIG REQUIRED COMPONENTS PATHS ${CGAL_DIR} NO_DEFAULT_PATH)
endif()

# Boost library
if(MICRO_BUILD_BINARIES)
    find_package(Boost 1.54 REQUIRED COMPONENTS filesystem system program_options QUIET)
    if(NOT TARGET micro::boost)
        add_library(meshfem_boost INTERFACE)
        if(TARGET Boost::filesystem AND TARGET Boost::system AND TARGET Boost::program_options)
            target_link_libraries(meshfem_boost INTERFACE
                Boost::filesystem
                Boost::system
                Boost::program_options)
        else()
            # When CMake and Boost versions are not in sync, imported targets may not be available... (sigh)
            target_include_directories(meshfem_boost SYSTEM INTERFACE ${Boost_INCLUDE_DIRS})
            target_link_libraries(meshfem_boost INTERFACE ${Boost_LIBRARIES})
        endif()
        add_library(micro::boost ALIAS meshfem_boost)
    endif()
endif()

# Nanoflann
if(NOT TARGET nanoflann::nanoflann)
    micro_download_nanoflann()
    add_library(nanoflann INTERFACE)
    add_library(nanoflann::nanoflann ALIAS nanoflann)
    target_include_directories(nanoflann INTERFACE ${MICRO_EXTERNAL}/nanoflann/include)
endif()

# Accelerate framework
# if(NOT TARGET micro::accelerate)
#     if(APPLE)
#         find_library(AccelerateFramework Accelerate)
#         add_library(micro_accelerate INTERFACE)
#         target_link_libraries(micro_accelerate INTERFACE ${AccelerateFramework})
#         add_library(micro::accelerate ALIAS micro_accelerate)
#     else()
#         add_library(micro::accelerate INTERFACE IMPORTED)
#     endif()
# endif()

# Catch2
# if(NOT TARGET Catch2::Catch2 AND (CMAKE_SOURCE_DIR STREQUAL PROJECT_SOURCE_DIR))
#     micro_download_catch()
#     add_subdirectory(${MICRO_EXTERNAL}/Catch2)
#     list(APPEND CMAKE_MODULE_PATH ${MICRO_EXTERNAL}/Catch2/contrib)
# endif()

# Cotire
if(MICRO_WITH_COTIRE)
    micro_download_cotire()
endif()

################################################################################
# Optional libraries
################################################################################

# libigl library
if(NOT TARGET libigl)
    if(NOT TARGET igl::core)
        micro_download_libigl()
        find_package(LIBIGL QUIET)
    endif()
    if(LIBIGL_FOUND)
        add_library(micro_libigl INTERFACE)
        target_link_libraries(micro_libigl INTERFACE igl::core)
        target_compile_definitions(micro_libigl INTERFACE -DHAS_LIBIGL)
        add_library(libigl ALIAS micro_libigl)
    else()
        add_library(libigl INTERFACE IMPORTED)
    endif()
endif()

# VCG library
if(NOT TARGET micro::vcglib)
    find_package(VCGlib QUIET)
    if(VCGLIB_FOUND)
        add_library(micro_vcglib INTERFACE)
        target_link_libraries(micro_vcglib INTERFACE VCGlib::core)
        target_compile_definitions(micro_vcglib INTERFACE -DHAS_VCGLIB)
        add_library(micro::vcglib ALIAS micro_vcglib)
    else()
        message(STATUS "VCGLib not found; disabling Luigi's Inflator")
        add_library(micro::vcglib INTERFACE IMPORTED)
    endif()
endif()

# Sanitizers
if(MICRO_WITH_SANITIZERS)
    if(NOT COMMAND add_sanitizers)
        micro_download_sanitizers()
    endif()
    find_package(Sanitizers)
endif()
