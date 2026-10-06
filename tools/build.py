import os
import shutil
from typing import Dict, Any

from setuptools.command.build_ext import build_ext
from setuptools import Distribution, Extension
from Cython.Build import cythonize

from cmake_extension import CMakeExtension, ExtensionBuilder


def get_numpy_include():
    import builtins

    builtins.__NUMPY_SETUP__ = False
    try:
        import numpy as np
    except ImportError:
        raise SystemExit("CEFWeaver requires NumPy for setup")
    return np.get_include()


compile_args = ["-march=native", "-O3"]
link_args = []
include_dirs = [get_numpy_include(), "cmake_build", "."]
libraries = ["hello"]


def build() -> None:
    cmake_modules = [
        CMakeExtension("libhello", sourcedir="src")]

    distribution = Distribution({"name": "extended", "ext_modules": cmake_modules})
    # distribution.package_dir = {"extended": "extended"}

    # Cmake Build
    cmd = ExtensionBuilder(distribution)
    cmd.ensure_finalized()
    cmd.run()

    extensions = [
        Extension(
            "hello2",
            ["native/*.pyx"],
            extra_compile_args=compile_args,
            extra_link_args=link_args,
            include_dirs=include_dirs,
            libraries=libraries,
        )
    ]
    cython_modules = cythonize(
        extensions,
        include_path=include_dirs,
        # compiler_directives={"binding": True, "language_level": 3},
    )

    distribution = Distribution({"name": "extended", "ext_modules": cmake_modules})
    distribution.package_dir = {"extended": "extended"}

    # Cmake Build
    cmd = build_ext(distribution)
    cmd.ensure_finalized()
    cmd.run()

    # print('-' * 80)
    print(cmd.get_outputs())
    # print(cmd.get_output_mapping())
    # print(dir(cmd))
    # print('-' * 80)

    # a = ['announce', 'boolean_options', 'build_cmake_extension', 'build_extension', 'build_extensions', 'build_lib', 'build_temp', 'check_extensions_list', 'command_consumes_arguments', 'compiler', 'copy_extensions_to_source', 'copy_file', 'copy_tree', 'cython_c_in_temp', 'cython_compile_time_env', 'cython_cplus', 'cython_create_listing', 'cython_directives', 'cython_gdb', 'cython_gen_pxi', 'cython_include_dirs', 'cython_line_directives', 'debug', 'debug_print', 'define', 'description', 'distribution', 'dump_options', 'editable_mode', 'ensure_dirname', 'ensure_filename', 'ensure_finalized', 'ensure_string', 'ensure_string_list', 'execute', 'ext_map', 'extensions', 'finalize_options', 'finalized', 'find_swig', 'force', 'get_command_name', 'get_export_symbols', 'get_ext_filename', 'get_ext_fullname', 'get_ext_fullpath', 'get_extension_attr', 'get_finalized_command', 'get_libraries', 'get_output_mapping', 'get_outputs', 'get_source_files', 'get_sub_commands', 'help', 'help_options', 'include_dirs', 'initialize_options', 'inplace', 'libraries', 'library_dirs', 'link_objects', 'links_to_dynamic', 'make_archive', 'make_file', 'mkpath', 'move_file', 'package', 'parallel', 'plat_name', 'reinitialize_command', 'rpath', 'run', 'run_command', 'sep_by', 'set_undefined_options', 'setup_shlib_compiler', 'shlib_compiler', 'shlibs', 'spawn', 'sub_commands', 'swig', 'swig_cpp', 'swig_opts', 'swig_sources', 'undef', 'user', 'user_options', 'validate_cmake', 'verbose', 'warn', 'write_stub']
    #
    # for item in a:
    #     print(f'{item}: {getattr(cmd, item)}')
    #
    # # Copy built extensions back to the project
    # for output in cmd.get_outputs():
    #     relative_extension = os.path.relpath(output, cmd.build_temp)
    #     shutil.copyfile(output, relative_extension)
    #     mode = os.stat(relative_extension).st_mode
    #     mode |= (mode & 0o444) >> 2
    #     os.chmod(relative_extension, mode)


if __name__ == "__main__":
    build()
