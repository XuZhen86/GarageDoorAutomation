import setuptools

setuptools.setup(
    name='garage-door-automation',
    version='0.1',
    author='XuZhen86',
    url='https://github.com/XuZhen86/GarageDoorAutomation',
    packages=setuptools.find_packages(),
    python_requires='>=3.11',
    install_requires=[
        'absl-py>=1.3.0',
        'asyncio-mqtt>=0.16.1',
        'pytz>=2023.3',
        'suntime>=1.2.5',
        'timezonefinder>=6.2.0',
    ],
    entry_points={
        'console_scripts': [
            'garage-door-automation = garage_door_automation.main:app_run_main',
        ],
    },
)
