import argparse
import requests
from ..bin.tomlr import load_rogkit_toml

# Load the configuration from TOML file
TOML = load_rogkit_toml()
DEFAULT_API_KEY = TOML.get('openai', {}).get('openai_api_key', '')
DEFAULT_ENGINE = "gpt-3.5-turbo-0613"

def query_chatgpt(prompt, api_key=DEFAULT_API_KEY, engine=DEFAULT_ENGINE, history=[]):
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    # Prepare the list of messages, starting with the system message
    messages = [{"role": "system", "content": "You are a helpful assistant."}]
    # Add history messages if any
    messages.extend(history)
    # Add the current prompt
    messages.append({"role": "user", "content": prompt})
    
    data = {
        "model": engine,
        "messages": messages
    }
    response = requests.post("https://api.openai.com/v1/chat/completions", json=data, headers=headers)
    return response.json()

def main():
    parser = argparse.ArgumentParser(description="CLI for querying ChatGPT.")
    parser.add_argument("prompt", nargs='+', help="Prompt to send to ChatGPT")
    parser.add_argument("--api_key", required=False, default=DEFAULT_API_KEY, help="API key for OpenAI")
    parser.add_argument("-e", "--engine", required=False, default=DEFAULT_ENGINE, help="OpenAI engine to use")
    parser.add_argument("-d", "--debug", action="store_true", help="Print debug info")
    args = parser.parse_args()

    full_prompt = ' '.join(args.prompt)
    history = []  # Initialize the history list

    if args.debug:
        print(DEFAULT_API_KEY)

    while True:
        response = query_chatgpt(full_prompt, api_key=args.api_key, engine=args.engine, history=history)
        try:
            output = response['choices'][0]['message']['content']
            print(output)
            # Update the history after receiving a response
            history.append({"role": "user", "content": full_prompt})
            history.append({"role": "assistant", "content": output})
        except Exception as e:
            print(f"Error: {e}")
        
        full_prompt = input("> ")
        if full_prompt.lower() in ['exit', 'quit', 'q']:
            break


if __name__ == "__main__":
    main()

# TODO: better chat history handling