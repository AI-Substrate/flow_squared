# LSP Server Binary Distribution: Best Practices Research

> **Research Date**: 2026-01-14
> **Context**: fs2 (Flowspace2) integration with external LSP servers
> **Target Servers**: Pyright, gopls, OmniSharp, typescript-language-server

---

## Executive Summary

This research examines best practices for Python tools that depend on external CLI binaries like LSP servers. Key findings:

1. **Documentation-first approach**: Clear, platform-specific installation instructions prevent most user issues
2. **Robust detection**: Use `shutil.which()` + subprocess version checks for reliable binary discovery
3. **Actionable errors**: Distinguish between "not installed", "not in PATH", and "wrong version"
4. **Graceful degradation**: Detect available servers and adapt functionality accordingly
5. **Cross-platform awareness**: Handle npm, Go, and .NET package manager differences

---

## 1. Best Practices for Python Tools with External Binary Dependencies

### Architecture Patterns

Mature Python tools implement a layered approach to binary management:

1. **Binary presence should be optional when possible** - tools should degrade gracefully
2. **Fail-fast with clear diagnostics** - follow Python's "Errors should never pass silently" principle
3. **Use subprocess.run() with proper error handling** for external binary execution

### Detection and Validation Pattern

Detection involves three sub-steps:
1. Check if binary exists on PATH
2. Verify it's executable
3. Confirm it's the correct tool (not a name collision) via version check

```python
import subprocess
import shutil
from pathlib import Path

def detect_and_validate_lsp_server(server_name: str, version_command: list[str]) -> tuple[bool, str]:
    """
    Detect an LSP server and validate it's executable and has correct version.

    Returns: (is_available, path_or_error_message)
    """
    # Step 1: Try to find the executable on PATH
    executable_path = shutil.which(server_name)

    if executable_path is None:
        return False, f"'{server_name}' not found in PATH. Please install it first."

    # Step 2: Verify it's actually executable
    try:
        path_obj = Path(executable_path)
        if not path_obj.exists():
            return False, f"'{server_name}' path exists in PATH but file not found at {executable_path}"
        if not path_obj.is_file():
            return False, f"'{server_name}' at {executable_path} is not a regular file"
    except (OSError, PermissionError) as e:
        return False, f"Cannot access '{server_name}' at {executable_path}: {e}"

    # Step 3: Verify it's the correct tool by checking version output
    try:
        result = subprocess.run(
            version_command,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            stderr_msg = result.stderr.strip() if result.stderr else "unknown error"
            return False, f"'{server_name}' returned error when checking version: {stderr_msg}"

        # Tool is valid, return success with the path
        return True, executable_path
    except subprocess.TimeoutExpired:
        return False, f"'{server_name}' version check timed out"
    except Exception as e:
        return False, f"Error verifying '{server_name}': {e}"
```

### Environment Variable Considerations

External binaries execute in the environment inherited from Python. Key issues:

- **PATH determines where executables are found** across all platforms
- **PATHEXT on Windows** controls executable extension search order
- **Virtual environments** may have different binaries than global installations
- **IDE/daemon contexts** may not inherit user shell environment variables

```python
import os

def run_with_custom_env(command: list[str], additional_env: dict | None = None) -> subprocess.CompletedProcess:
    """Run a command with augmented environment variables."""
    env = os.environ.copy()
    if additional_env:
        env.update(additional_env)

    return subprocess.run(command, env=env, capture_output=True, text=True, check=True)
```

---

## 2. How Popular LSP Clients Handle Installation/Detection

### coc.nvim: Plugin-Based Installation

- **Dual approach**: Extension system (`:CocInstall coc-tsserver`) + manual configuration
- **Explicit documentation**: Users must install servers following upstream instructions
- **Health checks**: Verify server status to diagnose issues
- **Clear commands**: Documents exact npm commands (`npm i -g typescript-language-server`)

### Neovim nvim-lspconfig: Separation of Concerns

- **Configuration distinct from installation**: Provides pre-configured specs, doesn't install servers
- **Expected workflow**: Install server independently, then enable in init.lua
- **Root directory detection**: Automatic via configurable root markers
- **Override flexibility**: Users can set custom `cmd` parameter for non-PATH installations

```lua
vim.lsp.config('jdtls', {
  cmd = { '/path/to/jdtls' },
})
```

### Helix Editor: Documentation-Forward Approach

- **Wiki page with table**: Language -> LSP server -> installation command
- **Direct links**: Upstream installation instructions
- **Scalable pattern**: Easy to maintain and extend

