"""
Open Interpreter integration for rogkit.

Provides CLI wrapper for Open Interpreter with optional OpenERP/Odoo
connection setup using stored credentials from rogkit config.
"""
import argparse
import sys

from ..bin.tomlr import load_rogkit_toml

oi_interpreter = None
INTERPRETER_IMPORT_ERROR = None

try:  # pragma: no cover - import guard for optional dependency
    from interpreter import interpreter as oi_interpreter  # type: ignore
except Exception as exc:  # pragma: no cover - handled at runtime for friendliness
    INTERPRETER_IMPORT_ERROR = exc

connection_script = """
import xmlrpc.client                                                                                                                                                                                                         
                                                                                                                                                                                                                            
def connect_to_openerp(url, db, username, password):                                                                                                                                                                          
    common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/common')                                                                                                                                                                
    uid = common.authenticate(db, username, password, {})                                                                                                                                                                    
                                                                                                                                                                                                                            
    if uid:                                                                                                                                                                                                                  
        print(f'Successfully authenticated. User ID: {uid}')                                                                                                                                                                 
    else:                                                                                                                                                                                                                    
        raise Exception('Authentication failed')                                                                                                                                                                              
                                                                                                                                                                                                                            
    # Object proxy                                                                                                                                                                                                            
    models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/object')                                                                                                                                                                
                                                                                                                                                                                                                            
    return common, models, uid                                                                                                                                                                                                
                                                                                                                                                                                                                            
# Replace with your details                                                                                                                                                                                                  
url = '<your_url>'                                                                                                                                                                                                            
db = '<your_database>'                                                                                                                                                                                                        
username = '<your_username>'                                                                                                                                                                                                 
password = '<your_password>'                                                                                                                                                                                                 
                                                                                                                                                                                                                            
common, models, uid = connect_to_openerp(url, db, username, password)   
"""


def check_environment() -> None:
    """Ensure the local environment can run Open Interpreter."""

    if oi_interpreter is None:
        message = "Open Interpreter is not installed."
        if sys.version_info >= (3, 13):
            message += (
                " Python 3.13+ is currently incompatible with Open Interpreter's"
                " `tiktoken` dependency. Use Python 3.12 or earlier, or reinstall"
                " with PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1."
            )
        if INTERPRETER_IMPORT_ERROR:
            message += f" Original import error: {INTERPRETER_IMPORT_ERROR}."
        raise RuntimeError(message)

    if sys.version_info >= (3, 13):
        raise RuntimeError(
            "Open Interpreter has not yet published wheels for Python 3.13+."
            " Switch to Python 3.12 or earlier, or reinstall with"
            " PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1."
        )


def setup(config):
    """Configure Open Interpreter with API key from rogkit config."""

    oi_config = config.get("open-interpreter") or {}

    api_key = oi_config.get("api_key")
    if api_key:
        oi_interpreter.llm.api_key = api_key
    elif "open-interpreter" in config:
        print("Warning: `open-interpreter.api_key` not set in rogkit config; proceeding without it.")

    model = oi_config.get("model", "gpt-4")
    oi_interpreter.llm.model = model
    oi_interpreter.auto_run = oi_config.get("auto_run", True)

    return oi_interpreter


def main():
    """CLI entry point for Open Interpreter integration."""
    # setup argparse, so turns args into prompt by default with -erp option to connect to the erp
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", nargs='*', help="Prompt to send to Open Interpreter")
    parser.add_argument("-e", "--erp", action="store_true", help="Connect to the ERP")
    args = parser.parse_args()

    print('Welcome to the Open Interpreter!')

    prompt = ' '.join(args.prompt) if args.prompt else ''
    try:
        check_environment()
    except RuntimeError as err:
        print(f"Open Interpreter is currently unavailable: {err}")
        raise SystemExit(1)

    config = load_rogkit_toml()
    interpreter_instance = setup(config)

    if args.erp:
        credentials = config.get("erp-live")
        if not credentials:
            print("ERP credentials not found in rogkit config (`erp-live`).")
            raise SystemExit(1)
        prompt = f"Connect to OpenERP using {connection_script} and these credentials:{credentials}"

    while True:
        interpreter_instance.chat(prompt)
        prompt = input()
        if prompt.lower() in ["exit", "quit", 'q']:
            exit(0)


if __name__ == "__main__":
    main()


