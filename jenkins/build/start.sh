#!/bin/bash -x

echo HOME $HOME

[ ! -e "$HOME/.ssh" ] && mkdir $HOME/.ssh

cd $HOME/.ssh

if [ ! -e "id_rsa-jenkins-agent" ]; then
    ssh-keygen -t rsa -P "" -f $HOME/.ssh/id_rsa-jenkins-agent -C "The access key for Jenkins slaves"

    cat id_rsa-jenkins-agent.pub >> authorized_keys
fi

export PATH="$PATH:/opt/java/openjdk/bin"
export JAVA_HOME="/opt/java/openjdk/bin"

echo PATH: $PATH

# sleep Infinity

/usr/local/bin/jenkins.sh