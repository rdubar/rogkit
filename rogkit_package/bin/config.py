import configparser

config = configparser.ConfigParser(allow_no_value=True)
config.read(config_path)

backup_from_folders = [key for key in config.options('BackupFrom')]
backup_to_locations = [key for key in config.options('BackupTo')]
