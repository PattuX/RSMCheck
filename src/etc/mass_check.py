"""
script to check all RSMs in a folder against their CTLs
RSM and CTL must have corresponding names, e.g. 42.rsm is checked against 42.ctl
usage:
python3 etc/mass_check.py D:/RSMs
"""

import argparse
import os

parser = argparse.ArgumentParser(description="Check many RSMs against CTLs")
parser.add_argument("path_to_pds_directory", help="path to directory with RSMs and CTLs")

args = parser.parse_args()
in_directory = args.path_to_pds_directory

directory = os.fsencode(in_directory)

for file in os.listdir(directory):
    rsm_filename = os.fsdecode(file)
    if rsm_filename.endswith(".rsm"):
        # base_name = rsm_filename[:-4]
        # ctl_filename = base_name + ".ctl"
        ctl_filename = "all.ctl"
        print(rsm_filename)
        os.system('python3 rsmcheck.py ' +
                  in_directory + "/" + rsm_filename + " " +
                  in_directory + "/" + ctl_filename)
