# PythonAnywhere WSGI Configuration
#
# INSTRUCTIONS:
# 1. Copy this file's contents to your WSGI config file on PythonAnywhere
# 2. Replace YOUR_USERNAME with your actual PythonAnywhere username
#

import sys

# Add your project directory to the path
path = '/home/YOUR_USERNAME/event-annotation-tool'
if path not in sys.path:
    sys.path.append(path)

# Set the working directory for data files
import os
os.chdir(path)

# Import the Flask app
from app import app as application
