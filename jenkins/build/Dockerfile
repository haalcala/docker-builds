FROM jenkins/jenkins:lts-jdk11

USER root

# RUN apt-get update; apt-get upgrade -y

USER jenkins
WORKDIR /home/jenkins

ENV PATH $PATH

COPY ./start.sh .

RUN echo $PATH

CMD [ "/bin/bash", "-l", "./start.sh" ]
# ENTRYPOINT []

# ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/jenkins.sh"]