#!/usr/bin/env bash

# Update and install dependencies
sudo apt-get update && sudo apt-get install -y wget unzip apt-transport-https

# Download and install Google Chrome
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt-get install -y ./google-chrome-stable_current_amd64.deb

# Get the latest version of chromedriver
CHROME_DRIVER_VERSION=$(curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE)

# Download and unzip chromedriver
wget -N https://chromedriver.storage.googleapis.com/$CHROME_DRIVER_VERSION/chromedriver_linux64.zip
unzip chromedriver_linux64.zip -d /app/.chromedriver/
rm chromedriver_linux64.zip

# Add chromedriver to the PATH
export PATH=$PATH:/app/.chromedriver/