### Emacs lsp-mode: Automatic Download Option

- **Offers to auto-install** missing servers
- **Environment propagation challenges**: Requires exec-path-from-shell package
- **Custom environment variables** configurable per language server

---

## 3. Pattern for Optional External Binary Dependencies

### Distinguishing Optional from Required

Python's `pyproject.toml` handles optional Python dependencies via `[project.optional-dependencies]`. For external binaries:

1. **Document clearly** which servers are optional vs required for core functionality
2. **Detect at runtime** and adapt capabilities accordingly
3. **Report available functionality** rather than failing completely

### Runtime Detection and Graceful Degradation

```python
from typing import Dict
from pathlib import Path

class LSPServerRegistry:
    def __init__(self):
        self.available_servers: Dict[str, Path] = {}
        self.unavailable_servers: Dict[str, str] = {}  # name -> error reason

    def detect_all_servers(self):
        """Detect which LSP servers are available."""
        servers = {
            'pyright': ['pyright', '--version'],
            'gopls': ['gopls', 'version'],
            'omnisharp': ['OmniSharp', '--version'],
            'typescript-language-server': ['typescript-language-server', '--version'],
        }

        for server_name, version_cmd in servers.items():
            is_available, result = detect_and_validate_lsp_server(server_name, version_cmd)
            if is_available:
                self.available_servers[server_name] = result
            else:
                self.unavailable_servers[server_name] = result

    def report_capabilities(self) -> str:
        """Generate a user-friendly report of available LSP servers."""
        lines = ["=== fs2 Language Server Availability ===\n"]

        if self.available_servers:
            lines.append("Available servers:")
            for name, path in self.available_servers.items():
                lines.append(f"  [OK] {name}: {path}")
        else:
            lines.append("[WARNING] No LSP servers detected.")

        if self.unavailable_servers:
            lines.append("\nMissing servers (functionality will be limited):")
            for name, error in self.unavailable_servers.items():
                lines.append(f"  [MISSING] {name}: {error}")

        return "\n".join(lines)
```

---

## 4. Cross-Platform Installation Instructions

### npm-Installed Tools: Pyright, typescript-language-server

**Prerequisite**: Node.js >= 16.18.0

| Platform | Node.js Installation |
|----------|---------------------|
| macOS | `brew install node` |
| Windows | https://nodejs.org/ |
| Linux | Package manager (apt, yum, pacman, etc.) |

**Installation (all platforms)**:
```bash
npm install -g typescript-language-server typescript
npm install -g pyright
```

**Verification**:
```bash
typescript-language-server --version
pyright --version
```

**Windows Note**: npm creates `.cmd` wrapper scripts. Detection must find the proper Windows executable.

### go install Tools: gopls

**Prerequisite**: Go >= 1.21

| Platform | Go Installation |
|----------|-----------------|
| macOS | `brew install go` |
| Windows | https://go.dev/dl/ or `choco install golang` |
| Linux | Package manager or https://go.dev/dl/ |

**Installation**:
```bash
go install golang.org/x/tools/gopls@latest
```

**Verification** (note: uses `version` not `--version`):
```bash
gopls version
```

**PATH Note**: Ensure `$GOPATH/bin` (Unix) or `%GOPATH%\bin` (Windows) is in PATH.

### .NET Tools: OmniSharp

**Option 1: Using dotnet CLI (recommended)**

| Platform | .NET SDK Installation |
|----------|----------------------|
| Windows | https://dotnet.microsoft.com/download |
| macOS | `brew install dotnet` |
| Linux | https://dotnet.microsoft.com/download |

```bash
dotnet tool install -g OmniSharp
OmniSharp --version
```

**Option 2: Pre-built binaries**

Download from https://github.com/OmniSharp/omnisharp-roslyn/releases

### Platform-Specific Guidance Generator

```python
import platform

def get_install_guidance(server_name: str) -> str:
    """Get platform-specific installation guidance."""
    system = platform.system()  # 'Windows', 'Darwin', 'Linux'

    guidance = {
        'typescript-language-server': {
            'Windows': 'npm install -g typescript-language-server typescript',
            'Darwin': 'npm install -g typescript-language-server typescript',
            'Linux': 'npm install -g typescript-language-server typescript',
        },
        'gopls': {
            'Windows': 'go install golang.org/x/tools/gopls@latest',
            'Darwin': 'go install golang.org/x/tools/gopls@latest',
            'Linux': 'go install golang.org/x/tools/gopls@latest',
        },
        'OmniSharp': {
            'Windows': 'dotnet tool install -g OmniSharp',
            'Darwin': 'dotnet tool install -g OmniSharp',
            'Linux': 'dotnet tool install -g OmniSharp',
        },
        'pyright': {
            'Windows': 'npm install -g pyright',
            'Darwin': 'npm install -g pyright',
            'Linux': 'npm install -g pyright',
        },
    }

    if server_name not in guidance:
        return f"Unknown server: {server_name}"

    command = guidance[server_name].get(system, 'Unsupported platform')
    return f"To install {server_name} on {system}:\n  {command}"
```

