# OrchestrAItor (orcai)

**OrchestrAItor** (`orcai`) is a CLI tool that monitors shell commands and file changes, capturing detailed modifications to files and converting them into Ansible playbooks using an OpenAI-compatible LLM endpoint. It provides seamless integration with systemd to run as a background service and allows flexible configuration through both interactive prompts and command-line flags.

---

## Features

- **Monitor Shell Commands**: Logs shell commands executed by the user.
- **Track File Edits**: Captures detailed changes (diffs) to files, allowing precise recreation of modifications.
- **Generate Ansible Playbooks**: Converts captured commands and file edits into Ansible playbooks via an LLM endpoint.
- **Flexible Configuration**: Set API endpoint, API key, model, and context length through interactive prompts or command-line flags.
- **Systemd Integration**: Runs as a managed background service.

---

## Installation

### Prerequisites

- Python 3.8 or higher
- `pip` for package installation
- Root access to set up the `systemd` service

### Steps

1. Clone the repository:

```bash
git clone https://github.com/mjtechguy/orchestraitor.git
cd orchestraitor
```

2.	Install the package:

```bash
pip install .
```

3.	Verify the installation:

```bash
orcai --help
```

## Commands

1. `orcai config`

Configures the tool interactively by prompting for necessary details:

```bash
orcai config
```

### Config Prompts:

- API Endpoint: The OpenAI-compatible API endpoint (e.g., https://api.openai.com/v1/completions).
- API Key: Your API key for authentication.
- Model: The model to use (e.g., gpt-4).
- Context Length: The maximum number of tokens in the response (e.g., 2048).

Configuration is saved to ~/.orcai_config.json.

2. `orcai start`

Starts monitoring shell commands and file changes. By default, the service uses the saved configuration.

#### Example:

```bash
orcai start
```

You can override configuration values with flags:

```bash
orcai start --api-endpoint https://api.openai.com/v1/completions --api-key my-key --model gpt-4 --context-length 8096
```

3. `orcai stop`

Stops monitoring and generates an Ansible playbook. The program sends the captured data to the LLM endpoint and prompts you to save the playbook.

#### Example:

```bash
orcai stop
```

After stopping, the program will prompt:

`Enter the file path to save the Ansible playbook:`

4. Command-Line Flags

Use flags to override saved configuration settings:

- 	`--api-endpoint`: Override the API endpoint.
- 	`--api-key`: Override the API key.
- 	`--model`: Override the model.
- 	`--context-length`: Override the maximum context length.

#### Example:

```bash
orcai start --api-endpoint https://api.example.com --model gpt-3.5
```

## Configuration File

The configuration is stored in a JSON file at ~/.orcai_config.json. Example:


```json
{
    "api_endpoint": "https://api.openai.com/v1/completions",
    "api_key": "your-api-key",
    "model": "gpt-4",
    "context_length": 2048
}
```

To update the configuration, run:

```bash
orcai config
```

#### Example Workflow

1.	Configure the Tool:

```bash
orcai config
```

2.	Start Capturing:

```bash
orcai start
```

Perform shell commands and make file edits. The tool will log your actions and track file changes.

3.	Stop Capturing:

```bash
orcai stop
```

The captured data is converted into an Ansible playbook, and you will be prompted to save it.

## Service Management

The orcai daemon can also be managed using systemd. By default, the installer sets it up as a systemd service.

Check Service Status:

```bash
systemctl status orcai
```

Restart the Service:

```bash
systemctl restart orcai
```

Stop the Service:

```bash
systemctl stop orcai
```

## Uninstallation

To uninstall Orchestraitor:

1.	Stop the systemd service:

```bash
systemctl stop orcai
```


2.	Disable the service:

```bash
systemctl disable orcai
```

3.	Remove the service file:

```bash
sudo rm /etc/systemd/system/orcai.service
```

4.	Uninstall the Python package:

```bash
pip uninstall orchestraitor
```

## Troubleshooting

The daemon isn’t running:

- Check the service status:

```bash
systemctl status orcai
```

- Restart the service:

```bash
systemctl restart orcai
```

- No configuration found:

  - Run `orcai config` to set up the configuration.

## Future Improvements

- Add support for monitoring additional system activities (e.g., network traffic, permission changes).
- Improve diff handling for binary files.
- Provide more detailed Ansible playbook generation for complex workflows.

## License

This project is licensed under the MIT License. See the LICENSE file for details.