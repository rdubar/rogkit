"""
ChatGPT CLI client.

Interactive command-line interface for OpenAI's GPT models with
conversation history support. Configuration via rogkit config.toml.
"""
import argparse
from openai import OpenAI
from ..bin.tomlr import load_rogkit_toml

# Load the configuration from TOML file
TOML = load_rogkit_toml()
DEFAULT_API_KEY = TOML.get('openai', {}).get('openai_api_key', '')
DEFAULT_ENGINE = "gpt-4o"

# Instantiate OpenAI client using MCP
client = OpenAI(api_key=DEFAULT_API_KEY)

def query_chatgpt(prompt, engine=DEFAULT_ENGINE, history=None):
    """Query ChatGPT with a prompt and optional conversation history."""
    if history is None:
        history = []
    messages = history + [{"role": "user", "content": prompt}]
    
    response = client.chat.completions.create(
        model=engine,
        messages=messages
    )
    return response

def chat_loop(prompt=None, engine=DEFAULT_ENGINE, history=None):
    """Run interactive chat loop with ChatGPT."""
    if history is None:
        history = []
    full_prompt = prompt or input("Enter your prompt: ")
    history = []

    while True:
        response = query_chatgpt(full_prompt, engine=engine, history=history)
        try:
            output = response.choices[0].message.content
            print(output)

            history.append({"role": "user", "content": full_prompt})
            history.append({"role": "assistant", "content": output})

        except Exception as e:
            print(f"Error: {e}")

        full_prompt = input("> ")
        if full_prompt.lower() in ['exit', 'quit', 'q']:
            break

def main():
    """CLI entry point for ChatGPT client."""
    parser = argparse.ArgumentParser(description="CLI for querying ChatGPT.")
    parser.add_argument("prompt", nargs='*', help="Prompt to send to ChatGPT")
    parser.add_argument("-e", "--engine", required=False, default=DEFAULT_ENGINE, help="OpenAI engine to use")
    parser.add_argument("-d", "--debug", action="store_true", help="Print debug info")
    parser.add_argument("-i", "--info", action="store_true", help="Print information about the assistant")
    args = parser.parse_args()
    
    if args.info:
        print(f'Connected to OpenAI engine: {args.engine}')

    if args.prompt:
        full_prompt = ' '.join(args.prompt)
    else:
        full_prompt = input("Enter your prompt: ")

    history = []

    while True:
        response = query_chatgpt(full_prompt, engine=args.engine, history=history)
        try:
            output = response.choices[0].message.content
            print(output)

            history.append({"role": "user", "content": full_prompt})
            history.append({"role": "assistant", "content": output})

        except Exception as e:
            print(f"Error: {e}")

        full_prompt = input("> ")
        if full_prompt.lower() in ['exit', 'quit', 'q']:
            break

if __name__ == "__main__":
    main()