FROM ubuntu:20.04

LABEL maintainer="Harold Alcala <harold.dev@gmail.com>"

ENV HOME /home/jenkins

# add jenkins and docker users
RUN groupadd jenkins -g 1000
RUN useradd -rm -d /home/jenkins -s /bin/bash -g jenkins -G jenkins -u 1000 jenkins

RUN groupadd docker -g 999
RUN useradd docker -g docker -u 999
RUN usermod -a -G docker jenkins

# set timezone
ENV TZ=Asia/Singapore
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# update system packages
RUN apt-get update; apt-get upgrade -y; apt-get install -y \
        python3.8 \
        python3-pip \
        libpython3.8-dev \
        net-tools \
        vim \
        curl \
        build-essential \
        libssl-dev \
        libffi-dev \
        python3-dev \
        git \
        openssh-server \
        unzip \
        jq

# RUN rm /etc/ssh/ssh_host_*
RUN dpkg-reconfigure openssh-server
RUN ssh-keygen -A
# RUN service start openssh-server

RUN pip3 install pip --upgrade

# install go
ENV GO_VERSION 1.18.10

RUN wget https://dl.google.com/go/go$GO_VERSION.linux-amd64.tar.gz

RUN tar -C /usr/local -xzf go$GO_VERSION.linux-amd64.tar.gz

RUN echo 'export PATH=$PATH:/usr/local/go/bin' >> /etc/bash.bashrc

# install java
RUN apt-get install -y openjdk-8-jdk maven

# package cleanup
RUN sed -i 's|session    required     pam_loginuid.so|session    optional     pam_loginuid.so|g' /etc/pam.d/sshd && \
    mkdir -p /var/run/sshd && \
    apt-get -qy autoremove

# install docker
RUN apt-get install -y docker.io

# install eksctl
RUN curl --silent --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp

RUN mv /tmp/eksctl /usr/local/bin

# install aws cli
RUN curl https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o awscliv2.zip
RUN unzip -o awscliv2.zip
RUN ./aws/install

USER jenkins
WORKDIR /home/jenkins

## install NVM
RUN touch .bash_profile

# install node and npm
ENV NVM_DIR .nvm
ENV NODE_VERSION 16.19.0
RUN mkdir $NVM_DIR

RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.3/install.sh | bash

RUN . $NVM_DIR/nvm.sh && \
  nvm install $NODE_VERSION && \
  nvm alias default 16

# Add user jenkins to the image
RUN mkdir /home/jenkins/.m2; mkdir /home/jenkins/.ssh; mkdir /home/jenkins/.docker

#ADD settings.xml /home/jenkins/.m2/
# Copy authorized keys
# COPY .ssh/authorized_keys /home/jenkins/.ssh/authorized_keys

RUN chown -R jenkins:jenkins /home/jenkins/.m2/ && \
    chown -R jenkins:jenkins /home/jenkins/.ssh/

RUN chown jenkins:jenkins /home/jenkins/.docker -R

# COPY ./start.sh .

USER root

# Standard SSH port
EXPOSE 22

CMD ["/usr/sbin/sshd", "-D"]
# CMD ["bash", "-l", "./start.sh"]