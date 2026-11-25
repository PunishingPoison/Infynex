FROM osrf/ros:jazzy-desktop

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV ROS_DISTRO=jazzy

# Install build essentials, Gazebo Harmonic, and system utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    ninja-build \
    git \
    rsync \
    wget \
    curl \
    lsb-release \
    gnupg \
    software-properties-common \
    pkg-config \
    libunwind-dev \
    cppzmq-dev \
    protobuf-compiler \
    libprotobuf-dev \
    libopencv-dev \
    libxml2-dev \
    libxml2-utils \
    python3-pip \
    python3-dev \
    python3-setuptools \
    python3-wheel \
    python3-colcon-common-extensions \
    python3-rosdep \
    net-tools \
    iproute2 \
    iputils-ping \
    socat \
    tmux \
    ccache \
    astyle \
    genromfs \
    mesa-utils \
    libgl1 \
    libglx-mesa0 \
    libgl1-mesa-dri \
    && rm -rf /var/lib/apt/lists/*

# Add Gazebo Harmonic repository and install gz-harmonic + ROS-Gazebo bridge
RUN wget https://packages.osrfoundation.org/gazebo.gpg -O /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null && \
    apt-get update && apt-get install -y --no-install-recommends \
    gz-harmonic \
    ros-jazzy-ros-gz \
    ros-jazzy-ros-gz-sim \
    ros-jazzy-ros-gz-bridge \
    ros-jazzy-ros-gz-image \
    ros-jazzy-actuator-msgs \
    && rm -rf /var/lib/apt/lists/*

# Install PX4 Python build dependencies, MAVSDK and runtime tools
RUN pip3 install --no-cache-dir --break-system-packages --ignore-installed \
    cerberus \
    "empy>=3.3,<4" \
    future \
    jinja2 \
    jsonschema \
    kconfiglib \
    lark \
    pkgconfig \
    psutil \
    pycryptodome \
    pygments \
    pymavlink \
    pynacl \
    pyros-genmsg \
    pyserial \
    pyulog \
    sympy \
    toml \
    mavsdk \
    opencv-python-headless \
    paho-mqtt

ENV CI=true

# Build and install Micro-XRCE-DDS-Agent for ROS 2 uORB bridge
WORKDIR /tmp
RUN git clone --depth 1 -b v2.4.3 https://github.com/eProsima/Micro-XRCE-DDS-Agent.git && \
    cd Micro-XRCE-DDS-Agent && \
    mkdir build && cd build && \
    . /opt/ros/jazzy/setup.sh && \
    cmake .. -DCMAKE_INSTALL_PREFIX=/usr/local -DUAGENT_USE_SYSTEM_FASTDDS=ON && \
    make -j$(nproc) && \
    make install && \
    ldconfig && \
    rm -rf /tmp/Micro-XRCE-DDS-Agent

# Configure git and clone PX4 Autopilot source
RUN git config --global --add safe.directory "*"
WORKDIR /opt
RUN git clone --depth 1 --branch v1.15.4 https://github.com/PX4/PX4-Autopilot.git && \
    cd PX4-Autopilot && \
    git submodule update --init --depth 1 \
        src/modules/mavlink/mavlink \
        src/modules/uxrce_dds_client/Micro-XRCE-DDS-Client \
        src/lib/events/libevents \
        Tools/simulation/gz \
        src/lib/crypto/monocypher \
        src/lib/crypto/libtomcrypt \
        src/lib/crypto/libtommath \
        src/lib/heatshrink/heatshrink

# Pre-build PX4 SITL target
WORKDIR /opt/PX4-Autopilot
RUN make px4_sitl_default

# Copy simulation entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Simulation environment exports
ENV PX4_HOME=/opt/PX4-Autopilot
ENV PATH="/opt/PX4-Autopilot/build/px4_sitl_default/bin:${PATH}"
ENV GZ_SIM_RESOURCE_PATH="/opt/PX4-Autopilot/Tools/simulation/gz/models:/opt/PX4-Autopilot/Tools/simulation/gz/worlds"

WORKDIR /workspace
ENTRYPOINT ["/entrypoint.sh"]
CMD ["headless"]
