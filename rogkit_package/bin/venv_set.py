import os
import subprocess

def find_virtual_envs(directory):
    return [folder for folder in os.listdir(directory) if os.path.exists(os.path.join(directory, folder, 'bin', 'activate'))]

def activate_virtual_env(directory):
    for root, dirs, files in os.walk(directory):
        if 'bin' in dirs and 'activate' in os.listdir(os.path.join(root, 'bin')):
            activate_script = os.path.join(root, 'bin', 'activate')
            command = f"source {activate_script}"
            subprocess.run(command, shell=True, executable="/bin/bash")
            return activate_script
    return None

def main():
    current_directory = os.getcwd()
    env_folders = find_virtual_envs(current_directory)
    
    print("Rog's Virtual Environment Tool")
    v_list = '' if len(env_folders)==0 else ': ' + str(env_folders)
    folders = 'folder' if len(env_folders)==1 else 'folders'
    print(f'Found {len(env_folders)} virtual environment {folders} in {current_directory}{v_list}')
    
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
