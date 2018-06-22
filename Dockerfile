FROM python:3.6.4-alpine
MAINTAINER Eloy Zuniga Jr, eloyz.email@gmail.com

# Install base packages
RUN apk update && apk add curl && apk add git \
  && apk add curl-dev && apk add vim \
  && apk add libxml2-dev && apk add libxslt-dev \
  && apk add libffi-dev && apk add gmp-dev \
  && apk add openssl-dev && apk add python3-dev \
  && apk add bash && apk add bash-completion \
  && apk add make && apk add gcc \
  && apk add linux-headers && apk add musl-dev \
  && apk add ncurses && apk add openssh-client

# Install python packages useful for all containers
RUN python3 -m pip install ipython freezegun==0.3.9 pytest==3.2.0 \
    flake8==3.4.1 pytest-cov==2.5.1

# Umask the root user so that files written to the filesystem in
# a container can be accessed by the user correctly from the host
# system and add a PS1
ADD extra/.bashrc /root/.bashrc

# Create the SSH config directory
RUN mkdir /root/.ssh
RUN chmod 700 /root/.ssh

# UTF-8 on all the time
ENV TERM=xterm
ENV LC_ALL=C.UTF-8 LANG=C.UTF-8

# Add pynab code
ADD . /code/pynab

# Install requirements and install pynab (in editable mode)
RUN python3 -m pip install -r /code/pynab/requirements.pip && python3 -m pip install -e /code/pynab
RUN echo 'eval "$(_PYNAB_COMPLETE=source pynab)"' >> /root/.bashrc

# Set working directory
WORKDIR /code/pynab
