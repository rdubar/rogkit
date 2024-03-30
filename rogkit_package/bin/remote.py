import argparse
import os
import subprocess
import paramiko

# SSH connection parameters
HOSTNAME = '192.168.0.240'
USERNAME = 'pi'
PASSWORD = 'your_password_here'  # It's better to use SSH keys if possible
FOLDER = '/mnt/expansion/Media/Movies'

def ssh_command_execute(hostname, username, password, cmd):
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname=hostname, username=username, password=password)
        stdin, stdout, stderr = client.exec_command(cmd)
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        if error:
            print(f"Error: {error}")
        return output
    finally:
        client.close()
        
def execute_command(command: str, folder: str, hostname: str = HOSTNAME, username: str = USERNAME, password: str = PASSWORD) -> str:
    if os.path.exists(folder):
        # Execute the command locally using subprocess
        print(f"Executing command: '{command}'")
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output, error = process.communicate()
        if error:
            print(f"Error: {error}")
    elif HOSTNAME and USERNAME:
        # Execute the command over SSH if the folder does not exist locally
        print(f"Executing '{command}' at {hostname}:{folder}")
        output = ssh_command_execute(hostname, username, password, command)
    else:
        print(f"Folder not found: {folder}")
        return None
    return output

def parse_args():
    parser = argparse.ArgumentParser(description="List large files and folders with multiple large files over SSH.")
    parser.add_argument('command', type=str, help='Command to execute')
    parser.add_argument('-a', '--all', action='store_true', help='Show all relevant paths') 
    parser.add_argument('-f', '--folder', type=str, required=False, default=FOLDER, help='Folder to check')
    parser.add_argument('--hostname', type=str, required=False, default=HOSTNAME, help='SSH server hostname')
    parser.add_argument('--username', type=str, required=False, default=USERNAME, help='SSH username')
    parser.add_argument('--password', type=str, required=False, default=PASSWORD, help='SSH password')
    return parser.parse_args()

def main():
    args = parse_args()
    try:
        output = execute_command(args.command, args.folder, args.hostname, args.username, args.password)
        print(output)
    except Exception as e:
        print(f"Error: {e}")
    
if __name__ == '__main__':
    main()