---

## 5. UX Patterns for Missing Binary Detection

### Error Message Requirements

A well-designed error message should:
1. **Clearly state what is missing**
2. **Explain why it matters** (impact on functionality)
3. **Provide specific installation instructions**
4. **Suggest troubleshooting steps**

### Example Error Message Format

**Poor error message**:
```
LSP initialization failed
```

**Good error message**:
```
Error: TypeScript language server not found

The 'typescript-language-server' binary is required for TypeScript/JavaScript analysis.
It was not found in your PATH. fs2 cannot perform cross-file JavaScript analysis without it.

To install:
  npm install -g typescript-language-server typescript

To verify installation:
  typescript-language-server --version

If already installed:
  - Check it's in your PATH: which typescript-language-server
  - Restart your editor/terminal
```

### Distinguishing Failure Modes

```python
def diagnose_server_issue(server_name: str, expected_version_min: str | None = None) -> str:
    """Provide diagnostic information about why a server isn't working."""

    # First check: is it on the PATH at all?
    executable_path = shutil.which(server_name)
    if not executable_path:
        return f"'{server_name}' not found in PATH. Install it or add its location to PATH."

    # Second check: can we execute it and get version?
    try:
        result = subprocess.run(
            [executable_path, '--version'],
            capture_output=True,
            text=True,
            timeout=3
        )
    except subprocess.TimeoutExpired:
        return f"'{server_name}' found at {executable_path} but version check timed out. May be misconfigured."
    except FileNotFoundError:
        return f"'{server_name}' found in PATH but cannot execute. Check permissions or broken symlink."

    if result.returncode != 0:
        error_details = result.stderr.strip() if result.stderr else result.stdout.strip()
        return f"'{server_name}' at {executable_path} cannot determine version. Error: {error_details}"

    # Third check: is version acceptable?
    if expected_version_min:
        actual_version = parse_version_output(result.stdout, server_name)
        if actual_version and actual_version < Version(expected_version_min):
            return f"'{server_name}' version {actual_version} is below minimum required {expected_version_min}. Upgrade it."

    return f"'{server_name}' is properly installed at {executable_path}"
```

### Startup Configuration Report

Report capabilities at startup rather than waiting for failures:

```
$ fs2 analyze project/

fs2 Configuration Report
========================

Available Language Servers:
  [OK] Pyright 1.1.320 (Python analysis)
  [OK] typescript-language-server 4.3.1 (TypeScript/JavaScript analysis)
  [MISSING] gopls (Go analysis) - not installed
      Install with: go install golang.org/x/tools/gopls@latest
  [WARNING] OmniSharp (C# analysis) - found but version 1.36.0 < recommended 1.37.0
      Update with: dotnet tool update -g OmniSharp

Analyzing with enabled servers...
```

---

## 6. Binary Detection Approaches in Python

### shutil.which() Behavior

```python
import shutil

# Basic usage
typescript_server_path = shutil.which('typescript-language-server')
if typescript_server_path:
    print(f"Found at: {typescript_server_path}")
else:
    print("Not found in PATH")
```

**Platform Differences**:
- **Unix**: Checks executable permission bits
- **Windows**: Uses PATHEXT to search for .COM, .EXE, .BAT, .CMD extensions

**Historical Bug (Python 3.12)**: npm creates both `.cmd` wrapper and bash script on Windows. Early 3.12 versions incorrectly preferred the bash script. Now fixed.

**Limitations of shutil.which()**:
- Doesn't verify it's the expected tool (name collisions possible)
- Doesn't check version
- Doesn't handle broken symlinks or permission issues

### Subprocess Verification

Different tools have different version commands:

| Server | Version Command |
|--------|----------------|
| Pyright | `pyright --version` |
| typescript-language-server | `typescript-language-server --version` |
| gopls | `gopls version` (not `--version`!) |
| OmniSharp | `OmniSharp --version` |

