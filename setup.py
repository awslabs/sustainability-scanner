from setuptools import find_packages, setup

setup(
    name="susscanner",
    version="1.0.0",
    author="AWS",
    packages=find_packages(include=["susscanner", "susscanner.*"]),
    install_requires=["typer==0.7.0"],
    url="http://github.com/awslabs/sustainability_scanner",
    python_requires=">=3.6",
    license="MIT-0",
    entry_points={
        "console_scripts": ["susscanner=susscanner.__main__:main"],
    },
)
