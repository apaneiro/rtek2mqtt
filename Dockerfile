ARG BUILD_FROM
#FROM ${BUILD_FROM}
FROM python:3.11-buster

# Add env
ENV LANG C.UTF-8

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

COPY rtek.py /
COPY rclasses.py /
COPY mdefs.py /
COPY run.sh /

RUN chmod a+x /run.sh

CMD [ "/run.sh" ]