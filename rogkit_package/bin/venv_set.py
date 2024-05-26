import os
import argparse
import subprocess

def find_virtual_envs(directory):
    env_folders = []
    for item in os.listdir(directory):
        if os.path.isdir(item) and (item.startswith('venv') or item.startswith('env')):
            env_folders.append(item)
    return env_folders

def activate_virtual_env(directory):
    for root, dirs, files in os.walk(directory):
        if 'bin' in dirs and 'activate' in os.listdir(os.path.join(root, 'bin')):
            activate_script = os.path.join(root, 'bin', 'activate')
            command = f"source {activate_script}"
            subprocess.run(command, shell=True, executable="/bin/bash")
            return activate_script
    return None

def main():
    parser = argparse.ArgumentParser(description="Search for virtual environment folders and optionally activate them.")
    parser.add_argument('-l', '--list', action='store_true', help='List all found virtual environment folders')
    parser.add_argument('-a', '--activate', action='store_true', help='Activate the first virtual environment found')

    args = parser.parse_args()
    current_directory = os.getcwd()
    env_folders = find_virtual_envs(current_directory)
    
    print("Rog's Virtual Environment Tool")
    print(f'Found {len(env_folders)} virtual environment folders in {current_directory}')

    if args.list:
        if env_folders:
            print("Found virtual environment folders:")
            for folder in env_folders:
                print(folder)
        else:
            print("No virtual environment folders found.")
    
    if args.activate:
        if env_folders:
            first_env = env_folders[0]
            print(f"Activating the first virtual environment found in {first_env}")
            activate_script = activate_virtual_env(first_env)
            if activate_script:
                print(f"Activated {activate_script}")
            else:
                print("No activation script found in the first virtual environment folder.")
        else:
            print("No virtual environment folders found.")

if __name__ == "__main__":
    main()
