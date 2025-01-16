import os
import sys
import json
import difflib
import argparse
import requests
import time
import pty
import select
import signal
from threading import Thread
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Globals
command_log = []         # Stores captured commands
file_changes = {}        # Tracks file modifications
executed_scripts = {}    # Captures .sh script content
observer = None
config_file = os.path.expanduser("~/.orcai_config.json")
state_file = os.path.expanduser("~/.orcai_state.json")
capturing = False        # Indicates whether we are capturing
shell_pid = None         # PID of the child shell process used in PTY

##############################################################################
# Configuration and State
##############################################################################

def load_config():
    """Loads configuration from file."""
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            return json.load(f)
    return {}

def save_config(config):
    """Saves configuration to file."""
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)
    print(f"Configuration saved to {config_file}")

def configure_orcai():
    """Prompts the user to configure Orcai."""
    print("Configuring Orcai...")
    api_endpoint = input("Enter the API endpoint (e.g., https://api.openai.com/v1/chat/completions): ").strip()
    api_key = input("Enter your API key: ").strip()
    model = input("Enter the model to use (e.g., gpt-4): ").strip()
    context_length = int(input("Enter the maximum context length (e.g., 2048): ").strip())

    config = {
        "api_endpoint": api_endpoint,
        "api_key": api_key,
        "model": model,
        "context_length": context_length,
    }
    save_config(config)

##############################################################################
# File Monitoring
##############################################################################

class FileEditHandler(FileSystemEventHandler):
    """Handles file edits and captures changes."""
    def on_modified(self, event):
        # Skip directories and temporary files
        if event.is_directory or event.src_path.endswith(".new"):
            return

        if capturing:
            path = event.src_path
            try:
                with open(path, "r") as f:
                    new_content = f.readlines()

                # Compare with previously saved content
                if path in file_changes:
                    old_content = file_changes[path]["content"]
                    diff = difflib.unified_diff(
                        old_content,
                        new_content,
                        fromfile="before",
                        tofile="after"
                    )
                    file_changes[path]["diff"] = "\n".join(diff)
                else:
                    file_changes[path] = {"content": new_content, "diff": None}
            except Exception as e:
                print(f"Error processing file {path}: {e}")

def start_file_monitoring(directory):
    """Starts monitoring file changes."""
    global observer
    if observer is None:
        observer = Observer()
        handler = FileEditHandler()
        observer.schedule(handler, directory, recursive=True)
        observer.start()

def stop_file_monitoring():
    """Stops monitoring file changes."""
    global observer
    if observer:
        observer.stop()
        observer.join()
        observer = None

##############################################################################
# Real-Time Shell Capture (PTY)
##############################################################################

def capture_script(script_path):
    """Reads and captures the content of a script file."""
    if os.path.exists(script_path):
        try:
            with open(script_path, "r") as script_file:
                content = script_file.readlines()
                executed_scripts[script_path] = content
                print(f"Captured script: {script_path}")
        except Exception as e:
            print(f"Error reading script {script_path}: {e}")

def capture_command(command):
    """Captures executed commands and filters out non-user commands."""
    cmd = command.strip()
    if not cmd or "orcai" in cmd:  # Ignore empty commands or Orcai-related commands
        return

    command_log.append(cmd)

    # Detect script execution
    if cmd.endswith(".sh") and os.path.exists(cmd):
        capture_script(cmd)

##############################################################################
# PTY Shell Session
##############################################################################

def shell_session(config, debug=False):
    """
    Spawns a pseudo-terminal with the user's default shell,
    intercepting commands in real-time and dynamically configuring history settings.
    """
    global capturing, shell_pid
    capturing = True
    start_file_monitoring(os.path.expanduser("~"))

    # Fork a new pseudo-terminal process
    pid, fd = pty.fork()
    shell_pid = pid

    if pid == 0:
        # Child process: Start user's default shell
        shell = os.environ.get("SHELL", "/bin/bash")
        
        # Apply dynamic history configuration
        if "zsh" in shell:
            os.environ["HISTFILE"] = os.path.expanduser("~/.zsh_history")
            os.environ["HISTSIZE"] = "10000"
            os.environ["SAVEHIST"] = "10000"
            os.environ["ZDOTDIR"] = os.path.expanduser("~")
        elif "bash" in shell:
            os.environ["HISTFILE"] = os.path.expanduser("~/.bash_history")
            os.environ["HISTSIZE"] = "10000"
            os.environ["HISTCONTROL"] = "ignoredups:erasedups"
            os.environ["PROMPT_COMMAND"] = "history -a; history -n"
        elif "fish" in shell:
            os.environ["fish_history"] = os.path.expanduser("~/.local/share/fish/fish_history")

        os.execlp(shell, shell)  # Replace child process with the shell
    else:
        # Parent process: Manage I/O with PTY
        print("Orcai shell started. Type 'exit' or Ctrl-D to finish and generate the playbook.")
        try:
            _pty_loop(fd, config, debug=debug)
        except OSError:
            pass
        finally:
            capturing = False
            stop_file_monitoring()
            generate_ansible_playbook(config, debug=debug)

