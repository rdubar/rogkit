import sys, argparse
from interpreter import interpreter
from ..bin.tomlr import load_rogkit_toml

def setup():
    api_key = load_rogkit_toml().get("open-interpreter").get("api_key")
    if api_key:    
        interpreter.llm.api_key = api_key

    interpreter.llm.model = "gpt-4"
    interpreter.auto_run = True

def main():
    # setup argparse, so turns args into prompt by default with -erp option to connect to the erp
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", nargs='*', help="Prompt to send to Open Interpreter")
    parser.add_argument("-e", "--erp", action="store_true", help="Connect to the ERP")
    args = parser.parse_args()

    prompt = ' '.join(args.prompt) if args.prompt else ''
    
    setup()
    
    if args.erp:
        credentials = load_rogkit_toml().get("erp-live")
        prompt = f"Connect to OpenERP via /xmlrpc/common using these credentials:{credentials}"

    while True:
        interpreter.chat(prompt)
        prompt = input()
        if prompt.lower() in ["exit", "quit", 'q']:
            break

if __name__ == "__main__":
    main()

