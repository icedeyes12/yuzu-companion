# Contributing to yuzu-companion

Thank you for your interest in contributing! Here's how to get started.

## Development Setup

```bash
git clone https://github.com/icedeyes12/yuzu-companion.git
cd yuzu-companion
pip install -r requirements.txt
cp config.example.json config.json
# Fill in your API keys in config.json
python main.py
```

## Project Structure

```
yuzu-companion/
├── app/              # Flask app routes
├── memory/           # Memory system (embedder, retrieval, FSRS review)
├── tools/            # MCP tools & registry
├── templates/        # HTML templates
├── static/           # CSS, JS, assets
└── main.py           # Entry point
```

## Code Style

- Python: 4-space indent, docstrings on all public functions
- JS: ES6+, no unused variables
- CSS: BEM-ish naming, CSS variables for theming

## Commit Messages

Format: \`type: short description\`

Types: \`feat\`, \`fix\`, \`refactor\`, \`docs\`, \`chore\`, \`test\`

## Testing

```bash
python -m pytest tests/ -v
python main.py --test
```

## Pull Request Checklist

- [ ] Tests pass locally
- [ ] No new lint errors
- [ ] CHANGELOG.md updated if applicable
- [ ] Commits are descriptive and atomic

## Issues

Before opening an issue, check existing issues and the FAQ in README.md.
