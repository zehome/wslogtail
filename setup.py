from setuptools import setup

setup(name="wslogtail",
    entry_points={
        'console_scripts': [
            'wslogtail = wslogtail:main',
        ],
    }
)
