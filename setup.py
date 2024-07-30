from setuptools import find_packages, setup
from typing import List

HYPHEN_E_DOT = '-e .'

def get_requirements(file_path: str) -> List[str]:
    '''
    This function will return the list of requirements.
    '''
    try:
        with open(file_path, 'r') as file_obj:
            requirements = [req.strip() for req in file_obj.readlines() if req.strip() and req.strip() != HYPHEN_E_DOT]
        return requirements
    except FileNotFoundError:
        print(f"Warning: {file_path} not found.")
        return []

setup(
    name='mlproject',
    version='0.0.1',
    author='Aj',
    author_email='crimsondew@gmail.com',
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=get_requirements('requirements.txt'),
)