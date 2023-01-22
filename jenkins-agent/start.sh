#!/bin/bash

/usr/sbin/sshd -D &

curl -sO http://jenkins-master:8080/jnlpJars/agent.jar

java -jar agent.jar -jnlpUrl http://jenkins-master:8080/manage/computer/$JENKINS_AGENT_NAME/jenkins-agent.jnlp -secret $JENKINS_MASTER_SECRET -workDir "/home/jenkins"