```python
import re
from packaging import version

class VersionChecker:
    @staticmethod
    def check_pyright_version(path: str) -> str | None:
        """Extract version from pyright --version output."""
        result = subprocess.run(
            [path, '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # Output format: "pyright 1.1.320"
            match = re.search(r'(\d+\.\d+\.\d+)', result.stdout)
            return match.group(1) if match else None
        return None

    @staticmethod
    def check_gopls_version(path: str) -> str | None:
        """Extract version from gopls version output."""
        result = subprocess.run(
            [path, 'version'],  # Note: 'version' not '--version'
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # gopls outputs: "golang.org/x/tools/gopls v0.14.2 ..."
            match = re.search(r'golang\.org/x/tools/gopls\s+v(\d+\.\d+\.\d+)', result.stdout)
            return match.group(1) if match else None
        return None
```

### Virtual Environment Handling

```python
import os
import sys

def get_prioritized_path() -> str:
    """Get PATH with virtual environment bin directory prioritized."""
    path_dirs = []

    # If in a virtual environment, prioritize its bin directory
    if hasattr(sys, 'prefix') and hasattr(sys, 'base_prefix') and sys.prefix != sys.base_prefix:
        venv_bin = os.path.join(sys.prefix, 'Scripts' if sys.platform == 'win32' else 'bin')
        path_dirs.append(venv_bin)

    # Add existing PATH
    path_dirs.extend(os.environ.get('PATH', '').split(os.pathsep))

    return os.pathsep.join(path_dirs)

def find_executable(name: str) -> str | None:
    """Find executable with virtual environment priority."""
    old_path = os.environ.get('PATH')
    try:
        os.environ['PATH'] = get_prioritized_path()
        return shutil.which(name)
    finally:
        if old_path:
            os.environ['PATH'] = old_path
```

### Windows Shell Execution

npm-installed tools may require shell execution on Windows:

```python
def run_npm_tool_windows(tool_name: str, args: list[str]) -> subprocess.CompletedProcess:
    """Run an npm-installed tool, handling Windows shell requirements."""
    if sys.platform == 'win32':
        # On Windows, npm creates .cmd wrapper scripts
        command_string = ' '.join([tool_name] + args)
        return subprocess.run(
            command_string,
            shell=True,
            capture_output=True,
            text=True
        )
    else:
        # On Unix, direct execution works fine
        return subprocess.run(
            [tool_name] + args,
            capture_output=True,
            text=True
        )
```

---

## 7. Version Requirement Handling

### Specifying Minimum Versions

```python
from packaging import version as pkg_version

class ServerRequirements:
    """Minimum version requirements for supported LSP servers."""
    REQUIREMENTS = {
        'pyright': '1.1.300',
        'typescript-language-server': '4.0.0',
        'gopls': '0.13.0',
        'OmniSharp': '1.37.0',
    }

    @classmethod
    def is_version_acceptable(cls, server_name: str, installed_version: str) -> bool:
        """Check if installed version meets requirements."""
        if server_name not in cls.REQUIREMENTS:
            return True  # Unknown server, assume acceptable

        min_required = pkg_version.parse(cls.REQUIREMENTS[server_name])
        installed = pkg_version.parse(installed_version)

        return installed >= min_required
```

### Parsing Version Output

```python
import re
from typing import Optional

class VersionParser:
    @staticmethod
    def parse_pyright(output: str) -> Optional[str]:
        """Parse pyright --version output."""
        # Format: "pyright 1.1.320"
        match = re.search(r'pyright\s+(\d+\.\d+\.\d+)', output, re.IGNORECASE)
        return match.group(1) if match else None

    @staticmethod
    def parse_gopls(output: str) -> Optional[str]:
        """Parse gopls version output."""
        # Format: "golang.org/x/tools/gopls v0.14.2 ..."
        match = re.search(r'golang\.org/x/tools/gopls\s+v(\d+\.\d+\.\d+)', output)
        return match.group(1) if match else None

    @staticmethod
    def parse_typescript_language_server(output: str) -> Optional[str]:
        """Parse typescript-language-server --version output."""
        match = re.search(r'(\d+\.\d+\.\d+)', output)
        return match.group(1) if match else None

    @staticmethod
    def parse_omnisharp(output: str) -> Optional[str]:
        """Parse OmniSharp version output."""
        match = re.search(r'(\d+\.\d+\.\d+)', output)
        return match.group(1) if match else None
```

### Upgrade Guidance

