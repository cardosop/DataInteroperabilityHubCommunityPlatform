"""
Setup script for DataHub CLI.
"""
from setuptools import setup, find_packages
from pathlib import Path

# Read version from package
version_file = Path(__file__).parent / 'datahub_cli' / '__init__.py'
version = '1.0.0'
if version_file.exists():
    for line in version_file.read_text().splitlines():
        if line.startswith('__version__'):
            version = line.split('=')[1].strip().strip('"').strip("'")
            break

# Read long description from README if it exists
readme_file = Path(__file__).parent / 'README.md'
long_description = ''
if readme_file.exists():
    long_description = readme_file.read_text()

setup(
    name='datahub-cli',
    version=version,
    description='Command-line tool for managing DataHub resources',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='DataHub Team',
    author_email='team@datahub.example.com',
    url='https://github.com/example/datahub',
    packages=find_packages(),
    install_requires=[
        'click>=8.0.0',
        'requests>=2.31.0',
        'pyyaml>=6.0.1',
    ],
    python_requires='>=3.12',
    entry_points={
        'console_scripts': [
            'datahub=datahub_cli.main:main',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Programming Language :: Python :: 3.14',
    ],
)

