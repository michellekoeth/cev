CEV : Claim Evolution Visualizer - Visualization tool for Patent Claims
***********************************************************************

cev is a Flask based webapp and API for visualizing patent claims. cev provides both
claim data corpus gathering, and analysis tools.


How to Install cev & Webapp/Webserver components:
=================================================
You can simply clone this repo using github to install. Then be sure to install all the dependencies as outlined in requirements.txt.

cev is written in python and uses flask as a web app server. The celery module is used to execute long data gathering tasks in the background. Redis is used
as the message broker for celery.

The amazing `spaCy library`_ is used for natural language (NL) processing.

.. _spaCy library: https://github.com/explosion/spaCy

Finally, if you want to serve up this web app using an http proxy like nginx, you'll need to install Gunicorn and configure nginx to pass web requests to Gunicorn
which then sends requests to Flask. As well, the celery module requires some configuration, and you will need to have redis configured.

Flask-Gunicorn-Nginx stack config: `fgnlink'_

.. _fgnlink: https://www.digitalocean.com/community/tutorials/how-to-serve-flask-applications-with-gunicorn-and-nginx-on-ubuntu-14-04

SystemD seems like an easy way to configure and manage Gunicorn, check out this document on how to use systemd: `systemdlink`_

.. _systemdlink: http://bartsimons.me/gunicorn-as-a-systemd-service/

Install redis: `installredislink`_

.. _installredislink: https://www.digitalocean.com/community/tutorials/how-to-install-and-configure-redis-on-ubuntu-16-04

Using redis with celery: `rediscelerylink`_

.. _rediscelerylink: http://docs.celeryproject.org/en/latest/getting-started/brokers/redis.html#broker-redis

