"""
script to convert all .pds files in directory to .rsm files
usage e.g. python3 etc/mass_convert_ctl.py ../../../PDSs D:/RSMs/
"""

import argparse
import os

parser = argparse.ArgumentParser(description="Convert many CTLs from PuMoC to PyModelChecking syntax")
parser.add_argument("path_to_pds_directory", help="path to directory with PDSs")
parser.add_argument("out", help="where to store RSMs")

args = parser.parse_args()
in_directory = args.path_to_pds_directory
out_directory = args.out

directory = os.fsencode(in_directory)

for file in os.listdir(directory):
    filename = os.fsdecode(file)
    if filename.endswith(".ctl"):
        with open(in_directory + "/" +  filename) as in_file:
            ctl = in_file.readline()
            ctl = ctl.replace("!", "~")
            ctl = ctl.replace("E", "E ")
            ctl = ctl.replace("G", "G ")
            ctl = ctl.replace("X", "X ")
            ctl = ctl.replace("U", " U ")
            ctl = ctl.replace("&&", "&")
            ctl = ctl.replace("||", "|")
            ctl = ctl.replace("[", "(")
            ctl = ctl.replace("]", ")")
            out = out_directory + filename
            with open(out, 'w') as f:
                f.write(ctl)