def _pty_loop(fd, config, debug=False):
    """Main loop for managing I/O with the PTY."""
    try:
        while True:
            r, w, e = select.select([fd, sys.stdin], [], [])
            if fd in r:
                output = os.read(fd, 1024)
                if not output:
                    break
                sys.stdout.buffer.write(output)
                sys.stdout.flush()

            if sys.stdin in r:
                user_input = os.read(sys.stdin.fileno(), 1024)
                if not user_input:
                    os.kill(shell_pid, signal.SIGTERM)
                    break
                lines = user_input.decode(errors="ignore").split("\n")
                for line in lines:
                    capture_command(line)
                os.write(fd, user_input)
    except KeyboardInterrupt:
        print("\nExiting shell on KeyboardInterrupt...")
        os.kill(shell_pid, signal.SIGTERM)

##############################################################################
# Generate Ansible Playbook
##############################################################################

def generate_ansible_playbook(config, debug=False):
    """Generates an Ansible playbook from captured data."""
    llm_endpoint = config.get("api_endpoint", "")
    api_key = config.get("api_key", "")
    model = config.get("model", "gpt-4")

    # Prepare data for the LLM
    prompt = f"""
    Convert the following shell commands, file changes, and executed scripts into an Ansible playbook:
    Only output the YAML content for the playbook without any additional text, explanations, or formatting.

    Commands:
    {json.dumps(command_log, indent=2)}

    File Changes:
    {json.dumps({path: data["diff"] for path, data in file_changes.items()}, indent=2)}

    Executed Scripts:
    {json.dumps(executed_scripts, indent=2)}
    """

    if debug:
        print("\n=== LLM Prompt ===")
        print(prompt)

    messages = [
        {"role": "system", "content": "You are a tool for generating Ansible playbooks."},
        {"role": "user", "content": prompt},
    ]

    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": config.get("context_length", 2048),
    }

    try:
        response = requests.post(llm_endpoint, json=payload, headers=headers)
        if response.status_code == 200:
            playbook = response.json()["choices"][0]["message"]["content"]
            if debug:
                print("\n=== LLM Response ===")
                print(playbook)

            save_path = input("\nEnter the file path to save the Ansible playbook: ").strip()
            with open(save_path, "w") as file:
                file.write(playbook.strip())
            print(f"Playbook saved to {save_path}.")
        else:
            print(f"Error generating playbook: {response.json()}")
    except Exception as e:
        print(f"Error generating playbook: {e}")

##############################################################################
# CLI
##############################################################################

def cli():
    """Command-line interface for Orcai."""
    parser = argparse.ArgumentParser(prog="orcai", description="Orchestraitor CLI")
    parser.add_argument(
        "command", 
        choices=["shell", "config"], 
        help="Run an interactive shell with real-time capture, or configure the tool."
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug mode for troubleshooting")

    parser.add_argument("--api-endpoint", help="Override API endpoint")
    parser.add_argument("--api-key", help="Override API key")
    parser.add_argument("--model", help="Override LLM model")
    parser.add_argument("--context-length", type=int, help="Override context length")

    args = parser.parse_args()

    config = load_config()

    # Apply overrides
    if args.api_endpoint:
        config["api_endpoint"] = args.api_endpoint
    if args.api_key:
        config["api_key"] = args.api_key
    if args.model:
        config["model"] = args.model
    if args.context_length:
        config["context_length"] = args.context_length

    if args.command == "config":
        configure_orcai()
    elif args.command == "shell":
        command_log.clear()
        file_changes.clear()
        executed_scripts.clear()
        shell_session(config, debug=args.debug)


if __name__ == "__main__":
    cli()