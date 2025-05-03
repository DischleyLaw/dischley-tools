#!/usr/bin/env bash

# Install poppler-utils (for pdf2image to convert PDFs to images)
apt-get update && apt-get install -y poppler-utils

# Ensure the Tesseract OCR engine is installed
apt-get install -y tesseract-ocr

# Install required Python packages
pip install -r requirements.txt