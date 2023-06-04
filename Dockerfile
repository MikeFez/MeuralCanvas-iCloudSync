FROM python:3.10

LABEL maintainer="Michael Fessenden <michael@mikefez.com>"

ENV IN_CONTAINER=true
ENV USERNAME=Meural
ENV PUID=1000
ENV PGID=1000
ENV LOGURU_LEVEL=INFO
ENV ICLOUD_ALBUM_URL=
ENV MEURAL_USERNAME=
ENV MEURAL_PASSWORD=
ENV MEURAL_PLAYLIST=
ENV ENTER=

RUN apt-get update && \
    apt-get -y install nano && \
    rm -rf /var/lib/apt/lists/*

RUN groupadd -g ${PGID} ${USERNAME} \
    && useradd -u ${PUID} -g ${USERNAME} -d /home/${USERNAME} ${USERNAME} \
    && mkdir /home/${USERNAME} \
    && chown -R ${USERNAME}:${USERNAME} /home/${USERNAME}

ADD app /opt/app

RUN cd /opt/app && pip3 install --no-cache-dir -r requirements.txt

ENTRYPOINT ["/bin/sh", "-c", "cd /opt/app \
    pip3 install --no-cache-dir -r requirements.txt && \
    if ! [ -z $ENTER ]; then \
        python3 app.py & \
        /bin/bash; \
    else \
        python3 app.py;  \
    fi"]