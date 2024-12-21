import argparse
import subprocess
import platform
from openai import OpenAI
from ..bin.tomlr import load_rogkit_toml

# Load the configuration from TOML file
TOML = load_rogkit_toml()
DEFAULT_API_KEY = TOML.get('openai', {}).get('openai_api_key', '')
DEFAULT_ENGINE = "gpt-4o"

client = OpenAI(api_key=DEFAULT_API_KEY)

def detect_default_os():
    """Detect the default OS using Python's platform module."""
    current_os = platform.system()
    if current_os == "Darwin":
        return "macOS"
    elif current_os == "Linux":
        return "Linux"
    elif current_os == "Windows":
        return "Windows"
    else:
        return "Unknown OS"

def get_system_prompt(os_name, expertise_level):
    """Generate a system prompt tailored to the OS and user expertise."""
    return (
        f"You are a shell assistant for {os_name}. "
        f"The user is an {expertise_level} in {os_name}, so your responses should be concise and advanced. "
        "Provide only the command necessary to accomplish the task without explanations or beginner-level detail."
    )

def query_chatgpt(prompt, os_name, expertise_level, engine=DEFAULT_ENGINE, history=[]):
    """Queries the AI with a custom system prompt."""
    system_message = {
        "role": "system",
        "content": get_system_prompt(os_name, expertise_level),
    }
    messages = [system_message] + history + [{"role": "user", "content": prompt}]
    response = client.chat.completions.create(model=engine, messages=messages)
    return response

def execute_command(command):
    """Executes a shell command and returns the output."""
    try:
        print(f"Executing: {command}")
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Output: {result.stdout.strip()}")
        else:
            print(f"Error: {result.stderr.strip()}")
    except Exception as e:
        print(f"Command execution failed: {e}")

def chat_loop(os_name, expertise_level, engine=DEFAULT_ENGINE):
    history = []
    print(f"Welcome to the AI Shell for {os_name}. Type your task in natural language. Type 'exit' to quit.")
    
    while True:
        user_input = input("Enter task: ")
        if user_input.lower() in ['exit', 'quit', 'q']:
            break

        try:
            response = query_chatgpt(user_input, os_name, expertise_level, engine=engine, history=history)
            output = response.choices[0].message.content.strip()

            # Confirm and execute
            print(f"AI Suggestion: {output}")
            confirm = input("Run this command? (y/n): ").strip().lower()
            if confirm == 'y':
                execute_command(output)

            # Update history
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": output})

        except Exception as e:
            print(f"Error: {e}")

def main():
    parser = argparse.ArgumentParser(description="AI Shell for executing tasks.")
    parser.add_argument("-o", "--os", help="Specify the operating system (e.g., Linux, macOS, Windows).")
    parser.add_argument("-l", "--level", choices=['beginner', 'intermediate', 'expert'],
                        help="Specify the user's expertise level.")
    parser.add_argument("-e", "--engine", default=DEFAULT_ENGINE, help="OpenAI engine to use.")
    args = parser.parse_args()

    # Detect OS and set defaults
    os_name = args.os or detect_default_os()
    expertise_level = args.level or "expert"

    chat_loop(os_name=os_name, expertise_level=expertise_level, engine=args.engine)

if __name__ == "__main__":
    main()