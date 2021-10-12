"""
script to convert all .pds files in directory to .rsm files
has to be used from src folder, e.g.
python3 etc/mass_convert_pds.py ../../../PDSs D:/RSMs/
"""

import argparse
import os

parser = argparse.ArgumentParser(description="Convert many PDS to RSM")
parser.add_argument("path_to_pds_directory", help="path to directory with PDSs")
parser.add_argument("out", help="where to store RSMs")

args = parser.parse_args()
in_directory = args.path_to_pds_directory
out_directory = args.out

directory = os.fsencode(in_directory)

for file in os.listdir(directory):
    filename = os.fsdecode(file)
    if filename.endswith(".pds"):
        out = out_directory + filename[:-3] + "rsm"
        nr = int(filename[:-4])
        if nr > 178:
            print(nr)
            os.system('python3 etc/pds_to_rsm.py ' + in_directory + "/" + filename + ' --out ' + out)
