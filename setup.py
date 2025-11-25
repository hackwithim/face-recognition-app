from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="face-recognition-app",
    version="1.0.0",
    author="Kashinath Gaikwad",
    author_email="kashinathgaikwad844@gmail.com",
    description="A comprehensive web-based face recognition system built with Flask and OpenCV",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kashinathgaikwad/face-recognition-app",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Framework :: Flask",
        "Topic :: Scientific/Engineering :: Image Recognition",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    keywords="face-recognition opencv flask web-application computer-vision",
    project_urls={
        "Bug Reports": "https://github.com/kashinathgaikwad/face-recognition-app/issues",
        "Source": "https://github.com/kashinathgaikwad/face-recognition-app",
        "Documentation": "https://github.com/kashinathgaikwad/face-recognition-app#readme",
    },
)