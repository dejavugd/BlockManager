from app import BlockManager
from sys import platform

if platform.startswith('win'):
    BlockManager()
else:
    exit(0)