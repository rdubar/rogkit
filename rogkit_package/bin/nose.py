"""
Odoo/OpenERP nosetests wrapper.

Simplifies running nosetests for specific addons in OpenERP projects
by automatically finding addon paths and constructing test commands.
"""
import argparse
import subprocess
import os

# Default values for ease of updating
ROOT = '/home/rdubar/projects/pythonProject/openerp-addons'
NOSETEST_CMD = 'bin/nosetests_odoo -- -v --with-timer --logging-clear-handlers'
ADDONS_FOLDERS = ['addons', 'ext_addons']

def main():
    """CLI entry point for Odoo nosetests wrapper."""
    parser = argparse.ArgumentParser(description='Run nosetests for the specified folder in the openerp-addons directory.')
    parser.add_argument('folder', help='The folder or addon name to run tests on.')
    args = parser.parse_args()

    # Construct the full path based on the input and defaults
    folder_path = get_full_folder_path(args.folder)
    if folder_path:
        run_tests(folder_path)
    else:
        print(f'Error: The specified folder or addon "{args.folder}" does not exist.')
        parser.print_help()
        exit(1)

def get_full_folder_path(arg):
    """Determines the full path of the folder to run tests on."""
    if os.path.isdir(arg):
        return arg
    elif os.path.isdir(f'{ROOT}/src/addons/{arg}'):
        return f'{ROOT}/src/addons/{arg}'
    else:
        for check in ADDONS_FOLDERS:
            potential_path = f'{ROOT}/src/{check}/{arg}'
            if os.path.isdir(potential_path):
                return potential_path
    return None

def run_tests(folder):
    """Executes the nosetest command on the specified folder."""
    command = f'cd {ROOT} && {NOSETEST_CMD} {folder}'
    print(command)
    subprocess.run(command, shell=True)

if __name__ == '__main__':
    main()
