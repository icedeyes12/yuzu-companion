#!/usr/bin/env python3
"""
Setup all MCP servers for Yuzu Companion
Run this after install_mcp_servers.sh
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database

ALL_SERVERS = [
    {
        "name": "filesystem",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/sdcard/Documents"],
        "description": "Access files on device storage",
    },
    {
        "name": "fetch",
        "transport": "stdio",
        "command": "python",
        "args": ["-m", "mcp_server_fetch"],
        "description": "Fetch URLs and web content",
    },
    {
        "name": "sqlite",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sqlite", "--db-path", "/data/data/com.termux/files/home/yuzu-companion/yuzu_core.db"],
        "description": "Query SQLite databases",
    },
    {
        "name": "memory",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-memory"],
        "description": "Persistent key-value storage",
    },
    {
        "name": "git",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-git"],
        "description": "Git repository operations",
    },
    {
        "name": "time",
        "transport": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-time"],
        "description": "Time and date utilities",
    },
    {
