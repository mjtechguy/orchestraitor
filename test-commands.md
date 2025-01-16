# Recommended Test Commands

## Basic Shell Commands

**Create a directory**

`mkdir test_directory`

**Create a file**

`touch test_directory/example.txt`

**Write to a file**

`echo "This is a test file." > test_directory/example.txt`

**Append to a file**

`echo "Adding another line." >> test_directory/example.txt`

**Change file permissions**

`chmod 644 test_directory/example.txt`

## File Editing

To test capturing file changes (diffs):

`nano test_directory/example.txt`

Edit the file manually by adding, removing, or modifying lines.

Alternatively, use a quick in-terminal edit:

```bash
echo "New content" >> test_directory/example.txt
sed -i 's/test/new-test/' test_directory/example.txt
```

Installing Packages

```bash
sudo apt update
sudo apt install -y tree
```

## System Configuration

Create a symbolic link

`ln -s /etc/hosts test_directory/hosts_link`

## Running Scripts

**Create a sample script**

```bash
echo -e "#!/bin/bash\nmkdir script_directory\necho 'Script executed' > script_directory/output.txt" > test_script.sh
chmod +x test_script.sh
```

**Run the script**

`./test_script.sh`

Complex Workflow

# Create a file and write to it
echo "Test workflow" > workflow.txt

# Create a backup
cp workflow.txt workflow_backup.txt

# Replace text in the file
sed -i 's/Test/Updated/' workflow.txt