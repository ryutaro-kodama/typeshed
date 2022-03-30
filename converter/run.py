import argparse
from logging import basicConfig, getLogger, DEBUG, INFO
import glob
import os
import pathlib
import unittest

from converter import Converter


basicConfig(level=DEBUG)
logger = getLogger(__name__)

def set_arg_parser():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(title="subcommands", description="valid subcommands", help="select the mode what you want to from below")

    parser_convert = subparsers.add_parser("convert", help="convert input files")
    parser_convert.add_argument("filepath", help="the file to be converted")
    parser_convert.add_argument("-o", "--output_directory", default=".", help="the directory to be put output file")
    parser_convert.set_defaults(func=convert_main)

    # parser_test = subparsers.add_parser("test", help="run test files")
    # parser_test.set_defaults(func=test_main)

    args = parser.parse_args()
    return args

def convert_main(args):
    arg_filepath = args.filepath
    arg_output = args.output_directory

    if os.path.isfile(arg_filepath):
        filepaths = [arg_filepath]
    else:
        filepaths = glob.glob(os.path.join(arg_filepath, "**/*.py"), recursive=True)
        
    for filepath in filepaths:
        filename_pyi = os.path.split(filepath)[-1]
        package_name = pathlib.PurePath(filename_pyi).stem
        filename_xml = package_name + ".xml"
        write_filepath = os.path.join(
            os.path.abspath(arg_output), filename_xml
        )

        output_dir = os.path.split(write_filepath)[0]
        if os.path.exists(output_dir):
            if not os.path.isdir(output_dir):
                raise RuntimeError("specified OUTPUT_DIRECTORY is not directory")
            else:
                pass
        else:
            os.makedirs(output_dir)

        logger.info(f"Start converting: {filepath}")
        converter = Converter(filepath, package_name)
        converter.convert()
        converter.write(write_filepath)
        logger.info(f"File is written to: {write_filepath}")

# def test_main(args):
#     argv = ["python.exe -m unittest", "discover", "-s", "test", "-p", "test_*.py", "-t", "."]
#     unittest.main(module=None, argv=argv)


if __name__ == "__main__":
    args = set_arg_parser()
    args.func(args)
