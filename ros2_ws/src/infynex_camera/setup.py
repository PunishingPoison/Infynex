from setuptools import find_packages, setup

package_name = 'infynex_camera'

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
    description='INFYNEX Camera Capture Node',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'camera_capture_node = infynex_camera.camera_capture_node:main',
        ],
    },
)
