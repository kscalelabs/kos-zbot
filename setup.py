from setuptools import setup, find_packages

setup(
    name='kos-zbot',
    version='0.1.0',
    description='K-OS ZBot Robotics Control Suite',
    author='Scott Carlson',
    author_email='scott@kscale.dev',
    url='https://github.com/kscalelabs/kos-zbot',
    packages=find_packages(),
    install_requires=[
        'pyserial==3.5',
        'grpcio',
        'pykos>=0.7.9',
        'adafruit-circuitpython-bno055',
        'psutil',
        'tabulate',
        'tqdm',
        'numpy',
        'dotenv',
        'pyaudio',
        'sounddevice',
        'pydub',
        'pyee',
        'openai[realtime]',
        'protobuf==5.29.0',
        'click',
        'rich',
        'RPi.GPIO'
    ],
    entry_points={
        'console_scripts': [
            'kos=kos_zbot.cli:cli',
        ],
    },
    include_package_data=True,
    python_requires='>=3.12',
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ],
)