import sys
import platform
import subprocess

print("Roger's Python System Report")

# Python version information in a human-friendly format
python_version = "Python version: {}.{}.{}".format(sys.version_info[0], sys.version_info[1], sys.version_info[2])
print(python_version)

# Path to the Python interpreter executable
print("Python Executable:", sys.executable)

# Operating system platform, e.g., 'darwin' for macOS, 'win32' for Windows, 'linux' for Linux
print("Operating System Platform:", sys.platform)

# Architecture information from the platform module
platform_architecture = platform.architecture()
print("Platform Architecture:", platform_architecture[0], "-", platform_architecture[1])

# Execute the 'arch' command to find out the architecture
process = subprocess.Popen(['arch'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
stdout, stderr = process.communicate()

# Decode stdout to get a string representation
# Python 3 returns bytes from subprocess, decode for compatibility
# In Python 2, stdout is already a string so decode only if necessary
if isinstance(stdout, bytes):
    architecture = stdout.strip().decode('utf-8')
else:
    architecture = stdout.strip()

print("System Architecture via 'arch':", architecture)

# Additional human-friendly formatting for architecture reporting
if architecture == 'i386':
    friendly_arch = "Intel 32-bit (possibly under Rosetta 2)"
elif architecture == 'x86_64':
    friendly_arch = "Intel 64-bit"
elif architecture == 'arm64':
    friendly_arch = "Apple Silicon (ARM 64-bit)"
else:
    friendly_arch = "Unknown Architecture"

print("Human-Friendly Architecture:", friendly_arch)
