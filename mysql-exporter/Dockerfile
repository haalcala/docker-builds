FROM ubuntu:20

RUN apt-get update && apt-get install -y wget

# RUN wget https://github.com/prometheus/mysqld_exporter/releases/download/v0.12.1/mysqld_exporter-0.12.1.linux-amd64.tar.gz && \
#     tar xvfz mysqld_exporter-0.12.1.linux-amd64.tar.gz

COPY mysqld_exporter-0.12.1.linux-amd64.tar.gz .

RUN tar xvfz mysqld_exporter-0.12.1.linux-amd64.tar.gz

# ENV DATA_SOURCE_NAME='exporter:exporter123456789@(mysql-server:3306)/'

WORKDIR mysqld_exporter-0.12.1.linux-amd64

EXPOSE 19104

CMD [ "./mysqld_exporter" ]