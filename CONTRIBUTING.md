# Contributing to Claude Session Init

Thanks for your interest in improving this skill! This guide will help you get started.

## How to Contribute

### Reporting Issues

- Use [GitHub Issues](https://github.com/anombyte93/claude-session-init/issues) to report bugs or suggest features
- Check existing issues before creating a new one

### Submitting Changes

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Test by running the skill in a test project directory
4. Commit with clear messages
5. Push to your fork and submit a Pull Request

### Areas for Contribution

- New or improved memory bank templates
- Better file categorization rules
- Support for additional project types
- Documentation improvements
- Install script improvements

### Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/claude-session-init.git

# Test the skill
cp start.md ~/.claude/skills/session-init/start.md
cp -r templates/ ~/claude-session-init-templates/

# Or use the install script
./install.sh
```

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).

## Questions?

Open an issue with the "question" label or start a [Discussion](https://github.com/anombyte93/claude-session-init/discussions).
