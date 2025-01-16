from setuptools import setup, find_packages

setup(
    name="orchestraitor",
    version="1.0.0",
    description="A CLI tool for capturing shell commands and file changes, and converting them to Ansible playbooks.",
    author="MJ",
    author_email="mj@mjtechguy.com",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "orcai=orchestraitor.main:cli",
        ],
    },
    install_requires=[
        "watchdog==2.3.0",
        "requests==2.31.0",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
)