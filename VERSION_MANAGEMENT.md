# Version Management

This project includes automated version management scripts to easily increment package versions across all files.

## Scripts

### `./scripts/show-version.sh`
Display current version information across all files.

```bash
./scripts/show-version.sh
```

Output:
```
APC UPS Monitor - Current Version Information
=============================================
setup.py:              1.1.0
src/__init__.py:       1.1.0
debian/changelog:      1.1.0-1

✅ All versions are consistent: 1.1.0
```

### `./scripts/bump-version.sh`
Increment version numbers across the project.

#### Usage Options

**Patch version bump** (1.0.0 → 1.0.1):
```bash
./scripts/bump-version.sh patch
```

**Minor version bump** (1.0.0 → 1.1.0):
```bash
./scripts/bump-version.sh minor
```

**Major version bump** (1.0.0 → 2.0.0):
```bash
./scripts/bump-version.sh major
```

**Set specific version**:
```bash
./scripts/bump-version.sh 1.2.3
```

#### What it updates
- `setup.py` - Package version
- `src/__init__.py` - Module version constant  
- `src/apc_ups_monitor.py` - Health endpoint version
- `debian/changelog` - Debian package changelog

#### What it cleans up
- Removes build artifacts (`build/`, `dist/`, `*.egg-info`)
- Forces clean rebuild of package

## Workflow

1. **Check current version**:
   ```bash
   ./scripts/show-version.sh
   ```

2. **Bump version**:
   ```bash
   ./scripts/bump-version.sh patch
   ```

3. **Review changes**:
   ```bash
   git diff
   ```

4. **Build package**:
   ```bash
   dpkg-buildpackage -us -uc
   ```

5. **Commit and tag**:
   ```bash
   git add .
   git commit -m "Bump version to 1.1.1"
   git tag v1.1.1
   ```

## Files Updated

The version bump script updates versions in these specific locations:

| File | Pattern | Example |
|------|---------|---------|
| `setup.py` | `version="X.Y.Z"` | `version="1.1.0"` |
| `src/__init__.py` | `__version__ = "X.Y.Z"` | `__version__ = "1.1.0"` |
| `src/apc_ups_monitor.py` | `'version': 'X.Y.Z'` | `'version': '1.1.0'` |
| `debian/changelog` | New entry created | `apc-ups-monitor (1.1.0-1)` |

The script uses precise patterns to avoid accidentally replacing version-like numbers elsewhere in the code.