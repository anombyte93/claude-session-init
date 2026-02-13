# Contributing to Atlas Session Lifecycle

Thanks for your interest in improving this project! This guide will help you get started.

## How to Contribute

### Reporting Issues

- Use [GitHub Issues](https://github.com/anombyte93/atlas-session-lifecycle/issues) to report bugs or suggest features
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
git clone https://github.com/YOUR_USERNAME/atlas-session-lifecycle.git
cd atlas-session-lifecycle

# Test as skill (copies to ~/.claude/skills/start/)
./install.sh

# Test as plugin (clones to ~/.claude/plugins/)
./install.sh --plugin

# Test init mode: run /start in a fresh project directory
# Test reconcile mode: run /start again in the same directory
```

### Testing Checklist

- [ ] Init mode creates `session-context/` with 5 files
- [ ] Reconcile mode detects existing session and offers Continue/Close/Redefine
- [ ] Templates are not modified during init
- [ ] Running `/start` multiple times does not corrupt state (idempotency)
- [ ] `session-init.py` subcommands all output valid JSON

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).

## Questions?

Open an issue with the "question" label or start a [Discussion](https://github.com/anombyte93/atlas-session-lifecycle/discussions).
