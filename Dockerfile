FROM python:3.10

LABEL maintainer="Michael Fessenden <michael@mikefez.com>"

ENV IN_CONTAINER=true
ENV USERNAME=Meural
ENV PUID=1000
ENV PGID=1000
ENV LOGURU_LEVEL=INFO
ENV UPDATE_FREQUENCY_MINS=
ENV MEURAL_USERNAME=
ENV MEURAL_PASSWORD=

# RUN apt-get update && \
#     apt-get -y install nano && \
#     rm -rf /var/lib/apt/lists/*

RUN groupadd -g ${PGID} ${USERNAME} \
    && useradd -u ${PUID} -g ${USERNAME} -d /home/${USERNAME} ${USERNAME} \
    && mkdir /home/${USERNAME} \
    && chown -R ${USERNAME}:${USERNAME} /home/${USERNAME}

ADD app /opt/app

RUN cd /opt/app && pip3 install --no-cache-dir -r requirements.txt

ENTRYPOINT ["/bin/sh", "-c", "cd /opt/app \
    && if [ ! -d '/images' ]; then \
        echo '/inbox volume was not mounted!'; \
    elif [ ! -d '/config' ]; then \
        echo '/config volume was not mounted!'; \
    else \
        python3 main.py; \
    fi"]