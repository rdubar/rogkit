import argparse
from openai import OpenAI
from ..bin.tomlr import load_rogkit_toml

# Load the configuration from TOML file
TOML = load_rogkit_toml()
DEFAULT_API_KEY = TOML.get('openai', {}).get('openai_api_key', '')
# Set the API key globally
DEFAULT_ENGINE = "gpt-3.5-turbo"

client = OpenAI(api_key=DEFAULT_API_KEY)

def query_chatgpt(prompt, engine=DEFAULT_ENGINE, history=[]):
    # Prepare the prompt with history as context
    messages = history + [{"role": "user", "content": prompt}]

    # Send the prompt to ChatGPT using the correct method
    response = client.chat.completions.create(model=engine,
    messages=messages)

    return response

def chat_loop(prompt=None, engine=DEFAULT_ENGINE, history=[]):
    full_prompt = prompt or input("Enter your prompt: ")
    history = [] 

    while True:
        response = query_chatgpt(full_prompt, engine=engine, history=history)
        try:
            output = response.choices[0].message.content
            print(output)

            # Update the history with both user and assistant roles
            history.append({"role": "user", "content": full_prompt})
            history.append({"role": "assistant", "content": output})

        except Exception as e:
            print(f"Error: {e}")

        full_prompt = input("> ")
        if full_prompt.lower() in ['exit', 'quit', 'q']:
            break


def main():
    parser = argparse.ArgumentParser(description="CLI for querying ChatGPT.")
    parser.add_argument("prompt", nargs='?', help="Prompt to send to ChatGPT")
    parser.add_argument("-e", "--engine", required=False, default=DEFAULT_ENGINE, help="OpenAI engine to use")
    parser.add_argument("-d", "--debug", action="store_true", help="Print debug info")
    args = parser.parse_args()
    if args.prompt is None:
        args.prompt = input("Enter your prompt: ")

    full_prompt = ' '.join(args.prompt)
    history = []  # Initialize the history list

    while True:
        response = query_chatgpt(full_prompt, engine=args.engine, history=history)
        try:
            output = response.choices[0].message.content
            print(output)

            # Update the history with both user and assistant roles
            history.append({"role": "user", "content": full_prompt})
            history.append({"role": "assistant", "content": output})

        except Exception as e:
            print(f"Error: {e}")

        full_prompt = input("> ")
        if full_prompt.lower() in ['exit', 'quit', 'q']:
            break


if __name__ == "__main__":
    main()