```python
def handle_incompatible_version(server_name: str, installed_version: str, required_version: str) -> str:
    """Generate upgrade guidance for outdated servers."""

    upgrade_commands = {
        'pyright': f"npm install -g pyright@{required_version}",
        'typescript-language-server': f"npm install -g typescript-language-server@{required_version}",
        'gopls': "go install golang.org/x/tools/gopls@latest",
        'OmniSharp': "dotnet tool update -g OmniSharp",
    }

    command = upgrade_commands.get(server_name, f"See documentation for {server_name}")

    return f"""
Warning: {server_name} version is too old

  Installed: {installed_version}
  Required:  {required_version}

Upgrade with:
  {command}

Verify with:
  {server_name} --version
""".strip()
```

---

## 8. Complete Implementation: LSPServerManager

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict
from pathlib import Path
import subprocess
import shutil
import re
from packaging import version as pkg_version

class ServerStatus(Enum):
    READY = "ready"
    MISSING = "missing"
    WRONG_VERSION = "wrong_version"
    MISCONFIGURED = "misconfigured"

@dataclass
class ServerInfo:
    name: str
    path: Optional[str]
    version: Optional[str]
    status: ServerStatus
    message: str
    upgrade_commands: list[str]

class LSPServerManager:
    """Manages detection, validation, and reporting for LSP servers."""

    # Server configurations: name -> (version_cmd, min_version)
    SERVER_CONFIGS = {
        'pyright': (['pyright', '--version'], '1.1.300'),
        'typescript-language-server': (['typescript-language-server', '--version'], '4.0.0'),
        'gopls': (['gopls', 'version'], '0.13.0'),
        'OmniSharp': (['OmniSharp', '--version'], '1.37.0'),
    }

    INSTALL_COMMANDS = {
        'pyright': ['npm install -g pyright', 'pip install pyright'],
        'typescript-language-server': ['npm install -g typescript-language-server typescript'],
        'gopls': ['go install golang.org/x/tools/gopls@latest'],
        'OmniSharp': ['dotnet tool install -g OmniSharp'],
    }

    UPGRADE_COMMANDS = {
        'pyright': ['npm install -g pyright'],
        'typescript-language-server': ['npm install -g typescript-language-server'],
        'gopls': ['go install golang.org/x/tools/gopls@latest'],
        'OmniSharp': ['dotnet tool update -g OmniSharp'],
    }

    def __init__(self):
        self.servers: Dict[str, ServerInfo] = {}

    def initialize(self):
        """Detect and validate all configured LSP servers."""
        for name, (version_cmd, min_version) in self.SERVER_CONFIGS.items():
            self.servers[name] = self._check_server(name, version_cmd, min_version)

    def _check_server(self, name: str, version_cmd: list[str], min_version: str) -> ServerInfo:
        """Check status of a single server."""

        # Step 1: Find executable
        path = shutil.which(name)
        if not path:
            return ServerInfo(
                name=name,
                path=None,
                version=None,
                status=ServerStatus.MISSING,
                message=f"'{name}' not found in PATH",
                upgrade_commands=self.INSTALL_COMMANDS.get(name, []),
            )

        # Step 2: Check version
        try:
            result = subprocess.run(
                version_cmd,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                return ServerInfo(
                    name=name,
                    path=path,
                    version=None,
                    status=ServerStatus.MISCONFIGURED,
                    message=f"'{name}' exists but version check failed",
                    upgrade_commands=[],
                )

            version_str = self._parse_version(name, result.stdout)
            if not version_str:
                return ServerInfo(
                    name=name,
                    path=path,
                    version=None,
                    status=ServerStatus.MISCONFIGURED,
                    message=f"'{name}' exists but version could not be determined",
                    upgrade_commands=[],
                )

            # Step 3: Check version requirement
            if not self._is_version_acceptable(version_str, min_version):
                return ServerInfo(
                    name=name,
                    path=path,
                    version=version_str,
                    status=ServerStatus.WRONG_VERSION,
                    message=f"'{name}' version {version_str} is below required {min_version}",
                    upgrade_commands=self.UPGRADE_COMMANDS.get(name, []),
                )

            # All checks passed
            return ServerInfo(
                name=name,
                path=path,
                version=version_str,
                status=ServerStatus.READY,
                message=f"Ready ({version_str})",
                upgrade_commands=[],
            )

        except subprocess.TimeoutExpired:
            return ServerInfo(
                name=name,
                path=path,
                version=None,
                status=ServerStatus.MISCONFIGURED,
                message=f"'{name}' version check timed out",
                upgrade_commands=[],
            )
        except Exception as e:
            return ServerInfo(
                name=name,
                path=path,
                version=None,
                status=ServerStatus.MISCONFIGURED,
                message=f"Error checking '{name}': {e}",
                upgrade_commands=[],
            )

    def _parse_version(self, server_name: str, output: str) -> Optional[str]:
        """Parse version from server output."""
        patterns = {
            'pyright': r'pyright\s+(\d+\.\d+\.\d+)',
            'typescript-language-server': r'(\d+\.\d+\.\d+)',
            'gopls': r'golang\.org/x/tools/gopls\s+v(\d+\.\d+\.\d+)',
            'OmniSharp': r'(\d+\.\d+\.\d+)',
        }
        pattern = patterns.get(server_name, r'(\d+\.\d+\.\d+)')
        match = re.search(pattern, output, re.IGNORECASE)
        return match.group(1) if match else None

    def _is_version_acceptable(self, installed: str, required: str) -> bool:
        """Check if installed version meets requirement."""
        try:
            return pkg_version.parse(installed) >= pkg_version.parse(required)
        except:
            return False

    def get_ready_servers(self) -> list[ServerInfo]:
        """Get list of servers that are ready to use."""
        return [s for s in self.servers.values() if s.status == ServerStatus.READY]

    def require_server(self, server_name: str) -> str:
        """Get path to a required server, raising if unavailable."""
        if server_name not in self.servers:
            raise RuntimeError(f"Unknown server: {server_name}")

        server = self.servers[server_name]
        if server.status == ServerStatus.READY:
            return server.path

        raise RuntimeError(
            f"Cannot use {server_name}: {server.message}\n"
            f"Run 'fs2 --check-servers' for installation guidance."
        )
```

---

## 9. Common Pitfalls and Solutions

### Pitfall 1: Windows PATH/PATHEXT Issues

**Problem**: npm creates both `.cmd` wrapper and bash script; wrong one may be found.

**Solution**: Test on Windows explicitly; rely on updated Python 3.12+ which fixes `shutil.which()`.

### Pitfall 2: Virtual Environment Binary Confusion

**Problem**: Global binary found instead of project-specific one.

**Solution**: Prioritize virtual environment bin directory in PATH search.

### Pitfall 3: IDE/Daemon Environment Differences

**Problem**: Tools work in terminal but not when run from IDE or daemon.

**Solution**:
- Document environment requirements
- Use exec-path-from-shell pattern (load shell environment)
- Allow explicit path configuration

### Pitfall 4: Version Command Variations

**Problem**: `gopls version` vs `pyright --version` - inconsistent interfaces.

**Solution**: Server-specific configuration for version commands.

### Pitfall 5: Silent Failures

**Problem**: Tool continues with reduced functionality without informing user.

**Solution**: Report capabilities at startup; fail-fast with actionable errors.

---

## 10. Recommendations for fs2

### Immediate Actions

1. **Implement LSPServerManager class** encapsulating detection, validation, and reporting
2. **Create platform-specific documentation** following Helix's model
3. **Integrate Rich** for formatted terminal output
4. **Provide CLI commands**: `fs2 --check-servers`, `fs2 --install-guidance [server]`

### Design Principles

1. **Detection at startup** - report status before attempting analysis
2. **Graceful degradation** - work with available servers
3. **Actionable errors** - always include installation commands
4. **Cross-platform testing** - especially Windows npm wrappers

### CLI Integration

```bash
# Check server status
fs2 --check-servers

# Get installation guidance
fs2 --install-guidance pyright

# Normal operation with status report
fs2 analyze ./project/
```

---

## Sources

1. IBM Data Science Best Practices - Dependency Management
2. Neovim LSP Documentation
3. Python CPython Issues - shutil.which() Windows behavior
4. Python Packaging Tutorial
5. coc.nvim GitHub Repository
6. Python shutil Documentation
7. Python Poetry Discussions
8. BetterStack Pyright Guide
9. Helix Editor GitHub Issues
10. Go gopls Documentation
11. nvim-lspconfig GitHub Repository
12. OmniSharp GitHub Repository
13. Python Errors Should Not Pass Silently - PyBites
14. Python subprocess Documentation
15. Emacs lsp-mode GitHub Issues
16. BetterStack Python Subprocess Guide
17. typescript-language-server npm Package
18. Microsoft .NET Tool Install Documentation
19. Python Packaging Versioning
20. Rich Documentation
21. Python platform Module Documentation
