from setuptools import setup, find_packages

setup(
    name="screen-translator",
    version="1.5.3",
    description="Auto-translate highlighted text on Ubuntu",
    author="sonnn",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "deep-translator>=1.11.4",
        "gTTS>=2.3.2",
        "langdetect>=1.0.9",
    ],
    entry_points={
        "console_scripts": [
            "screen-translator=screen_translator.main:main",
        ],
    },
)
