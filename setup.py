from setuptools import setup, find_packages

setup(
    name="norad",
    version="0.2.0",
    python_requires=">=3.11",
    packages=find_packages(exclude=["tests"]),
    package_data={"norad": ["lsl_api.cfg"], "norad.server": ["static/*", "static/vendor/*"]},
    install_requires=open("requirements.txt").read().split(),
    extras_require={"dev": ["pytest"]},
    entry_points={"console_scripts": ["norad=norad.server.app:main"]},
)
