FROM jenkins/jenkins:lts-jdk11

USER root

RUN apt-get update; apt-get upgrade -y

USER jenkins

ENV PATH $PATH

COPY ./start.sh .

RUN echo $PATH

CMD [ "bash", "-l", "./start.sh" ]

# ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/jenkins.sh"]