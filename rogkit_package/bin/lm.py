"""
Local LLM chat client for LM Studio.

Interactive chat interface for locally-hosted large language models via
LM Studio server. Supports streaming responses and conversation history.
"""
import argparse
from openai import OpenAI
import json

MODEL = 'lmstudio-community/Meta-Llama-3-70B-Instruct-GGUF/Meta-Llama-3-70B-Instruct-IQ1_M.gguf'


def connect_to_lm(show_history=False, model=MODEL):
    """Connect to local LM Studio server and start interactive chat loop."""
    # Point to the local server
    client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

    history = [
        {"role": "system", "content": "You are an intelligent assistant. You always provide well-reasoned answers that are both correct and helpful."},
        {"role": "user", "content": "Hello, introduce yourself to someone opening this program for the first time. Be concise."},
    ]

    while True:
        completion = client.chat.completions.create(
            messages=history,
            temperature=0.7,
            stream=True,
            model=model,
        ) 

        new_message = {"role": "assistant", "content": ""}
        
        for chunk in completion:
            if chunk.choices[0].delta.content:
                print(chunk.choices[0].delta.content, end="", flush=True)
                new_message["content"] += chunk.choices[0].delta.content

        history.append(new_message)
        
        if show_history:
            gray_color = "\033[90m"
            reset_color = "\033[0m"
            print(f"{gray_color}\n{'-'*20} History dump {'-'*20}\n")
            print(json.dumps(history, indent=2))
            print(f"\n{'-'*55}\n{reset_color}")

        print()
        history.append({"role": "user", "content": input("> ")})
        
def main():
    """CLI entry point for local LLM chat client."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--show-history", action="store_true")
    parser.add_argument("-m", "--model", default=MODEL)
    args = parser.parse_args()
    
    print('LM Local LLM Tool.')
    print(f'Using model: {args.model}')

    def run():
        connect_to_lm(show_history=args.show_history, model=args.model)
    
    if args.debug:
        run()
    else:
        try:
            run()
        except Exception as e:
            print(f'{e} Is the LM server running?')
            exit(0)

if __name__ == "__main__":
    main()

