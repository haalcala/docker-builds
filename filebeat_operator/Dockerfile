FROM ubuntu

RUN groupadd mattermost -g 1001
RUN useradd -rm -d /home/mattermost -s /bin/bash -g mattermost -G mattermost -u 1001 mattermost

RUN groupadd docker -g 1002
RUN useradd docker -g docker -u 1002
RUN usermod -a -G docker mattermost

RUN apt-get update; apt-get upgrade -y; apt-get install -y docker.io python3 python3-pip net-tools vim

USER mattermost

WORKDIR /app

CMD ["bash", "-l", "./start.sh"]