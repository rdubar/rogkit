import os
import subprocess

def find_virtual_envs(directory):
    return [folder for folder in os.listdir(directory) if os.path.exists(os.path.join(directory, folder, 'bin', 'activate'))]

def activate_virtual_env(directory):
    activate_script = os.path.join(directory, 'bin', 'activate')
    if os.path.exists(activate_script):
        command = f"source {activate_script}"
        subprocess.run(command, shell=True, executable="/bin/bash")
        return activate_script
    return None

def main():
    current_directory = os.getcwd()
    env_folders = find_virtual_envs(current_directory)
    
    print("Rog's Virtual Environment Tool")
    v_list = '' if len(env_folders) == 0 else ': ' + ', '.join(env_folders)
    folders = 'folder' if len(env_folders) == 1 else 'folders'
    print(f'Found {len(env_folders)} virtual environment {folders} in {current_directory}{v_list}')
    
    if env_folders:
        first_env = env_folders[0]
        full_path = os.path.join(current_directory, first_env)
        print(f"Activating the first virtual environment found in {first_env} at {full_path}")
        activate_script = activate_virtual_env(full_path)
        if activate_script:
            print(f"Activated {activate_script}")
        else:
            print("No activation script found in the first virtual environment folder.")
    else:
        print("No virtual environment folders found.")

if __name__ == "__main__":
    main()
