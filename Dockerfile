ARG BUILD_FROM
FROM python:3.13-slim

# Add env
ENV LANG C.UTF-8

# Set shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG BUILD_ARCH
ARG BUILD_DATE
ARG BUILD_REF
ARG BUILD_VERSION

LABEL \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version=${BUILD_VERSION} \
    org.label-schema.build-date=${BUILD_DATE} \
    org.label-schema.vcs-ref=${BUILD_REF}

RUN pip3 install asyncio
RUN pip3 install paho-mqtt
RUN pip3 install pyyaml
RUN pip3 install aiomqtt

ARG BASHIO_VERSION="v0.16.4"

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && apt-get install -y --no-install-recommends jq \
    && curl -J -L -o /tmp/bashio.tar.gz \
    "https://github.com/hassio-addons/bashio/archive/${BASHIO_VERSION}.tar.gz" \
    && mkdir /tmp/bashio \
    && tar zxvf \
    /tmp/bashio.tar.gz \
    --strip 1 -C /tmp/bashio \
    && mv /tmp/bashio/lib /usr/lib/bashio \
    && ln -s /usr/lib/bashio/bashio /usr/bin/bashio

COPY rtek.py /
COPY rclasses.py /
COPY mdefs.py /
COPY run.sh /

RUN chmod a+x /run.sh

CMD [ "/run.sh" ]