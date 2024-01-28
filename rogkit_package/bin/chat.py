import argparse
import requests
from ..bin.tomlr import load_rogkit_toml

TOML = load_rogkit_toml()
DEFAULT_API_KEY = TOML.get('openai', {}).get('openai_api_key', '')
DEFAULT_ENGINE = "gpt-3.5-turbo-0613"

def query_chatgpt(prompt, api_key=DEFAULT_API_KEY, engine=DEFAULT_ENGINE):
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    data = {
        "model": engine,  # Include the model parameter
        "messages": [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}]
    }
    response = requests.post(f"https://api.openai.com/v1/chat/completions", json=data, headers=headers)
    return response.json()

def main():
    parser = argparse.ArgumentParser(description="CLI for querying ChatGPT.")
    parser.add_argument("prompt", nargs='+', help="Prompt to send to ChatGPT")
    parser.add_argument("--api_key", required=False, default=DEFAULT_API_KEY, help="API key for OpenAI")
    parser.add_argument("-e", "--engine", required=False, default=DEFAULT_ENGINE, help="OpenAI engine to use")
    parser.add_argument("-d", "--debug", action="store_true", help="Print debug info")
    args = parser.parse_args()

    full_prompt = ' '.join(args.prompt)

    response = query_chatgpt(full_prompt, api_key=args.api_key, engine=args.engine)
    try:
        print(response['choices'][0]['message']['content'])
    except Exception as e:
        print(f"Error: {e}")
        print(response)

    if args.debug:
        print(DEFAULT_API_KEY)

if __name__ == "__main__":
    main()

# TODO: creats an input loop for chatgpt & remember the conversation for the next prompt
