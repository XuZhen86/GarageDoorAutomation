import setuptools

setuptools.setup(
    name='garage-door-automation',
    version='0.1',
    author='XuZhen86',
    url='https://github.com/XuZhen86/GarageDoorAutomation',
    packages=setuptools.find_packages(),
    python_requires='==3.11.3',
    install_requires=[
        'absl-py==1.4.0',
        'aioconsole==0.6.1',
        'asyncio-mqtt==0.16.1',
        'line_protocol_cache@git+https://github.com/XuZhen86/LineProtocolCache@8a9f994',
        'pytz==2023.3',
        'requests==2.31.0',
        'suntime==1.2.5',
        'timezonefinder==6.2.0',
    ],
    entry_points={
        'console_scripts': [
            'garage-door-automation = garage_door_automation.main:app_run_main',
        ],
    },
)
