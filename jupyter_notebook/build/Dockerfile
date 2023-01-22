FROM ubuntu

ARG NB_USER="jupyter-notebook"
ARG NB_UID="1000"
ARG NB_GID="100"

RUN echo "* soft nproc 65535" >> /etc/security/limits.conf
RUN echo "* hard nproc 65535" >> /etc/security/limits.conf
RUN echo "* soft nofile 1048576" >> /etc/security/limits.conf
RUN echo "* hard nofile 1048576" >> /etc/security/limits.conf
RUN echo "" >> /etc/security/limits.conf
RUN echo "linuxhint soft nproc 100000" >> /etc/security/limits.conf
RUN echo "linuxhint hard nproc 100000" >> /etc/security/limits.conf
RUN echo "linuxhint soft nofile 1048576" >> /etc/security/limits.conf
RUN echo "linuxhint hard nofile 1048576" >> /etc/security/limits.conf

RUN ln -s /usr/share/zoneinfo/Asia/Singapore /etc/localtime

RUN apt-get update

RUN apt-get install -y vim iptraf tcpdump net-tools iputils-ping curl wget

RUN apt-get install -y build-essential zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev libssl-dev libreadline-dev libffi-dev libsqlite3-dev wget libbz2-dev

RUN wget https://www.python.org/ftp/python/3.9.1/Python-3.9.1.tgz && \
        tar -xf Python-3.9.1.tgz && \
        cd Python-3.9.1 && \
        ./configure --enable-optimizations && \
        make -j 12 && \
        make altinstall && \
        python3.9 -m pip install --upgrade pip

RUN python3.9 -m pip install pandas numpy scipy requests rich tensorflow seaborn jupyterlab

RUN groupadd ${NB_USER} -g ${NB_UID}
RUN useradd -rm -d /home/${NB_USER} -s /bin/bash -g ${NB_USER} -G ${NB_USER} -u ${NB_UID} ${NB_USER}

USER ${NB_USER}

WORKDIR /home/${NB_USER}

ENV PATH="$PATH:~/.local/bin/"

EXPOSE 8888

CMD ["jupyter-lab", "--ServerApp.ip=0.0.0.0", "--ServerApp.open_browser=False", "--ExtensionApp.open_browser=False"]
