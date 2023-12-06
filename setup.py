from setuptools import find_packages, setup

setup(
    name="susscanner",
    version="1.2.2",
    author="AWS",
    packages=find_packages(include=["susscanner", "susscanner.*"]),
    package_data={"": ["rules_metadata.json", "rules/*", "rules/test_cases/*"]},
    include_package_data=True,
    install_requires=["typer==0.7.0"],
    url="http://github.com/awslabs/sustainability-scanner",
    python_requires=">=3.6",
    license="MIT-0",
    entry_points={
        "console_scripts": ["susscanner=susscanner.__main__:main"],
    },
)
