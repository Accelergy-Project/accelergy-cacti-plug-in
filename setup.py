from setuptools import setup
from setuptools.command.build_py import build_py
import os
import shutil
import subprocess
import glob

# Remove build directory
THIS_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
if os.path.exists(os.path.join(THIS_SCRIPT_DIR, "build")):
    shutil.rmtree(os.path.join(THIS_SCRIPT_DIR, "build"))


def readme():
    with open("README.md") as f:
        return f.read()


setup(
    name="accelergy-cacti-plug-in",
    version="0.1",
    description="An energy estimation plug-in for Accelergy framework using CACTI",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Topic :: Scientific/Engineering :: Electronic Design Automation (EDA)",
    ],
    keywords="accelerator hardware energy estimation CACTI",
    author="Yannan Wu",
    author_email="nelliewu@mit.edu",
    license="MIT",
    install_requires=["pyYAML"],
    python_requires=">=3.8",
    data_files=[
        (
            "share/accelergy/estimation_plug_ins/accelergy-cacti-plug-in",
            [
                "cacti.estimator.yaml",
                "cacti_wrapper.py",
                "default_cfg.cfg",
            ],
        ),
        (
            "share/accelergy/estimation_plug_ins/accelergy-cacti-plug-in",
            ["cacti/cacti"],
        ),
        (
            "share/accelergy/estimation_plug_ins/accelergy-cacti-plug-in/tech_params",
            [f for f in glob.glob("cacti/tech_params/*") if os.path.isfile(f)],
        ),
    ],
    include_package_data=True,
    entry_points={},
    zip_safe=False,
)
