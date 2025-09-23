# FileDrop - File Sharing Application

## Overview
FileDrop is a Flask-based web application that allows users to create temporary rooms for file sharing. Users can generate QR codes for easy room access and share files within these rooms.

## Recent Changes (September 23, 2025)
- Successfully imported and configured for Replit environment
- Updated Flask app to run on port 5000 instead of 8080
- Configured deployment settings for autoscale hosting
- All dependencies installed and working correctly

## Project Architecture
- **Backend**: Flask (Python)
- **Database**: SQLite for room management
- **Frontend**: HTML templates with embedded CSS
- **File Storage**: Local filesystem in 'uploads' directory
- **Dependencies**: Flask, qrcode, Pillow, pyrebase4, requests

## Key Features
- Room creation with random 5-character codes
- Presenter authentication system
- File upload/download functionality
- QR code generation for easy room access
- Clean, responsive web interface

## Current State
- Application is fully functional and running
- Workflow configured for port 5000
- Database initialized successfully
- Ready for deployment and use