---
name: termux-runtime-target
description: Enforce Termux-specific constraints for the yuzu-companion codebase. Ensure all code, paths, and commands generated are compatible with the target Android environment, regardless of where the agent is currently hosted.
---
# Termux Target Runtime Constraints

## Core Concept
- **Host vs Target**: You (the agent) may be running on a Modal container, Windows, laptop, or other environments, but the **target runtime** for `yuzu-companion` is strictly Android via Termux. All code edits, scripts, and suggested commands must be written for the target environment.

## Target Environment Rules
- **Target OS**: Code execution for the app happens exclusively on Android via Termux. Do not write code that depends on standard Linux desktop environments, Windows, or macOS native libraries.
- **Paths**: When writing hardcoded paths or absolute directories in the codebase, assume the root directory is `/data/data/com.termux/files/home`.
- **Services**: The target environment does not support `systemd` or `systemctl`. 
- **Background Processes**: The Android Phantom Killer issue on the target device has been resolved via ADB wireless pairing. Do not write code that modifies device battery optimization settings or adds wakelocks.
- **Target Packages**: When suggesting installation commands for the yuzu-companion environment, use Termux-compatible package managers (`pkg` or `apt`).
