from setuptools import setup, find_packages

setup(
    name="norad",
    version="0.2.0",
    python_requires=">=3.13",
    packages=find_packages(exclude=["tests"]),
    package_data={"norad": ["lsl_api.cfg"], "norad.server": ["static/*", "static/vendor/*"]},
    # direct dependencies; exact tested versions of everything are in requirements.txt
    install_requires=["pylsl==1.18.7", "pyserial==3.5", "bleak==3.1.0", "bleakheart==0.2.0",
                      "tobiiglassesctrl==2.2.6", "numpy==2.5.5", "opencv-python==5.0.0.93",
                      "flask==3.1.3", "flask-socketio==5.7.2"],
    extras_require={"dev": ["pytest"]},
    entry_points={"console_scripts": ["norad=norad.server.app:main"]},
)
