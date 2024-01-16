import configparser
import os
import shutil
import argparse

rog_kit_ini = 'config.ini'

def create_default_config(config_file_path):
    config = configparser.ConfigParser(allow_no_value=True)
    config['BackupFrom'] = { 'primary' : '~/' }  # Add default directories if needed
    config['BackupTo'] = {'primary' : '~/archive/' }  # Add default directories if needed
    print(f'Creating default config file at {config_file_path}')
    with open(config_file_path, 'w') as configfile:
        config.write(configfile)

def reset_config(config_file_path, default_config_path):
    confirmation = input("Are you sure you want to reset the configuration? (yes/no): ")
    if confirmation.lower() == 'yes':
        if os.path.exists(config_file_path):
            os.remove(config_file_path)
        shutil.copy(default_config_path, config_file_path)
        print(f"The configuration has been reset to default. New config file copied to {config_file_path}.")
    else:
        print("Configuration reset canceled.")

def get_arguments():
    parser = argparse.ArgumentParser(description='Rog Kit Config Utility')
    parser.add_argument('-r', '--reset', action='store_true', help='Reset config to default')
    return parser.parse_args()

def get_user_config_path():
    user_home = os.path.expanduser('~')
    user_home_rogkit_dir = os.path.join(user_home, '.rogkit')
    user_home_rogkit_ini = os.path.join(user_home_rogkit_dir, rog_kit_ini)
    return user_home_rogkit_ini

def setup_config(script_dir_config_path, user_home_rogkit_ini):
    if not os.path.exists(script_dir_config_path):
        create_default_config(script_dir_config_path)

    user_home_rogkit_dir = os.path.dirname(user_home_rogkit_ini)
    if not os.path.exists(user_home_rogkit_ini):
        if not os.path.exists(user_home_rogkit_dir):
            os.mkdir(user_home_rogkit_dir)
        shutil.copy(script_dir_config_path, user_home_rogkit_ini)
        print(f'Copied {rog_kit_ini} to {user_home_rogkit_ini}')

def read_config(config_file_path):
    config = configparser.ConfigParser(allow_no_value=True)
    if not os.path.exists(config_file_path):
        print(f'Config file not found at {config_file_path}')
        return None

    try:
        config.read(config_file_path)
    except Exception as e:
        print(f'Error reading config file {config_file_path}: {e}')
        return None

    return config.items()


def main():
    args = get_arguments()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_dir_config_path = os.path.join(script_dir, rog_kit_ini)
    user_home_rogkit_ini = get_user_config_path()

    print('Rogkit Config Tool')

    if args.reset:
        reset_config(user_home_rogkit_ini, script_dir_config_path)
    else:
        setup_config(script_dir_config_path, user_home_rogkit_ini)

    config = read_config(user_home_rogkit_ini)

    print('Config:')
    for items in config:
        print(items)

if __name__ == '__main__':
    main()