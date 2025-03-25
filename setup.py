from setuptools import setup, find_packages

setup(
    name="P4wnForge",
    version="1.0.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "paramiko",
        "pymupdf",
        "pillow",
        "requests",
        "tqdm",
        "pikepdf",
        "PyPDF2",
        "pypdf",
    ],
    entry_points={
        "console_scripts": [
            "p4wnforge=p4wnforge:main",
        ],
    },
    author="Detective Aaron Cuddeback",
    description="A comprehensive password recovery application for various file formats",
    license="MIT",
) 