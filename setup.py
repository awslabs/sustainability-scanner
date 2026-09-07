from setuptools import find_packages, setup

setup(
    name="sustainability-scanner",
    version="1.3.0",
    author="AWS",
    description="Sustainability Scanner",
    long_description_content_type="text/markdown",
    long_description=open("README.md").read(),
    packages=find_packages(include=["susscanner", "susscanner.*"]),
    package_data={
        "": ["rules_metadata.json", "rules/*", "rules/test_cases/*", "static/*"]
    },
    include_package_data=True,
    install_requires=["typer==0.12.4"],
    url="http://github.com/awslabs/sustainability-scanner",
    # 3.9 is the real floor: susscanner/cli.py imports Annotated from typing,
    # which PEP 593 added in 3.9, so the package cannot import on 3.6-3.8.
    python_requires=">=3.9",
    license="MIT-0",
    entry_points={
        "console_scripts": ["susscanner=susscanner.__main__:main"],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Natural Language :: English",
        "License :: OSI Approved :: MIT No Attribution License (MIT-0)",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
    ],
)
