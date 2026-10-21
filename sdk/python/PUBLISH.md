# Publishing SDK to PyPI

## Prerequisites

1. PyPI account with access to `datahub-interoperability` package
2. Authentication configured: `pip install twine`
3. Build completed: `python setup.py sdist bdist_wheel`
4. Tests passing: `pytest`

## Publishing Steps

### 1. Update Version

Update version in `setup.py` and `pyproject.toml`:
- Patch: 1.0.0 → 1.0.1
- Minor: 1.0.0 → 1.1.0
- Major: 1.0.0 → 2.0.0

### 2. Build Package

```bash
python setup.py sdist bdist_wheel
```

Or using build tool:
```bash
python -m build
```

### 3. Test Package

```bash
twine check dist/*
```

### 4. Upload to TestPyPI (Optional)

```bash
twine upload --repository testpypi dist/*
```

### 5. Publish to PyPI

```bash
twine upload dist/*
```

## CI/CD Integration

Add to CI/CD pipeline:

```yaml
- name: Publish to PyPI
  if: github.ref == 'refs/heads/main' && github.event_name == 'push'
  run: |
    python -m build
    twine check dist/*
    twine upload dist/*
  env:
    TWINE_USERNAME: __token__
    TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
```

## Notes

- Package will be published as `datahub-interoperability`
- Version follows semantic versioning
- Requires `twine` for uploading: `pip install twine build`

