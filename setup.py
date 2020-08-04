# coding: utf-8
# flake8: noqa

"""
Pure Storage Python SDK for FlashArray and VMware Integration
"""


from setuptools import setup, find_packages  # noqa: H301

NAME = 'purepyvmware'
VERSION = '1.0.0'

REQUIRES = ['purestorage >= 1.18.0', 'pyvmomi >= 6.7.3']

readme = open('README.md', 'r')
README_TEXT = readme.read()
readme.close()

setup(
    name=NAME,
    version=VERSION,
    description='Pure Storage Python SDK for FlashArray and VMware Integration',
    author='Jacob Hopkinson',
    author_email='jhop@purestorage.com',
    url='https://github.com/PureStorage-OpenConnect/PureStorage-VMware-Python-SDK',
    download_url='https://github.com/PureStorage-OpenConnect/PureStorage-VMware-Python-SDK/archive/master.zip',
    keywords=['Pure Storage', 'Python', 'clients', 'REST', 'API', 'FlashArray', 'VMware'],
    license='Apache-2.0',
    python_requires='>=3.6',
    install_requires=REQUIRES,
    packages=find_packages(),
    include_package_data=True,
    long_description=README_TEXT,
    long_description_content_type='text/markdown'
)
