# Use the official Filebeat image as the base image
FROM docker.elastic.co/beats/filebeat:7.16.1

USER root

# Set environment variables
ENV USER_UID=1001 \
    USER_NAME=filebeat \
    GROUP_NAME=filebeat

# Create the 'filebeat' group and user with UID 1001
RUN groupadd -r ${GROUP_NAME} --gid ${USER_UID} && \
    useradd -r -u ${USER_UID} -g ${GROUP_NAME} ${USER_NAME} && \
    mkdir -p /usr/share/filebeat/data && \
    chown -R ${USER_NAME}:${GROUP_NAME} /usr/share/filebeat

# Switch to the new user
USER ${USER_UID}
