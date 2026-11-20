from glob import glob
import os

from setuptools import find_packages, setup

PACKAGE_NAME = "task4_bringup"

setup(
    name=PACKAGE_NAME,
    version="0.0.1",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + PACKAGE_NAME]),
        ("share/" + PACKAGE_NAME, ["package.xml"]),
        (os.path.join("share", PACKAGE_NAME, "config"), glob("config/*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Task Four Project Team",
    maintainer_email="maintainer@example.invalid",
    description="Workspace bootstrap for room-specific object search and counting.",
    license="Proprietary",
    entry_points={"console_scripts": [
        "workspace_info = task4_bringup.workspace_info:main",
        "scan_reader = task4_bringup.scan_reader:main",
    ]},
)
