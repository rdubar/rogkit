import argparse
import requests
from ..bin.tomlr import load_rogkit_toml

TOML = load_rogkit_toml()
# TOML.get('location', {}).get('ipinfo_api_key', '')
DEFAULT_API_KEY = TOML.get('openai', {}).get('openai_api_key', '')

def query_chatgpt(prompt, api_key=DEFAULT_API_KEY):
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    data = {
        "prompt": prompt,
        "max_tokens": 100  # You can adjust the number of tokens as needed
    }
    response = requests.post("https://api.openai.com/v1/engines/davinci-codex/completions", json=data, headers=headers)
    return response.json()

def main():
    parser = argparse.ArgumentParser(description="CLI for querying ChatGPT.")
    parser.add_argument("prompt", nargs='?', help="Prompt to send to ChatGPT")
    parser.add_argument("--api_key", required=False, default="Your-Default-API-Key", help="API key for OpenAI")
    parser.add_argument("-d", "--debug", action="store_true", help="Print debug info")
    args = parser.parse_args()

    # Join the prompt parts into a single string
    full_prompt = ' '.join(args.prompt) if args.prompt else "Hello, I'm a chatbot. Ask me anything!"

    response = query_chatgpt(full_prompt, api_key=args.api_key)
    try:
        print(response['choices'][0]['text'])
    except Exception as e:
        print(f"Error: {e}")
        print(response)

    if args.debug:
        print(DEFAULT_API_KEY)

if __name__ == "__main__":
    main()
