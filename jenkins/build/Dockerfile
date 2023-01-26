FROM jenkins/jenkins:2.375.2-jdk11

# set timezone
ENV TZ=Asia/Singapore
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

USER root

# RUN apt-get update; apt-get upgrade -y

USER jenkins
WORKDIR /home/jenkins

RUN jenkins-plugin-cli --plugins "blueocean:1.25.3 docker-workflow:1.28"

ENV PATH $PATH

COPY ./start.sh .

RUN echo $PATH

CMD [ "/bin/bash", "-l", "./start.sh" ]
# ENTRYPOINT []

# ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/jenkins.sh"]