from setuptools import find_packages, setup

package_name = 'infynex_drone'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='VCMR',
    maintainer_email='vcmr@infynex.io',
    description='INFYNEX Drone Controller Node',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'drone_telemetry_node = infynex_drone.drone_telemetry_node:main',
            'drone_controller_node = infynex_drone.drone_controller_node:main',
        ],
    },
)
