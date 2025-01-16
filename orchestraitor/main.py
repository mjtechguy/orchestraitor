import os
import sys
import json
import difflib
import argparse
import requests
import time
from threading import Thread
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Globals
command_log = []
file_changes = {}
executed_scripts = {}
observer = None
config_file = os.path.expanduser("~/.orcai_config.json")
state_file = os.path.expanduser("~/.orcai_state.json")
capturing = False
last_processed_command = 0  # Tracks the last command index in shell history
history_file = os.path.expanduser("~/.bash_history")  # Default shell history file


class FileEditHandler(FileSystemEventHandler):
    """Handles file edits and captures changes."""
    def on_modified(self, event):
        if event.is_file() and capturing:
            path = event.src_path
            try:
                with open(path, "r") as f:
                    new_content = f.readlines()

                # Compare with previously saved content
                if path in file_changes:
                    old_content = file_changes[path]["content"]
                    diff = difflib.unified_diff(
                        old_content, new_content, fromfile="before", tofile="after"
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


def load_state():
    """Loads the capture state from the state file."""
    if os.path.exists(state_file):
        with open(state_file, "r") as f:
            return json.load(f)
    return {"capturing": False}


def save_state(state):
    """Saves the capture state to the state file."""
    with open(state_file, "w") as f:
        json.dump(state, f)


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
    """Captures executed commands and handles scripts."""
    command_log.append(command)

    # Detect script execution
    if command.endswith(".sh") and os.path.exists(command):
        capture_script(command)


def monitor_shell_history():
    """Continuously monitors the shell history file for new commands."""
    global last_processed_command, capturing
    while capturing:
        try:
            with open(history_file, "r") as f:
                lines = f.readlines()
                new_commands = lines[last_processed_command:]
                for command in new_commands:
                    command = command.strip()
                    capture_command(command)
                last_processed_command = len(lines)
        except Exception as e:
            print(f"Error reading history file: {e}")
        time.sleep(1)  # Check for new commands every second


def start_capture(config):
    """Starts capturing commands and file changes."""
    state = load_state()
    if state["capturing"]:
        print("Capture is already running!")
        return

    print("Starting capture...")
    state["capturing"] = True
    save_state(state)

    global capturing, command_log, file_changes, executed_scripts, last_processed_command
    capturing = True
    command_log.clear()
    file_changes.clear()
    executed_scripts.clear()

    # Initialize history tracking
    with open(history_file, "r") as f:
        last_processed_command = len(f.readlines())

    # Start monitoring file changes
    start_file_monitoring(os.path.expanduser("~"))

    # Start monitoring shell history
    history_thread = Thread(target=monitor_shell_history, daemon=True)
    history_thread.start()


def stop_capture(config):
    """Stops capturing and generates an Ansible playbook."""
    state = load_state()
    if not state["capturing"]:
        print("No capture to stop!")
        return

    print("Stopping capture...")
    state["capturing"] = False
    save_state(state)

    global capturing
    capturing = False
    stop_file_monitoring()
    generate_ansible_playbook(config)


def generate_ansible_playbook(config):
    """Generates an Ansible playbook from captured data."""
    llm_endpoint = config["api_endpoint"]
    api_key = config["api_key"]
    model = config["model"]

    # Prepare script content as part of the playbook generation
    scripts = {
        path: "".join(content) for path, content in executed_scripts.items()
    }

    # Prepare data for the LLM
    prompt = f"""
    Convert the following shell commands, file changes, and executed scripts into an Ansible playbook:

    Commands:
    {json.dumps(command_log, indent=2)}

    File Changes:
    {json.dumps({path: data["diff"] for path, data in file_changes.items()}, indent=2)}

    Executed Scripts:
    {json.dumps(scripts, indent=2)}
    """

    # Chat-style API expects a `messages` array
    messages = [
        {"role": "system", "content": "You are a tool for generating Ansible playbooks."},
        {"role": "user", "content": prompt},
    ]

    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": config["context_length"],
    }

    try:
        response = requests.post(llm_endpoint, json=payload, headers=headers)
        if response.status_code == 200:
            playbook = response.json()["choices"][0]["message"]["content"]
            save_path = input("Enter the file path to save the Ansible playbook: ").strip()
            with open(save_path, "w") as file:
                file.write(playbook)
            print(f"Playbook saved to {save_path}.")
        else:
            print(f"Error generating playbook: {response.json()}")
    except Exception as e:
        print(f"Error generating playbook: {e}")


def cli():
    """Command-line interface for Orcai."""
    parser = argparse.ArgumentParser(prog="orcai", description="Orchestraitor CLI")
    parser.add_argument(
        "command", choices=["start", "stop", "config"], help="Control the Orchestraitor"
    )
    parser.add_argument("--api-endpoint", help="Override API endpoint")
    parser.add_argument("--api-key", help="Override API key")
    parser.add_argument("--model", help="Override LLM model")
    parser.add_argument("--context-length", type=int, help="Override context length")

    args = parser.parse_args()

    # Load configuration and apply command-line overrides
    config = load_config()
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
    elif args.command == "start":
        start_capture(config)
    elif args.command == "stop":
        stop_capture(config)


if __name__ == "__main__":
    cli()