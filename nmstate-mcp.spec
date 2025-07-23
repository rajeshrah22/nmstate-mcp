Name:           nmstate-mcp
Version:        0.1.0
Release:        2%{?dist}
Summary:        MCP server for nmstate network management

License:        MIT

# Disable debug package generation (no compiled code)
%global debug_package %{nil}
URL:            https://github.com/rajeshrah22/nmstate-mcp
Source0:        %{name}-%{version}.tar.gz

# Runtime dependencies
Requires:       python3 >= 3.12
Requires:       python3-libnmstate
Requires:       uv
Requires:       ansible-core

%description
A Model Context Protocol (MCP) server implementation that works with MCP clients
to enable LLM-powered network management using nmstate. This tool allows AI
assistants to manage network configurations through nmstate and ansible.

%prep
%setup -q

%build
# Nothing to build for this pure Python package

%install
# Create directory structure
mkdir -p %{buildroot}%{_bindir}
mkdir -p %{buildroot}%{_datadir}/%{name}
mkdir -p %{buildroot}%{_docdir}/%{name}

# Install main application
install -m 755 main.py %{buildroot}%{_datadir}/%{name}/main.py

# Install setup script
install -m 755 setup_cursor.py %{buildroot}%{_datadir}/%{name}/setup_cursor.py

# Install uv.lock for reproducible dependencies
install -m 644 uv.lock %{buildroot}%{_datadir}/%{name}/uv.lock

# Install pyproject.toml (needed by uv)
install -m 644 pyproject.toml %{buildroot}%{_datadir}/%{name}/pyproject.toml

# Install documentation
install -m 644 README.md %{buildroot}%{_docdir}/%{name}/README.md

# Create wrapper scripts
cat > %{buildroot}%{_bindir}/nmstate-mcp << 'EOF'
#!/bin/bash
# nmstate-mcp wrapper script
export UV_CACHE_DIR="${HOME}/.cache/nmstate-mcp"
export UV_PROJECT_ENVIRONMENT="${HOME}/.cache/nmstate-mcp/.venv"
exec uv run --directory %{_datadir}/%{name} main.py "$@"
EOF

cat > %{buildroot}%{_bindir}/nmstate-mcp-setup << 'EOF'
#!/bin/bash
export UV_CACHE_DIR="${HOME}/.cache/nmstate-mcp"
export UV_PROJECT_ENVIRONMENT="${HOME}/.cache/nmstate-mcp/.venv"
exec python3 %{_datadir}/%{name}/setup_cursor.py "$@"
EOF

chmod 755 %{buildroot}%{_bindir}/nmstate-mcp
chmod 755 %{buildroot}%{_bindir}/nmstate-mcp-setup

%files
%license LICENSE
%doc %{_docdir}/%{name}/README.md
%{_bindir}/nmstate-mcp
%{_bindir}/nmstate-mcp-setup
%{_datadir}/%{name}/main.py
%{_datadir}/%{name}/setup_cursor.py
%{_datadir}/%{name}/uv.lock
%{_datadir}/%{name}/pyproject.toml

%post
echo "nmstate-mcp has been installed!"
echo ""
echo "To get started:"
echo "1. Run 'nmstate-mcp-setup' to configure your MCP client"
echo "2. Or manually configure your MCP client to use 'nmstate-mcp'"
echo ""
echo "For more information, see: %{_docdir}/%{name}/README.md"

%changelog
* Sun Jul 20 2025 Rahul Rajesh <rajeshrah22@gmail.com> - 0.1.0-1
- Initial package for nmstate-mcp
- MCP server for nmstate network management
- Includes setup script for MCP client configuration
- Work in progress release
