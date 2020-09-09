from setuptools import setup

setup(
    name='lightkube',
    version="0.2.0",
    description='Lightweight kubernetes client library',
    long_description='Lightweight kubernetes client library',
    author='Giuseppe Tribulato',
    author_email='gtsystem@gmail.com',
    license='Apache Software License',
    url='https://github.com/gtsystem/lightkube',
    packages=['lightkube', 'lightkube.config', 'lightkube.core'],
    install_requires=[
        'lightkube-models >= 1.15.6.2',
        'httpx >= 0.14.1',
        'respx',
        'PyYAML',
        'backports-datetime-fromisoformat;python_version<"3.7"',
        'dataclasses;python_version<"3.7"'
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8'
    ]
)
